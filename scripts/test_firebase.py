import logging
from app.integration.firebase import send_push
from app.core.config import settings

# Configure logging to see the output
logging.basicConfig(level=logging.INFO)

def test_firebase_push():
    print(f"Testing Firebase with Project ID: {settings.FIREBASE_PROJECT_ID}", flush=True)
    print(f"Service Account Path: {settings.FIREBASE_SERVICE_ACCOUNT}", flush=True)
    
    # Replace with a real device token if you want to test actual delivery
    dummy_token = "dummy_fcm_token"
    
    try:
        result = send_push(
            token=dummy_token,
            title="Test Notification",
            message="This is a test notification from MoveMate backend!",
            data={"test_id": "123"}
        )
        print("Result:", result, flush=True)
    except Exception as e:
        print("Failed to send push:", e, flush=True)

if __name__ == "__main__":
    test_firebase_push()
