"""Admin Authentication, Password Hashing, Session Management, and Audit Trail Service."""

import hashlib
import hmac
import json
import os
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.logging import get_logger
from app.models.admin_auth import AdminAuditEvent, AdminSession, StaffCredential
from app.models.role import Role
from app.models.user import User

logger = get_logger(__name__)

# Scrypt OWASP-recommended parameters
SCRYPT_N = 16384
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_SALT_LEN = 32
SCRYPT_KEY_LEN = 64
MAX_FAILED_LOGIN_ATTEMPTS = 5
MAX_PASSWORD_LENGTH = 128
_DUMMY_SCRYPT_HASH = (
    f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${'00' * SCRYPT_SALT_LEN}${'00' * SCRYPT_KEY_LEN}"
)


def sanitize_audit_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    """Sanitize metadata: strictly exclude password or credential keys and redact secrets."""
    if not metadata:
        return {}
    sensitive_substrings = (
        "password",
        "secret",
        "token",
        "auth",
        "cookie",
        "key",
        "credential",
        "database",
    )
    safe_meta: dict[str, Any] = {}
    for k, v in metadata.items():
        if any(sec in k.lower() for sec in sensitive_substrings):
            continue
        if isinstance(v, dict):
            safe_meta[k] = sanitize_audit_metadata(v)
        elif isinstance(v, str):
            sanitized_val = re.sub(r"Bearer\s+[A-Za-z0-9_\-\.]+", "Bearer [REDACTED]", v)
            sanitized_val = re.sub(
                r"(password|token|secret)=[^&\s]+",
                r"\1=[REDACTED]",
                sanitized_val,
                flags=re.IGNORECASE,
            )
            safe_meta[k] = sanitized_val
        else:
            safe_meta[k] = v
    return safe_meta


class AdminAuthService:
    """Service handling secure staff authentication, scrypt password hashing, and session tokens."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    # -------------------------------------------------------------------------
    # Password Hashing & Verification (scrypt)
    # -------------------------------------------------------------------------
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a plaintext password using scrypt with a unique 32-byte salt."""
        if not password or len(password) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        if len(password) > MAX_PASSWORD_LENGTH:
            raise ValueError(f"Password must not exceed {MAX_PASSWORD_LENGTH} characters.")
        salt = os.urandom(SCRYPT_SALT_LEN)
        derived = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=SCRYPT_N,
            r=SCRYPT_R,
            p=SCRYPT_P,
            maxmem=33554432,
            dklen=SCRYPT_KEY_LEN,
        )
        salt_hex = salt.hex()
        hash_hex = derived.hex()
        return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt_hex}${hash_hex}"

    @staticmethod
    def verify_password(plain_password: str, stored_hash: str) -> bool:
        """Verify password against stored scrypt hash using constant-time comparison."""
        try:
            if not plain_password or len(plain_password) > MAX_PASSWORD_LENGTH:
                return False
            parts = stored_hash.split("$")
            if len(parts) != 6 or parts[0] != "scrypt":
                return False
            n = int(parts[1])
            r = int(parts[2])
            p = int(parts[3])
            # Bound algorithmic resource parameters to prevent algorithmic DoS
            if n > 65536 or r > 16 or p > 16:
                return False
            salt = bytes.fromhex(parts[4])
            expected_key = bytes.fromhex(parts[5])
            if len(salt) > 64 or len(expected_key) > 128:
                return False

            derived = hashlib.scrypt(
                plain_password.encode("utf-8"),
                salt=salt,
                n=n,
                r=r,
                p=p,
                maxmem=33554432,
                dklen=len(expected_key),
            )
            return hmac.compare_digest(derived, expected_key)
        except Exception as e:
            logger.warning("Error verifying password hash: %s", type(e).__name__)
            return False

    # -------------------------------------------------------------------------
    # Authentication & Session Management
    # -------------------------------------------------------------------------
    @staticmethod
    def hash_session_token(token: str) -> str:
        """Compute SHA-256 digest of session token for safe persistence."""
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    async def authenticate_staff(
        self,
        session: AsyncSession,
        username: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[User, str, str]:
        """Authenticate staff user.

        Returns:
            tuple[User, raw_session_token, csrf_token]

        Raises:
            ValueError: On invalid credentials, account locked, or non-staff user.
        """
        # Truncate user-agent to avoid header-driven storage bloat
        safe_user_agent = user_agent[:255] if user_agent else None

        # Check maximum password length to avoid hashing multi-megabyte payloads
        if len(password) > MAX_PASSWORD_LENGTH:
            raise ValueError("Invalid username or password.")

        # Lookup credential
        stmt = (
            select(StaffCredential)
            .options(selectinload(StaffCredential.user).selectinload(User.roles))
            .where(StaffCredential.username == username.strip())
        )
        result = await session.execute(stmt)
        cred = result.scalar_one_or_none()

        if not cred:
            # Timing oracle mitigation: compute dummy scrypt calculation so response
            # latency is indistinguishable between existing and non-existing accounts
            self.verify_password(password, _DUMMY_SCRYPT_HASH)
            raise ValueError("Invalid username or password.")

        if cred.is_locked:
            raise ValueError(
                "Account is locked due to excessive failed login attempts."
            )

        user = cred.user
        if not user or not user.is_active:
            raise ValueError("Account is deactivated.")

        # Verify password
        if not self.verify_password(password, cred.password_hash):
            cred.failed_login_attempts += 1
            if cred.failed_login_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
                cred.is_locked = True
                logger.warning(
                    "Staff account '%s' locked after %d failed attempts",
                    username,
                    cred.failed_login_attempts,
                )
            await session.commit()
            raise ValueError("Invalid username or password.")

        # Check that user actually has staff roles (default deny)
        staff_roles = {
            "superadmin",
            "head_broker",
            "sales_broker",
            "rental_broker",
            "crm_operator",
            "marketing_specialist",
            "moderator",
        }
        user_roles = {r.name for r in user.roles}
        if not (user_roles & staff_roles):
            logger.warning("User id=%d attempted staff login without staff role", user.id)
            raise ValueError("Access denied: Not an authorized staff account.")

        # Reset failed attempts and update last login
        cred.failed_login_attempts = 0
        cred.last_login_at = datetime.now(UTC)

        # Generate tokens
        raw_session_token = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(32)
        session_hash = self.hash_session_token(raw_session_token)

        max_age = self.settings.admin_session_max_age_seconds
        expires_at = datetime.now(UTC) + timedelta(seconds=max_age)

        admin_session = AdminSession(
            session_token_hash=session_hash,
            user_id=user.id,
            csrf_token=csrf_token,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=safe_user_agent,
            is_revoked=False,
        )
        session.add(admin_session)

        # Audit event
        await self.record_audit_event(
            session,
            actor_user_id=user.id,
            action="auth.login",
            entity_type="user",
            entity_id=user.id,
            metadata={"username": username, "ip": ip_address},
            ip_address=ip_address,
        )

        await session.commit()
        return user, raw_session_token, csrf_token

    async def get_staff_from_session(
        self,
        session: AsyncSession,
        raw_session_token: str,
    ) -> tuple[User, AdminSession] | None:
        """Validate session token and return (User, AdminSession), or None if invalid/expired."""
        if not raw_session_token:
            return None

        token_hash = self.hash_session_token(raw_session_token)
        now = datetime.now(UTC)

        stmt = (
            select(AdminSession)
            .options(
                selectinload(AdminSession.user).selectinload(User.roles)
            )
            .where(
                AdminSession.session_token_hash == token_hash,
                AdminSession.is_revoked.is_(False),
                AdminSession.expires_at > now,
            )
        )
        result = await session.execute(stmt)
        admin_session = result.scalar_one_or_none()
        if not admin_session:
            return None

        user = admin_session.user
        if not user or not user.is_active:
            return None

        return user, admin_session

    async def revoke_session(
        self,
        session: AsyncSession,
        raw_session_token: str,
        actor_user_id: int | None = None,
        ip_address: str | None = None,
    ) -> bool:
        """Revoke active session (logout)."""
        if not raw_session_token:
            return False

        token_hash = self.hash_session_token(raw_session_token)
        stmt = (
            update(AdminSession)
            .where(AdminSession.session_token_hash == token_hash)
            .values(is_revoked=True)
        )
        result = await session.execute(stmt)

        if actor_user_id:
            await self.record_audit_event(
                session,
                actor_user_id=actor_user_id,
                action="auth.logout",
                entity_type="user",
                entity_id=actor_user_id,
                metadata={"revoked_token_hash_prefix": token_hash[:8]},
                ip_address=ip_address,
            )

        await session.commit()
        return bool(result.rowcount > 0)

    # -------------------------------------------------------------------------
    # Audit Logging
    # -------------------------------------------------------------------------
    @staticmethod
    async def record_audit_event(
        session: AsyncSession,
        *,
        actor_user_id: int | None,
        action: str,
        entity_type: str,
        entity_id: int | None = None,
        metadata: dict[str, Any] | None = None,
        ip_address: str | None = None,
    ) -> AdminAuditEvent:
        """Persist an immutable audit record."""
        safe_meta = sanitize_audit_metadata(metadata)

        event = AdminAuditEvent(
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            safe_metadata_json=json.dumps(safe_meta) if safe_meta else None,
            ip_address=ip_address,
            created_at=datetime.now(UTC),
        )
        session.add(event)
        await session.flush()
        return event

    # -------------------------------------------------------------------------
    # Bootstrap / Staff Setup Helper
    # -------------------------------------------------------------------------
    async def create_or_update_staff_credential(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        username: str,
        password: str,
        role_name: str | None = None,
    ) -> StaffCredential:
        """Create or update staff web credentials and assign staff role."""
        user = await session.get(User, user_id)
        if not user:
            raise ValueError(f"User with id={user_id} not found.")

        # If role specified, assign it
        if role_name:
            role_stmt = select(Role).where(Role.name == role_name)
            role = (await session.execute(role_stmt)).scalar_one_or_none()
            if not role:
                role = Role(name=role_name, description=f"Staff role: {role_name}")
                session.add(role)
                await session.flush()

            if role not in user.roles:
                user.roles.append(role)

        password_hash = self.hash_password(password)

        cred_stmt = select(StaffCredential).where(StaffCredential.user_id == user_id)
        cred = (await session.execute(cred_stmt)).scalar_one_or_none()

        if cred:
            cred.username = username.strip()
            cred.password_hash = password_hash
            cred.is_locked = False
            cred.failed_login_attempts = 0
        else:
            cred = StaffCredential(
                user_id=user.id,
                username=username.strip(),
                password_hash=password_hash,
                is_locked=False,
                failed_login_attempts=0,
            )
            session.add(cred)

        await session.commit()
        logger.info("Configured staff credentials for user_id=%d username='%s'", user.id, username)
        return cred
