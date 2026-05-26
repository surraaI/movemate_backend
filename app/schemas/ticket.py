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


class TicketResponse(BaseModel):
    id: str
    user_id: str
    route_id: str
    fare: int
    qr_code: str

    class Config:
        from_attributes = True


class TicketQRResponse(BaseModel):
    ticket_id: str
    qr_code: str