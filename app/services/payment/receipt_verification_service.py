"""AI-powered payment receipt verification service using Gemini Multimodal Vision."""

import json
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.logging import get_logger

logger = get_logger(__name__)

RECEIPT_ANALYSIS_PROMPT = """Siz O'zbekistondagi bank to'lov cheklarini
(Click, Payme, Uzum Bank, Anorbank, Apelsin, bank ilovalari yoki terminal cheklari)
aniq tahlil qiluvchi professional AI inspektorisiz.

Ushbu tasvirni diqqat bilan o'rganib chiqib, quyidagi ma'lumotlarni ajrating:
1. Tasvir haqiqiy to'lov yoki pul o'tkazmasi chekimi (skrinshot)?
2. To'lov muvaffaqiyatli amalga oshirilganmi (O'tkazildi, Muvaffaqiyatli, Оплачено, Успешно)?
3. To'langan summa aniq qancha (faqat raqam, masalan 50000)?
4. Tranzaksiya ID yoki chek raqami (agar mavjud bo'lsa).
5. Qabul qiluvchi karta raqami yoki uning ko'ringan qismi (masalan, 9860 **** 1234).
6. To'lov sanasi va vaqti.
7. To'lov tizimi nomi (click, payme, uzum, anor, bank_app, boshqa).
8. Rasm sifati va ishonchliligi (aniq, tushunarsiz, qirqilgan, past_sifat).

MUHIM: Faqat va faqat quyidagi JSON formatida javob qaytaring:
{
  "is_receipt": true,
  "is_successful": true,
  "amount_uzs": 50000,
  "transaction_id": "TRX-12345678",
  "recipient_card": "9860 **** 1234",
  "transaction_date": "2026-10-29 14:00",
  "payment_system": "click",
  "image_quality": "clear",
  "notes": "Click orqali 50 000 so'm muvaffaqiyatli o'tkazilgan"
}

Agar tasvir to'lov cheki bo'lmasa yoki tushunarsiz rasm bo'lsa:
{
  "is_receipt": false,
  "is_successful": false,
  "amount_uzs": 0,
  "transaction_id": null,
  "recipient_card": null,
  "transaction_date": null,
  "payment_system": "unknown",
  "image_quality": "unreadable",
  "notes": "Tasvir to'lov cheki emas yoki mutlaqo o'qib bo'lmaydi"
}
"""


class ReceiptVerificationResult(BaseModel):
    """Structured result of payment receipt verification and comparison against order."""

    verdict: Literal["likely_match", "mismatch", "uncertain"] = Field(
        default="uncertain",
        description="likely_match (matches), mismatch (differs), uncertain (unclear)",
    )
    is_receipt: bool = Field(default=False)
    is_successful: bool = Field(default=False)
    amount_uzs: Decimal = Field(default=Decimal(0))
    transaction_id: str | None = Field(default=None)
    recipient_card: str | None = Field(default=None)
    transaction_date: str | None = Field(default=None)
    payment_system: str = Field(default="unknown")
    image_quality: str = Field(default="unknown")
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
        *,
        mime_type: str = "image/jpeg",
        expected_amount_uzs: Decimal | None = None,
        expected_card_number: str | None = None,
    ) -> ReceiptVerificationResult:
        """Analyze receipt image with Gemini Vision and compare against order expectations."""
        if not self.api_key or not image_bytes:
            logger.warning("GEMINI_API_KEY is not set or empty image; returning uncertain result.")
            return ReceiptVerificationResult(
                verdict="uncertain",
                is_receipt=False,
                is_successful=False,
                amount_uzs=Decimal(0),
                notes="Gemini API ulanmagan yoki rasm ma'lumoti bo'sh.",
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
                clean_amount_str = str(amount_raw).replace(" ", "").replace(",", "")
                amount = Decimal(clean_amount_str)
            except (InvalidOperation, ValueError):
                amount = Decimal(0)

            is_receipt = bool(data.get("is_receipt", False))
            is_successful = bool(data.get("is_successful", False))
            trans_id = data.get("transaction_id")
            recipient_card = data.get("recipient_card")
            trans_date = data.get("transaction_date")
            pay_system = str(data.get("payment_system", "unknown"))
            img_quality = str(data.get("image_quality", "unknown"))
            ai_notes = str(data.get("notes", ""))

            # Calculate verdict against order expectations
            verdict: Literal["likely_match", "mismatch", "uncertain"] = "uncertain"

            if not is_receipt or img_quality in ("unreadable", "poor"):
                verdict = "uncertain"
                ai_notes = (
                    ai_notes
                    or "Tasvir to'lov cheki emas yoki sifati o'qish uchun yetarli emas."
                )
            elif not is_successful:
                verdict = "mismatch"
                ai_notes = "Chekda to'lov muvaffaqiyatsiz yoki bekor qilingan deb ko'rsatilgan."
            elif expected_amount_uzs is not None and amount < expected_amount_uzs:
                verdict = "mismatch"
                ai_notes = (
                    f"To'langan summa ({amount:,.0f} so'm) xizmat narxidan kam."
                )
            else:
                # Check recipient card suffix if discernible
                if recipient_card and expected_card_number:
                    exp_last4 = expected_card_number.replace(" ", "")[-4:]
                    recip_clean = recipient_card.replace(" ", "")
                    if exp_last4 and exp_last4 not in recip_clean:
                        digits = "".join(ch for ch in recip_clean if ch.isdigit())
                        if len(digits) >= 4 and digits[-4:] != exp_last4:
                            verdict = "mismatch"
                            ai_notes = "Qabul qiluvchi karta raqami mos kelmadi."

                if verdict != "mismatch":
                    verdict = "likely_match"
                    ai_notes = (
                        ai_notes
                        or "Chek ma'lumotlari buyurtmaga mos (admin tasdig'i talab etiladi)."
                    )

            return ReceiptVerificationResult(
                verdict=verdict,
                is_receipt=is_receipt,
                is_successful=is_successful,
                amount_uzs=amount,
                transaction_id=str(trans_id) if trans_id else None,
                recipient_card=str(recipient_card) if recipient_card else None,
                transaction_date=str(trans_date) if trans_date else None,
                payment_system=pay_system,
                image_quality=img_quality,
                notes=ai_notes,
                raw_response=data,
            )

        except Exception as exc:
            logger.error("Failed to verify receipt with Gemini: %s", exc)
            return ReceiptVerificationResult(
                verdict="uncertain",
                is_receipt=False,
                is_successful=False,
                amount_uzs=Decimal(0),
                notes=f"AI tahlilida texnik xatolik: {exc}",
            )
