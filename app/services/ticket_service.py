from sqlalchemy.orm import Session
from app.models.ticket import Ticket
from app.models.payment import Payment
from app.core.qr import generate_qr
from app.services.payment_service import initiate_payment
import uuid


def create_payment_session(db: Session, user_id, data):
    payment_data = initiate_payment(data.fare, data.email)

    payment = Payment(
        tx_ref=payment_data["tx_ref"],
        user_id=user_id,
        route_id=data.route_id,
        amount=data.fare,
        status="pending"
    )

    db.add(payment)
    db.commit()

    return payment_data


def purchase_ticket(db: Session, user_id, data):
    route_id = data["route_id"]
    fare = data["fare"]

    ticket_id = str(uuid.uuid4())

    qr_path = generate_qr(
        data=f"ticket_id:{ticket_id}",
        filename=ticket_id
    )

    ticket = Ticket(
        id=ticket_id,
        user_id=user_id,
        route_id=route_id,
        fare=fare,
        qr_code=qr_path
    )

    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    return ticket