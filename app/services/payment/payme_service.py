"""Payme Merchant JSON-RPC 2.0 integration service."""

import base64
from decimal import Decimal

from app.config import Settings
from app.logging import get_logger

logger = get_logger(__name__)

# Payme JSON-RPC standard error codes
PAYME_ERR_AUTH_FAILED = -32504
PAYME_ERR_METHOD_NOT_FOUND = -32601
PAYME_ERR_INVALID_PARAMS = -32602
PAYME_ERR_INVALID_AMOUNT = -31001
PAYME_ERR_TRANSACTION_NOT_FOUND = -31003
PAYME_ERR_UNABLE_CANCEL = -31008
PAYME_ERR_ORDER_NOT_FOUND = -31050
PAYME_ERR_ORDER_STATE_INVALID = -31051

# Payme state constants
PAYME_STATE_CREATED = 1
PAYME_STATE_PERFORMED = 2
PAYME_STATE_CANCELLED = -1
PAYME_STATE_CANCELLED_AFTER_PERFORM = -2


class PaymePaymentService:
    """Handles Payme Checkout URL generation and JSON-RPC 2.0 webhook processing."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.merchant_id = settings.payme_merchant_id
        self.secret_key = settings.payme_secret_key
        self.test_mode = settings.payme_test_mode

    def is_configured(self) -> bool:
        """Check whether merchant credentials are fully configured."""
        return bool(self.merchant_id and self.secret_key)

    def generate_payment_url(
        self,
        order_id: str,
        amount_uzs: Decimal,
        return_url: str | None = None,
    ) -> str | None:
        """Generate official Payme Checkout redirect URL.

        Amount in Payme must be converted to tiyins (1 UZS = 100 tiyins).
        Format: Base64(m={merchant_id};ac.order_id={order_id};a={amount_in_tiyin};c={return_url})
        """
        if not self.is_configured():
            return None

        amount_tiyin = int(amount_uzs * 100)
        ret_url = return_url or self.settings.payment_return_url

        payload = f"m={self.merchant_id};ac.order_id={order_id};a={amount_tiyin}"
        if ret_url:
            payload += f";c={ret_url}"

        encoded = base64.b64encode(payload.encode("utf-8")).decode("utf-8")
        base_url = (
            "https://test.checkout.paycom.uz"
            if self.test_mode
            else "https://checkout.paycom.uz"
        )
        return f"{base_url}/{encoded}"

    def verify_basic_auth(self, auth_header: str | None) -> bool:
        """Verify HTTP Basic Authentication header sent by Payme.

        Header format: 'Basic <base64(Paycom:secret_key)>'
        """
        if not self.secret_key or not auth_header:
            return False

        if not auth_header.startswith("Basic "):
            return False

        try:
            encoded_credentials = auth_header.split(" ", 1)[1].strip()
            decoded = base64.b64decode(encoded_credentials).decode("utf-8")
            parts = decoded.split(":", 1)
            if len(parts) != 2:
                return False
            login, password = parts
            return login.lower() == "paycom" and password == self.secret_key
        except Exception:
            return False
