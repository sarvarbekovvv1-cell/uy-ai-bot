"""Admin lead management, pipeline, stage transitions, and notes routes."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db_session
from app.api.schemas.admin import (
    AdminLeadDetail,
    AdminLeadEventItem,
    AdminLeadItem,
    AdminLeadNoteItem,
    LeadAssignRequest,
    LeadNoteCreateRequest,
    LeadStageUpdateRequest,
    PaginatedResponse,
)
from app.logging import get_logger
from app.models.crm_sync import CRMEntityLink
from app.models.lead import Lead, LeadEvent, LeadNote
from app.models.user import User
from app.services.admin_auth_service import AdminAuthService
from app.services.admin_rbac import (
    PERM_LEADS_ADD_NOTE,
    PERM_LEADS_ASSIGN,
    PERM_LEADS_CHANGE_STAGE,
    PERM_LEADS_VIEW,
    has_permission,
    require_permission,
    verify_csrf_token,
)
from app.services.lead_service import LeadService

logger = get_logger(__name__)

router = APIRouter(prefix="/leads", tags=["Admin Leads"])


@router.get("", response_model=PaginatedResponse)
async def list_leads(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    stage: str | None = None,
    broker_id: int | None = None,
    search: str | None = Query(default=None, max_length=100),
    session: AsyncSession = Depends(get_db_session),
    staff_user: User = Depends(require_permission(PERM_LEADS_VIEW)),
) -> PaginatedResponse:
    """Return paginated leads with horizontal broker isolation."""
    stmt = (
        select(Lead)
        .options(
            selectinload(Lead.customer),
            selectinload(Lead.property),
            selectinload(Lead.broker),
        )
    )

    # Horizontal isolation: standard brokers only see their assigned leads
    can_manage_all = has_permission(staff_user, PERM_LEADS_ASSIGN)
    if not can_manage_all:
        stmt = stmt.where(Lead.broker_user_id == staff_user.id)
    elif broker_id:
        stmt = stmt.where(Lead.broker_user_id == broker_id)

    if stage:
        stmt = stmt.where(Lead.stage == stage)

    if search:
        search_pattern = f"%{search.strip()}%"
        stmt = stmt.join(Lead.customer).where(
            (User.first_name.ilike(search_pattern))
            | (User.last_name.ilike(search_pattern))
            | (User.phone.ilike(search_pattern))
        )

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one() or 0

    stmt = stmt.order_by(Lead.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(stmt)
    leads = result.scalars().all()

    items = []
    for ld in leads:
        customer_name = (
            f"{ld.customer.first_name or ''} {ld.customer.last_name or ''}".strip()
            or f"Customer #{ld.customer_user_id}"
        )
        broker_name = (
            f"{ld.broker.first_name or ''} {ld.broker.last_name or ''}".strip()
            if ld.broker
            else None
        )
        prop_title = ld.property.title if ld.property else None

        items.append(
            AdminLeadItem(
                id=ld.id,
                customer_id=ld.customer_user_id,
                customer_name=customer_name,
                customer_phone=ld.customer.phone,
                property_id=ld.property_id,
                property_title=prop_title,
                stage=ld.stage,
                source=ld.source,
                broker_id=ld.broker_user_id,
                broker_name=broker_name,
                created_at=ld.created_at,
                updated_at=ld.updated_at,
            )
        )

    total_pages = (total + page_size - 1) // page_size
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{lead_id}", response_model=AdminLeadDetail)
async def get_lead_detail(
    lead_id: int,
    session: AsyncSession = Depends(get_db_session),
    staff_user: User = Depends(require_permission(PERM_LEADS_VIEW)),
) -> AdminLeadDetail:
    """Fetch lead detail with timeline history, notes, and amoCRM mapping."""
    stmt = (
        select(Lead)
        .options(
            selectinload(Lead.customer),
            selectinload(Lead.property),
            selectinload(Lead.broker),
        )
        .where(Lead.id == lead_id)
    )
    result = await session.execute(stmt)
    ld = result.scalar_one_or_none()

    if not ld:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found.")

    # Horizontal authorization check
    can_manage_all = has_permission(staff_user, PERM_LEADS_ASSIGN)
    if not can_manage_all and ld.broker_user_id != staff_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: You are not assigned to this lead.",
        )

    # Fetch notes directly to ensure complete fresh collection
    notes_stmt = (
        select(LeadNote)
        .options(selectinload(LeadNote.author))
        .where(LeadNote.lead_id == ld.id)
        .order_by(LeadNote.created_at.asc())
    )
    notes_res = await session.execute(notes_stmt)
    lead_notes = notes_res.scalars().all()

    # Fetch timeline events directly
    events_stmt = (
        select(LeadEvent)
        .options(selectinload(LeadEvent.actor))
        .where(LeadEvent.lead_id == ld.id)
        .order_by(LeadEvent.created_at.asc())
    )
    events_res = await session.execute(events_stmt)
    lead_events = events_res.scalars().all()

    # Fetch amoCRM entity link if present
    link_stmt = select(CRMEntityLink.external_entity_id).where(
        CRMEntityLink.provider == "amocrm",
        CRMEntityLink.local_entity_type == "lead",
        CRMEntityLink.local_entity_id == ld.id,
    )
    amo_lead_id = (await session.execute(link_stmt)).scalar_one_or_none()

    customer_name = (
        f"{ld.customer.first_name or ''} {ld.customer.last_name or ''}".strip()
        or f"Customer #{ld.customer_user_id}"
    )
    broker_name = (
        f"{ld.broker.first_name or ''} {ld.broker.last_name or ''}".strip()
        if ld.broker
        else None
    )

    notes = []
    for n in lead_notes:
        a_name = "System"
        if n.author:
            a_name = f"{n.author.first_name or ''} {n.author.last_name or ''}".strip() or "Staff"
        notes.append(
            AdminLeadNoteItem(
                id=n.id,
                author_name=a_name,
                note_text=n.text,
                created_at=n.created_at,
            )
        )

    events = []
    for e in lead_events:
        act_name = "System"
        if e.actor:
            act_name = f"{e.actor.first_name or ''} {e.actor.last_name or ''}".strip() or "Staff"
        events.append(
            AdminLeadEventItem(
                id=e.id,
                event_type=e.event_type,
                from_stage=e.old_value,
                to_stage=e.new_value,
                actor_name=act_name,
                created_at=e.created_at,
            )
        )

    return AdminLeadDetail(
        id=ld.id,
        customer_id=ld.customer_user_id,
        customer_name=customer_name,
        customer_phone=ld.customer.phone,
        property_id=ld.property_id,
        property_title=ld.property.title if ld.property else None,
        stage=ld.stage,
        source=ld.source,
        broker_id=ld.broker_user_id,
        broker_name=broker_name,
        created_at=ld.created_at,
        updated_at=ld.updated_at,
        amo_crm_lead_id=amo_lead_id,
        notes=notes,
        events=events,
    )


@router.patch("/{lead_id}/stage", status_code=status.HTTP_200_OK)
async def update_lead_stage(
    lead_id: int,
    request: Request,
    body: LeadStageUpdateRequest,
    session: AsyncSession = Depends(get_db_session),
    staff_user: User = Depends(require_permission(PERM_LEADS_CHANGE_STAGE)),
    _: None = Depends(verify_csrf_token),
) -> dict[str, Any]:
    """Transition lead stage using LeadService state machine rules."""
    lead = await session.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found.")

    # Horizontal check
    can_manage_all = has_permission(staff_user, PERM_LEADS_ASSIGN)
    if not can_manage_all and lead.broker_user_id != staff_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: You cannot modify leads assigned to another broker.",
        )

    old_stage = lead.stage
    lead_service = LeadService()
    try:
        updated_lead = await lead_service.update_stage(
            session,
            lead_id=lead_id,
            broker_user_id=staff_user.id,
            target_stage=body.target_stage,
            close_reason=body.close_reason,
        )
    except Exception as e:
        logger.warning("Stage transition failed for lead id=%d: %s", lead_id, e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stage transition rejected: {e}",
        ) from e

    client_ip = request.client.host if request.client else None
    await AdminAuthService.record_audit_event(
        session,
        actor_user_id=staff_user.id,
        action="lead.stage_change",
        entity_type="lead",
        entity_id=lead_id,
        metadata={"from_stage": old_stage, "to_stage": body.target_stage},
        ip_address=client_ip,
    )

    await session.commit()
    return {"status": "ok", "lead_id": lead_id, "stage": updated_lead.stage}


@router.patch("/{lead_id}/assign", status_code=status.HTTP_200_OK)
@router.post("/{lead_id}/assign", status_code=status.HTTP_200_OK)
async def assign_lead_broker(
    lead_id: int,
    request: Request,
    body: LeadAssignRequest,
    session: AsyncSession = Depends(get_db_session),
    staff_user: User = Depends(require_permission(PERM_LEADS_ASSIGN)),
    _: None = Depends(verify_csrf_token),
) -> dict[str, Any]:
    """Assign or reassign lead to a broker."""
    lead = await session.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found.")

    target_broker = await session.get(User, body.broker_user_id)
    if not target_broker or not target_broker.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid broker user.")

    old_broker_id = lead.broker_user_id
    lead_service = LeadService()
    try:
        updated_lead = await lead_service.assign_broker(
            session,
            lead_id=lead_id,
            broker_user_id=body.broker_user_id,
            assigned_by_user_id=staff_user.id,
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    client_ip = request.client.host if request.client else None
    await AdminAuthService.record_audit_event(
        session,
        actor_user_id=staff_user.id,
        action="lead.assign",
        entity_type="lead",
        entity_id=lead_id,
        metadata={"previous_broker_id": old_broker_id, "new_broker_id": body.broker_user_id},
        ip_address=client_ip,
    )

    await session.commit()
    return {
        "status": "ok",
        "lead_id": lead_id,
        "broker_user_id": updated_lead.broker_user_id,
        "broker_id": updated_lead.broker_user_id,
    }


@router.post("/{lead_id}/notes", status_code=status.HTTP_201_CREATED)
async def add_lead_note(
    lead_id: int,
    request: Request,
    body: LeadNoteCreateRequest,
    session: AsyncSession = Depends(get_db_session),
    staff_user: User = Depends(require_permission(PERM_LEADS_ADD_NOTE)),
    _: None = Depends(verify_csrf_token),
) -> dict[str, Any]:
    """Attach internal staff note to lead."""
    lead = await session.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found.")

    can_manage_all = has_permission(staff_user, PERM_LEADS_ASSIGN)
    if not can_manage_all and lead.broker_user_id != staff_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: You cannot add notes to leads assigned to another broker.",
        )

    lead_service = LeadService()
    note = await lead_service.add_note(
        session,
        lead_id=lead_id,
        author_user_id=staff_user.id,
        text=body.note_text.strip(),
    )

    client_ip = request.client.host if request.client else None
    await AdminAuthService.record_audit_event(
        session,
        actor_user_id=staff_user.id,
        action="lead.add_note",
        entity_type="lead",
        entity_id=lead_id,
        metadata={"note_id": note.id},
        ip_address=client_ip,
    )

    await session.commit()
    return {"status": "ok", "note_id": note.id}
