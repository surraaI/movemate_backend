from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.schemas.ticket import TicketCreate
from app.services.ticket_service import create_payment_session, purchase_ticket
from app.services.payment_service import verify_payment
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
        return {"message": "Payment failed"}

    # ✅ mark as success BEFORE ticket creation (prevents duplicates)
    payment.status = "success"
    db.commit()

    # 🎟️ create ticket
    ticket = purchase_ticket(
        db,
        payment.user_id,
        {
            "route_id": payment.route_id,
            "fare": payment.amount
        }
    )

    return {
        "message": "Payment verified",
        "ticket": ticket
    }