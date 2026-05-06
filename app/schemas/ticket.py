from pydantic import BaseModel


class TicketCreate(BaseModel):
    route_id: str
    fare: int
    email: str


class TicketResponse(BaseModel):
    id: str
    route_id: str
    fare: int
    qr_code: str

    class Config:
        from_attributes = True