from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.ticket_service import process_chapa_payment_callback

router = APIRouter(prefix="/api/payments/chapa", tags=["payments"])


@router.api_route("/callback", methods=["GET", "POST"])
def chapa_callback(
    trx_ref: str,
    db: Session = Depends(get_db),
):
    return process_chapa_payment_callback(db, trx_ref)