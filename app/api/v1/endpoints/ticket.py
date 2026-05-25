from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.schemas.ticket import TicketCreate, TicketResponse
from app.services.ticket_service import (
    create_payment_session,
    get_ticket_qr_path,
    get_user_ticket,
    get_user_tickets,
    purchase_ticket,
)
from app.services.payment_service import verify_payment
from app.services.event_service import EventService
from app.models.event import EventType
from app.db.session import get_db
from app.models.payment import Payment
from app.core.deps import get_current_user
from app.models.user import User

router = APIRouter()


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