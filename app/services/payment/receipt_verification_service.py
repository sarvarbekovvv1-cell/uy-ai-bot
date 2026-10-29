"""AI-powered payment receipt verification service using Gemini Multimodal Vision."""

import json
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.logging import get_logger

logger = get_logger(__name__)

RECEIPT_ANALYSIS_PROMPT = """Siz O'zbekistondagi to'lov cheklarini
(Click, Payme, Uzum Bank, Anorbank, Apelsin, bank ilovalari yoki terminal cheklari)
aniq tahlil qiluvchi AI tizimisiz.

Ushbu tasvirni diqqat bilan tahlil qiling:
1. Tasvir haqiqiy to'lov yoki pul o'tkazmasi chekimi (skrinshot)?
2. To'lov muvaffaqiyatli amalga oshirilganmi (O'tkazildi, Muvaffaqiyatli, Оплачено, Успешно)?
3. To'langan summa aniq qancha (faqat UZS so'mda son ko'rinishida, masalan 15000)?
4. To'lov tizimi nomi (click, payme, uzum, bank_app, boshqa).
5. Qabul qiluvchi karta raqami yoki qisqartmasi (agar ko'ringan bo'lsa).
6. Qisqa izoh.

MUHIM: Faqat va faqat quyidagi JSON formatida javob bering:
{
  "is_receipt": true,
  "is_successful": true,
  "amount_uzs": 15000,
  "payment_system": "click",
  "recipient_card": "9860 **** 1234",
  "transaction_date": "2026-10-28",
  "notes": "Click orqali 15 000 so'm muvaffaqiyatli to'langan"
}

Agar tasvir to'lov cheki bo'lmasa yoki tushunarsiz rasm bo'lsa:
{
  "is_receipt": false,
  "is_successful": false,
  "amount_uzs": 0,
  "payment_system": "unknown",
  "recipient_card": null,
  "transaction_date": null,
  "notes": "Tasvir to'lov cheki emas"
}
"""


class ReceiptVerificationResult(BaseModel):
    """Structured result of payment receipt verification."""

    is_receipt: bool = Field(default=False)
    is_successful: bool = Field(default=False)
    amount_uzs: Decimal = Field(default=Decimal(0))
    payment_system: str = Field(default="unknown")
    recipient_card: str | None = Field(default=None)
    transaction_date: str | None = Field(default=None)
    notes: str = Field(default="")
    raw_response: dict[str, Any] = Field(default_factory=dict)


class ReceiptVerificationService:
    """Verifies P2P transaction receipts via Gemini Multimodal Vision API."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.api_key = self.settings.gemini_api_key
        self.model_name = self.settings.gemini_model

    async def verify_receipt(
        self,
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
    ) -> ReceiptVerificationResult:
        """Analyze receipt image bytes using Gemini Vision and return structured validation."""
        if not self.api_key:
            logger.warning("GEMINI_API_KEY is not set; falling back to mock receipt check.")
            # If no API key configured, return failed receipt result with helpful note
            return ReceiptVerificationResult(
                is_receipt=False,
                is_successful=False,
                amount_uzs=Decimal(0),
                notes="Gemini API kaliti ulanmagan.",
            )

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key)
            part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)

            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
            )

            response = await client.aio.models.generate_content(
                model=self.model_name,
                contents=[part, RECEIPT_ANALYSIS_PROMPT],
                config=config,
            )

            raw_text = response.text or "{}"
            cleaned = raw_text.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            data = json.loads(cleaned)

            amount_raw = data.get("amount_uzs", 0)
            try:
                # Remove spaces or currency suffixes if any
                clean_amount_str = str(amount_raw).replace(" ", "").replace(",", "")
                amount = Decimal(clean_amount_str)
            except (InvalidOperation, ValueError):
                amount = Decimal(0)

            return ReceiptVerificationResult(
                is_receipt=bool(data.get("is_receipt", False)),
                is_successful=bool(data.get("is_successful", False)),
                amount_uzs=amount,
                payment_system=str(data.get("payment_system", "unknown")),
                recipient_card=data.get("recipient_card"),
                transaction_date=data.get("transaction_date"),
                notes=str(data.get("notes", "")),
                raw_response=data,
            )

        except Exception as exc:
            logger.error("Failed to verify receipt with Gemini: %s", exc)
            return ReceiptVerificationResult(
                is_receipt=False,
                is_successful=False,
                amount_uzs=Decimal(0),
                notes=f"AI tahlilida xatolik yuz berdi: {exc}",
            )
