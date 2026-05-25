from pydantic import BaseModel


class TicketCreate(BaseModel):
    route_id: str
    fare: int
    email: str


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