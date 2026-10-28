"""Click Merchant / Shop API integration service."""

import hashlib
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

from app.config import Settings
from app.logging import get_logger

logger = get_logger(__name__)

# Click standard response error codes
CLICK_ERROR_SUCCESS = 0
CLICK_ERROR_SIGN_CHECK_FAILED = -1
CLICK_ERROR_INVALID_AMOUNT = -2
CLICK_ERROR_ACTION_NOT_FOUND = -3
CLICK_ERROR_ALREADY_PAID = -4
CLICK_ERROR_ORDER_NOT_FOUND = -5
CLICK_ERROR_TRANSACTION_NOT_FOUND = -6
CLICK_ERROR_FAILED_UPDATE = -7
CLICK_ERROR_REQUEST_ERROR = -8
CLICK_ERROR_TRANSACTION_CANCELLED = -9


class ClickPaymentService:
    """Handles Click Checkout URL generation and Shop API webhook processing."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.service_id = settings.click_service_id
        self.merchant_id = settings.click_merchant_id
        self.secret_key = settings.click_secret_key
        self.merchant_user_id = settings.click_merchant_user_id

    def is_configured(self) -> bool:
        """Check whether merchant credentials are fully configured."""
        return bool(self.service_id and self.merchant_id and self.secret_key)

    def generate_payment_url(
        self,
        order_id: str,
        amount_uzs: Decimal,
        return_url: str | None = None,
    ) -> str | None:
        """Generate official Click Checkout redirect URL.

        Format: https://my.click.uz/services/pay?service_id=...&merchant_id=...&amount=...&transaction_param=...&return_url=...
        """
        if not self.is_configured():
            return None

        ret_url = return_url or self.settings.payment_return_url
        params: dict[str, Any] = {
            "service_id": self.service_id,
            "merchant_id": self.merchant_id,
            "amount": f"{amount_uzs:.2f}",
            "transaction_param": order_id,
        }
        if ret_url:
            params["return_url"] = ret_url

        return f"https://my.click.uz/services/pay?{urlencode(params)}"

    def verify_prepare_signature(
        self,
        click_trans_id: str,
        service_id: str,
        merchant_trans_id: str,
        amount: str,
        action: str,
        sign_time: str,
        sign_string: str,
    ) -> bool:
        """Verify MD5 signature for Click Prepare request (action=0)."""
        if not self.secret_key:
            return False

        raw = (
            f"{click_trans_id}"
            f"{service_id}"
            f"{self.secret_key}"
            f"{merchant_trans_id}"
            f"{amount}"
            f"{action}"
            f"{sign_time}"
        )
        expected = hashlib.md5(raw.encode("utf-8")).hexdigest()
        return expected.lower() == sign_string.lower()

    def verify_complete_signature(
        self,
        click_trans_id: str,
        service_id: str,
        merchant_trans_id: str,
        merchant_prepare_id: str,
        amount: str,
        action: str,
        sign_time: str,
        sign_string: str,
    ) -> bool:
        """Verify MD5 signature for Click Complete request (action=1)."""
        if not self.secret_key:
            return False

        raw = (
            f"{click_trans_id}"
            f"{service_id}"
            f"{self.secret_key}"
            f"{merchant_trans_id}"
            f"{merchant_prepare_id}"
            f"{amount}"
            f"{action}"
            f"{sign_time}"
        )
        expected = hashlib.md5(raw.encode("utf-8")).hexdigest()
        return expected.lower() == sign_string.lower()
