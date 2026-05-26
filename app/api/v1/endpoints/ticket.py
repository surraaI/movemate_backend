from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.ticket import Ticket
from app.models.user import User
from app.schemas.ticket import (
    TicketCreate,
    TicketResponse,
    TicketScanRequest,
    TicketScanResponse,
    TicketValidateRequest,
    TicketValidateResponse,
)
from app.services.ticket_service import (
    create_payment_session,
    get_ticket_qr_path,
    get_user_ticket,
    get_user_tickets,
    process_chapa_payment_callback,
    validate_ticket,
)

router = APIRouter()


@router.api_route("/callback", methods=["GET", "POST"])
def chapa_callback(
    trx_ref: str,
    db: Session = Depends(get_db)
):
    return process_chapa_payment_callback(db, trx_ref)


@router.get("/me", response_model=list[TicketResponse])
def get_my_tickets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_user_tickets(db, current_user.user_id)


@router.get("/{ticket_id}", response_model=TicketResponse)
def get_ticket(
    ticket_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_user_ticket(db, current_user.user_id, ticket_id)


@router.get("/{ticket_id}/qr")
def get_ticket_qr(
    ticket_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    qr_path = get_ticket_qr_path(db, current_user.user_id, ticket_id)
    if not qr_path:
        raise HTTPException(status_code=404, detail="QR code not found")
    return FileResponse(qr_path, media_type="image/png", filename=f"{ticket_id}.png")


@router.post("/start-payment")
def start_payment(
    data: TicketCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return create_payment_session(db, current_user.user_id, data)


@router.post("/validate", response_model=TicketValidateResponse)
def validate_ticket_qr(
    payload: TicketValidateRequest,
    current_user: User = Depends(require_roles(UserRole.DRIVER)),
    db: Session = Depends(get_db),
) -> TicketValidateResponse:
    ticket = validate_ticket(
        db,
        current_user.user_id,
        {
            "ticket_id": payload.ticket_id,
            "qr_code": payload.qr_code,
            "bus_id": payload.bus_id,
        },
    )
    return TicketValidateResponse(
        valid=True,
        message="Ticket validated successfully",
        ticket_id=ticket.id,
        route_id=ticket.route_id,
        bus_id=payload.bus_id,
        validated_at=ticket.validated_at,
        expires_at=ticket.expires_at,
    )


@router.post("/scan", response_model=TicketScanResponse)
def scan_ticket(
    payload: TicketScanRequest,
    db: Session = Depends(get_db),
) -> TicketScanResponse:
    """Record a ticket scan at a stop and persist the demand signal for rerouting."""

    ticket: Ticket | None = None
    if payload.ticket_id is not None:
        ticket = db.query(Ticket).filter(Ticket.id == payload.ticket_id).first()
    elif payload.qr_code is not None:
        ticket = db.query(Ticket).filter(Ticket.qr_code == payload.qr_code).first()

    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    event = Ticket.scan(
        db=db,
        ticket=ticket,
        bus_id=payload.bus_id,
        stop_id=payload.stop_id,
        direction=payload.direction,
    )
    return TicketScanResponse(acknowledged=True, event_id=event.id)