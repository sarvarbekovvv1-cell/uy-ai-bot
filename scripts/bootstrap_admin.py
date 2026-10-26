#!/usr/bin/env python3
"""Operational CLI tool for bootstrapping staff accounts and setting web credentials.

Usage:
    python3 scripts/bootstrap_admin.py --telegram-id 123456789 --username admin --role superadmin
    python3 scripts/bootstrap_admin.py --user-id 1 --username admin --role superadmin
"""

import argparse
import asyncio
import getpass
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.database.session import get_session_factory
from app.models.role import Role
from app.models.user import User
from app.services.admin_auth_service import AdminAuthService


async def bootstrap_staff_account(
    session: AsyncSession,
    *,
    telegram_id: int | None,
    user_id: int | None,
    username: str,
    password: str,
    role_name: str,
) -> None:
    """Safely bootstrap or promote a user to staff."""
    user = None
    if user_id:
        user = await session.get(User, user_id)
    elif telegram_id:
        stmt = select(User).where(User.telegram_id == telegram_id)
        user = (await session.execute(stmt)).scalar_one_or_none()

    if not user:
        if not telegram_id:
            print(f"Error: User with id={user_id} not found.", file=sys.stderr)
            sys.exit(1)
        # Create a new local staff user
        user = User(
            telegram_id=telegram_id,
            first_name="Staff",
            last_name="Administrator",
            is_active=True,
            is_verified=True,
        )
        session.add(user)
        await session.flush()
        print(f"Created new user id={user.id} for telegram_id={telegram_id}")

    # Ensure role exists and assign
    role_stmt = select(Role).where(Role.name == role_name)
    role = (await session.execute(role_stmt)).scalar_one_or_none()
    if not role:
        role = Role(name=role_name, description=f"Staff role: {role_name}")
        session.add(role)
        await session.flush()

    if role not in user.roles:
        user.roles.append(role)
        print(f"Assigned role '{role_name}' to user id={user.id}")

    # Set staff credentials
    settings = get_settings()
    auth_service = AdminAuthService(settings)
    await auth_service.create_or_update_staff_credential(
        session,
        user_id=user.id,
        username=username,
        password=password,
    )

    print(
        f"✅ Successfully configured staff credentials for username '{username}' "
        f"(User #{user.id}, Role: {role_name})"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap UyAI staff web credentials")
    parser.add_argument("--telegram-id", type=int, help="Telegram ID of the user to promote")
    parser.add_argument("--user-id", type=int, help="Internal User ID of the user to promote")
    parser.add_argument("--username", type=str, required=True, help="Staff login username")
    parser.add_argument("--password", type=str, help="Password (prompted if omitted)")
    parser.add_argument(
        "--role",
        type=str,
        default="superadmin",
        choices=[
            "superadmin",
            "head_broker",
            "sales_broker",
            "rental_broker",
            "crm_operator",
            "marketing_specialist",
            "moderator",
        ],
        help="Staff role to assign",
    )

    args = parser.parse_args()

    if not args.telegram_id and not args.user_id:
        print("Error: Either --telegram-id or --user-id must be provided.", file=sys.stderr)
        sys.exit(1)

    password = args.password
    if not password:
        password = getpass.getpass("Enter staff password (min 8 chars): ")
        password_confirm = getpass.getpass("Confirm password: ")
        if password != password_confirm:
            print("Error: Passwords do not match.", file=sys.stderr)
            sys.exit(1)

    if len(password) < 8:
        print("Error: Password must be at least 8 characters long.", file=sys.stderr)
        sys.exit(1)

    if len(password) > 128:
        print("Error: Password must not exceed 128 characters.", file=sys.stderr)
        sys.exit(1)

    session_factory: async_sessionmaker[AsyncSession] = get_session_factory()

    async def run():
        async with session_factory() as session:
            await bootstrap_staff_account(
                session,
                telegram_id=args.telegram_id,
                user_id=args.user_id,
                username=args.username,
                password=password,
                role_name=args.role,
            )

    asyncio.run(run())


if __name__ == "__main__":
    main()
