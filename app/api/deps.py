"""FastAPI dependencies for authentication and database sessions."""

from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import (
    TelegramAuthExpiredError,
    TelegramAuthInvalidSignatureError,
    TelegramAuthMalformedError,
)
from app.database.session import get_db_session
from app.logging import get_logger
from app.models.user import User
from app.services.miniapp.auth import verify_telegram_init_data
from app.services.user_service import UserService

logger = get_logger(__name__)


async def get_current_miniapp_user(
    _request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    authorization: Annotated[str | None, Header()] = None,
    x_telegram_init_data: Annotated[str | None, Header()] = None,
    x_dev_telegram_id: Annotated[str | None, Header()] = None,
) -> User:
    """Validate Telegram Mini App initData cryptographic signature and resolve current User.

    CRITICAL SECURITY SPECIFICATION:
    1. Extracts initData from Authorization header ('tma <data>' or 'Bearer <data>')
       or 'X-Telegram-Init-Data' header.
    2. Gated development bypass only allowed if MINIAPP_DEV_AUTH_ENABLED is explicitly True.
    3. Production strictly requires HMAC-SHA256 verification using the bot token.
    4. Automatically binds the request to the cryptographically verified user.
    """
    settings = get_settings()
    user_service = UserService()

    # Extract initData
    init_data: str | None = None
    if authorization:
        parts = authorization.strip().split(" ", 1)
        if len(parts) == 2 and parts[0].lower() in ("tma", "bearer"):
            init_data = parts[1].strip()
        elif len(parts) == 1:
            init_data = parts[0].strip()

    if not init_data and x_telegram_init_data:
        init_data = x_telegram_init_data.strip()

    # Gated local development bypass
    if not init_data:
        if settings.miniapp_dev_auth_enabled and x_dev_telegram_id:
            try:
                dev_id = int(x_dev_telegram_id)
                user = await user_service.get_by_telegram_id(session, dev_id)
                if user:
                    return user
                # Initialize dev user if not in DB
                user = await user_service.initialize_user(
                    session,
                    telegram_id=dev_id,
                    username="dev_user",
                    first_name="Dev",
                )
                await session.commit()
                return user
            except ValueError:
                pass

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "AUTH_REQUIRED",
                    "message": "Telegram Mini App initData is required for authentication.",
                }
            },
        )

    # Cryptographic verification
    try:
        verified_payload = verify_telegram_init_data(
            init_data=init_data,
            bot_token=settings.bot_token,
            max_age_seconds=settings.telegram_init_data_max_age_seconds,
        )
    except TelegramAuthInvalidSignatureError as sig_err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "INVALID_SIGNATURE",
                    "message": "Invalid Telegram Mini App signature.",
                }
            },
        ) from sig_err
    except TelegramAuthExpiredError as exp_err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "AUTH_EXPIRED",
                    "message": (
                        "Telegram authentication session has expired. "
                        "Please reopen the Mini App."
                    ),
                }
            },
        ) from exp_err
    except TelegramAuthMalformedError as mal_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "AUTH_MALFORMED",
                    "message": str(mal_err),
                }
            },
        ) from mal_err

    tg_user = verified_payload["user"]
    tg_id = tg_user["id"]

    # Resolve or initialize user in database
    user = await user_service.initialize_user(
        session,
        telegram_id=tg_id,
        language=tg_user.get("language_code") or "uz",
        username=tg_user.get("username"),
        first_name=tg_user.get("first_name"),
        last_name=tg_user.get("last_name"),
    )
    await session.commit()
    return user
