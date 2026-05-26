from datetime import datetime

from pydantic import BaseModel


class TicketCreate(BaseModel):
    route_id: str
    fare: int
    email: str


class TicketScanRequest(BaseModel):
    ticket_id: str | None = None
    qr_code: str | None = None
    bus_id: str
    stop_id: str
    direction: str


class TicketScanResponse(BaseModel):
    acknowledged: bool
    event_id: str


class TicketValidateRequest(BaseModel):
    ticket_id: str | None = None
    qr_code: str | None = None
    bus_id: str


class TicketValidateResponse(BaseModel):
    valid: bool
    message: str
    ticket_id: str
    route_id: str
    bus_id: str
    validated_at: datetime
    expires_at: datetime


class TicketResponse(BaseModel):
    id: str
    user_id: str
    route_id: str
    fare: int
    qr_code: str | None = None
    created_at: datetime
    validated_at: datetime | None = None
    expires_at: datetime

    class Config:
        from_attributes = True


class TicketQRResponse(BaseModel):
    ticket_id: str
    qr_code: str