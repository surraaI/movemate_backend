from sqlalchemy.orm import Session
from app.models.ticket import Ticket
from app.models.payment import Payment
from app.core.qr import generate_qr
from app.services.payment_service import initiate_payment
from app.services.event_service import EventService
from app.models.event import EventType
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
    db.flush()
    
    # Write payment_start event
    EventService.write_event(
        db,
        event_type=EventType.PAYMENT_START,
        user_id=user_id,
        route_id=data.route_id,
        metadata={"tx_ref": payment_data["tx_ref"], "amount": data.fare}
    )
    
    db.commit()

    return payment_data


def purchase_ticket(db: Session, user_id, data):
    route_id = data["route_id"]
    fare = data["fare"]
    origin_stop_id = data.get("origin_stop_id")  # new parameter

    ticket_id = str(uuid.uuid4())

    qr_path = generate_qr(
        data=f"ticket_id:{ticket_id}",
        filename=ticket_id
    )

    ticket = Ticket(
        id=ticket_id,
        user_id=user_id,
        route_id=route_id,
        origin_stop_id=origin_stop_id,
        fare=fare,
        qr_code=qr_path
    )

    db.add(ticket)
    db.flush()
    
    # Write ticket_created event
    EventService.write_event(
        db,
        event_type=EventType.TICKET_CREATED,
        user_id=user_id,
        route_id=route_id,
        metadata={"ticket_id": ticket_id, "origin_stop_id": origin_stop_id, "fare": fare}
    )
    
    db.refresh(ticket)
    db.commit()

    return ticket