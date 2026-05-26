from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models.ticket import Ticket
from app.schemas.ticket import TicketCreate, TicketScanRequest, TicketScanResponse
from app.services.ticket_service import create_payment_session, purchase_ticket
from app.services.payment_service import verify_payment
from app.services.event_service import EventService
from app.models.event import EventType
from app.db.session import get_db
from app.models.payment import Payment
from app.core.deps import get_current_user
from app.models.user import User

router = APIRouter()


@router.post("/start-payment")
def start_payment(
    data: TicketCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return create_payment_session(db, current_user.user_id, data)


@router.post("/callback")
def chapa_callback(
    trx_ref: str,
    db: Session = Depends(get_db)
):
    payment = db.query(Payment).filter(Payment.tx_ref == trx_ref).first()

    if not payment:
        return {"error": "Payment not found"}

    # 🔴 Prevent duplicate processing
    if payment.status == "success":
        return {"message": "Already processed"}

    # ✅ ALWAYS verify with provider
    verification = verify_payment(trx_ref)

    if verification["status"] != "success":
        payment.status = "failed"
        db.commit()
        
        # Write payment_failed event
        EventService.write_event(
            db,
            event_type=EventType.PAYMENT_FAILED,
            user_id=payment.user_id,
            route_id=payment.route_id,
            metadata={"tx_ref": trx_ref, "amount": payment.amount}
        )
        db.commit()
        
        return {"message": "Payment failed"}

    # ✅ mark as success BEFORE ticket creation (prevents duplicates)
    payment.status = "success"
    db.commit()

    # Write payment_success event
    EventService.write_event(
        db,
        event_type=EventType.PAYMENT_SUCCESS,
        user_id=payment.user_id,
        route_id=payment.route_id,
        metadata={"tx_ref": trx_ref, "amount": payment.amount}
    )
    db.commit()

    # 🎟️ create ticket (include origin_stop_id if available)
    ticket = purchase_ticket(
        db,
        payment.user_id,
        {
            "route_id": payment.route_id,
            "fare": payment.amount,
            "origin_stop_id": None  # Can be enhanced later with stop data from payment
        }
    )

    return {
        "message": "Payment verified",
        "ticket": ticket
    }


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