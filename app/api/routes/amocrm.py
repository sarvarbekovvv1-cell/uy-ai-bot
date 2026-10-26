"""FastAPI endpoints for amoCRM webhooks."""

import hmac
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.config import Settings, get_settings
from app.integrations.amocrm.mapper import AmoCRMMapper
from app.integrations.amocrm.service import AmoCRMService
from app.logging import get_logger
from app.models.lead import LEAD_STAGES, Lead
from app.services.lead_service import LeadService
from app.services.rate_limiter import rate_limit

logger = get_logger(__name__)

router = APIRouter(prefix="/api/integrations/amocrm", tags=["amoCRM Integration"])

MAX_WEBHOOK_BODY_SIZE = 1_048_576  # 1 MB


def verify_webhook_secret(
    x_amocrm_secret: str | None = Header(default=None, alias="X-AmoCRM-Secret"),
    settings: Settings = Depends(get_settings),
) -> None:
    """Verify webhook authenticity using constant-time comparison on X-AmoCRM-Secret header.

    Query-parameter secrets are strictly rejected to prevent secret leakage in access logs.
    """
    if not settings.amocrm_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="amoCRM integration is disabled.",
        )

    expected = settings.amocrm_webhook_secret
    if not expected:
        if settings.app_env != "testing":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="AMOCRM_WEBHOOK_SECRET must be configured.",
            )
        return

    if not x_amocrm_secret or not hmac.compare_digest(x_amocrm_secret, expected):
        logger.warning("Rejected amoCRM webhook with missing or invalid X-AmoCRM-Secret header.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing webhook secret header.",
        )


async def enforce_max_body_size(request: Request) -> None:
    """Check request size to prevent memory exhaustion / DoS."""
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_WEBHOOK_BODY_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail="Payload size exceeds limit of 1MB.",
                )
        except ValueError:
            pass


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def handle_amocrm_webhook(
    request: Request,
    _: None = Depends(verify_webhook_secret),
    __: None = Depends(rate_limit("amocrm_webhook", max_requests=120, window_seconds=60)),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Receive and process amoCRM status and lead update webhooks.

    Guarantees:
    - Constant-time secret authentication via X-AmoCRM-Secret header.
    - 1MB max body limit.
    - Idempotent processing.
    - Loop prevention: updates applied without re-enqueuing outbox events.
    - Unknown external entities fail closed (ignored, no arbitrary internal leads created).
    - Unmapped statuses ignored without corrupting internal state machine.
    - Pipeline mismatch ignored.
    """
    await enforce_max_body_size(request)
    content_type = request.headers.get("content-type", "")

    # amoCRM sends either application/json or application/x-www-form-urlencoded
    parsed_leads: list[dict[str, Any]] = []

    if "application/json" in content_type:
        try:
            body = await request.json()
            if isinstance(body, dict):
                # Standard json format: {"leads": {"status": [{"id": 123, "status_id": 456}]}}
                leads_block = body.get("leads", {})
                if isinstance(leads_block, dict):
                    for key in ("status", "update", "add"):
                        items = leads_block.get(key, [])
                        if isinstance(items, list):
                            parsed_leads.extend(items)
        except Exception as e:
            logger.warning("Failed to parse JSON webhook: %s", e)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed JSON"
            ) from e
    else:
        # Form URL-encoded parser
        try:
            form = await request.form()
            # Form keys can be: leads[status][0][id], leads[status][0][status_id]
            extracted: dict[str, dict[str, Any]] = {}
            for k, v in form.items():
                if "leads" in k and "[" in k:
                    # Quick extraction of index and field
                    parts = k.replace("]", "").split("[")
                    if len(parts) >= 4:
                        _section, _action, idx, field = parts[0], parts[1], parts[2], parts[3]
                        key_id = f"{idx}"
                        if key_id not in extracted:
                            extracted[key_id] = {}
                        extracted[key_id][field] = v
            parsed_leads.extend(extracted.values())
        except Exception as e:
            logger.warning("Failed to parse form webhook: %s", e)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed form data"
            ) from e

    if not parsed_leads:
        return {"status": "ignored", "reason": "no_leads_found"}

    mapper = AmoCRMMapper(settings)
    lead_service = LeadService()
    crm_service = AmoCRMService(settings=settings, provider=None, mapper=mapper)  # type: ignore[arg-type]

    processed_count = 0

    for item in parsed_leads:
        ext_lead_id = str(item.get("id", ""))
        status_id_val = item.get("status_id")

        if not ext_lead_id or status_id_val is None:
            continue

        # Check pipeline if configured
        item_pipeline = item.get("pipeline_id")
        if (
            settings.amocrm_pipeline_id is not None
            and item_pipeline is not None
            and str(item_pipeline) != str(settings.amocrm_pipeline_id)
        ):
            logger.info(
                "Ignoring webhook item with mismatched pipeline_id=%s (expected %s)",
                item_pipeline,
                settings.amocrm_pipeline_id,
            )
            continue

        try:
            status_id = int(status_id_val)
        except (ValueError, TypeError):
            continue

        # 1. Lookup local lead ID by external amoCRM ID
        local_lead_id = await crm_service.get_local_lead_id_by_external_id(session, ext_lead_id)
        if not local_lead_id:
            logger.info("Ignoring webhook for unknown external amoCRM lead %s", ext_lead_id)
            continue

        # 2. Resolve target stage from external status_id
        target_stage = mapper.resolve_stage_from_status_id(status_id)
        if not target_stage or target_stage not in LEAD_STAGES:
            logger.info(
                "Ignoring unmapped external status_id=%d for lead id=%d",
                status_id,
                local_lead_id,
            )
            continue

        # 3. Load local lead and verify if stage transition is needed
        lead = await session.get(Lead, local_lead_id)
        if not lead or lead.stage == target_stage:
            continue

        # 4. Check state machine validity
        try:
            lead_service.validate_stage_transition(lead.stage, target_stage)
        except Exception as trans_err:
            logger.warning(
                "Disallowed transition from %s to %s for lead id=%d via webhook: %s",
                lead.stage,
                target_stage,
                local_lead_id,
                trans_err,
            )
            continue

        # 5. Apply stage transition with LOOP PREVENTION (enqueue_crm=False)
        broker_id = lead.broker_user_id or 1  # Fallback to system actor
        try:
            await lead_service.update_stage(
                session,
                lead_id=local_lead_id,
                broker_user_id=broker_id,
                target_stage=target_stage,
                close_reason="other" if target_stage == "lost" else None,
                enqueue_crm=False,  # CRITICAL: loop prevention
            )
            await session.commit()
            processed_count += 1
            logger.info(
                "Successfully synchronized amoCRM -> UyAI stage %s for lead id=%d",
                target_stage,
                local_lead_id,
            )
        except Exception as update_err:
            logger.error(
                "Failed to apply webhook stage update to lead id=%d: %s",
                local_lead_id,
                update_err,
            )

    return {"status": "ok", "processed": processed_count}
