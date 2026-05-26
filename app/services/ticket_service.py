from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.ticket import Ticket
from app.models.payment import Payment
from app.core.qr import generate_qr
from app.services.payment_service import initiate_payment
from app.services.event_service import EventService
from app.models.event import EventType
import os
import uuid
from datetime import UTC, datetime, timedelta


TICKET_VALIDITY_HOURS = 24


def _get_ticket_expiration(ticket: Ticket) -> datetime:
    created_at = ticket.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    return created_at + timedelta(hours=TICKET_VALIDITY_HOURS)


def _ensure_ticket_is_active(ticket: Ticket) -> None:
    if ticket.qr_code is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ticket already used")
    if datetime.now(UTC) >= _get_ticket_expiration(ticket):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Ticket expired")


def _get_ticket_by_reference(db: Session, ticket_id: str | None = None, qr_code: str | None = None) -> Ticket:
    if ticket_id is None and qr_code is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ticket_id or qr_code is required")

    query = db.query(Ticket)
    if ticket_id is not None:
        query = query.filter(Ticket.id == ticket_id)
    elif qr_code is not None:
        query = query.filter(Ticket.qr_code == qr_code)

    ticket = query.first()
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return ticket


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
    generate_qr_code = data.get("generate_qr_code", False)

    ticket_id = str(uuid.uuid4())

    qr_path = None
    if generate_qr_code:
        qr_path = generate_qr(
            data=f"ticket_id:{ticket_id}",
            filename=ticket_id,
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


def validate_ticket(db: Session, validator_user_id: str, data: dict) -> Ticket:
    ticket = _get_ticket_by_reference(
        db,
        ticket_id=data.get("ticket_id"),
        qr_code=data.get("qr_code"),
    )

    _ensure_ticket_is_active(ticket)

    validated_at = datetime.now(UTC)
    ticket.validated_at = validated_at
    qr_path = ticket.qr_code
    ticket.qr_code = None
    db.add(ticket)
    db.flush()

    if qr_path and os.path.exists(os.path.abspath(qr_path)):
        try:
            os.remove(os.path.abspath(qr_path))
        except OSError:
            pass

    EventService.write_event(
        db,
        event_type=getattr(EventType, "TICKET_VALIDATED", "ticket_validated"),
        user_id=ticket.user_id,
        route_id=ticket.route_id,
        metadata={
            "ticket_id": ticket.id,
            "bus_id": data["bus_id"],
            "validated_by": validator_user_id,
            "validated_at": validated_at.isoformat(),
            "expires_at": _get_ticket_expiration(ticket).isoformat(),
        },
        occurred_at=validated_at,
    )
    db.commit()
    db.refresh(ticket)
    return ticket


def get_user_tickets(db: Session, user_id: str):
    return (
        db.query(Ticket)
        .filter(Ticket.user_id == user_id)
        .order_by(Ticket.created_at.desc())
        .all()
    )


def get_user_ticket(db: Session, user_id: str, ticket_id: str):
    ticket = (
        db.query(Ticket)
        .filter(Ticket.id == ticket_id, Ticket.user_id == user_id)
        .first()
    )
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return ticket


def get_ticket_qr_path(db: Session, user_id: str, ticket_id: str):
    ticket = get_user_ticket(db, user_id, ticket_id)
    if not ticket.qr_code:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="QR code not available")
    _ensure_ticket_is_active(ticket)
    qr_path = os.path.abspath(ticket.qr_code)
    if not os.path.exists(qr_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="QR code file not found")
    return qr_path