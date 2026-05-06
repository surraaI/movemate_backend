import requests
import uuid
from app.core.config import settings

def initiate_payment(amount: int, email: str):
    tx_ref = f"tx-{uuid.uuid4()}"

    payload = {
        "amount": str(amount),
        "currency": "ETB",
        "email": email,
        "tx_ref": tx_ref,
        "callback_url": settings.CHAPA_CALLBACK_URL,
        "return_url": settings.CHAPA_RETURN_URL
    }

    headers = {
        "Authorization": f"Bearer {settings.CHAPA_SECRET_KEY}",
        "Content-Type": "application/json"
    }

    response = requests.post(
        f"{settings.CHAPA_BASE_URL}/transaction/initialize",
        json=payload,
        headers=headers
    )

    data = response.json()

    return {
        "tx_ref": tx_ref,
        "checkout_url": data["data"]["checkout_url"]
    }


def verify_payment(tx_ref: str):
    url = f"{settings.CHAPA_BASE_URL}/transaction/verify/{tx_ref}"

    headers = {
        "Authorization": f"Bearer {settings.CHAPA_SECRET_KEY}"
    }

    response = requests.get(url, headers=headers)

    return response.json()