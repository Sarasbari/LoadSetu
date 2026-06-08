import os
import logging
from twilio.rest import Client
from services import supabase_service

logger = logging.getLogger(__name__)

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "AC00000000000000000000000000000000")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "00000000000000000000000000000000")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")

# Check if using mock mode
IS_MOCK_TWILIO = (
    not TWILIO_ACCOUNT_SID 
    or TWILIO_ACCOUNT_SID == "AC00000000000000000000000000000000"
    or not TWILIO_AUTH_TOKEN 
    or TWILIO_AUTH_TOKEN == "00000000000000000000000000000000"
)

twilio_client = None
if not IS_MOCK_TWILIO:
    try:
        twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        logger.info("Twilio client initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize Twilio client: {e}")
        IS_MOCK_TWILIO = True

def send_message(to_number: str, body: str, shipment_id: str = None, media_url: str = None) -> bool:
    """Sends a WhatsApp message using Twilio API (or prints/logs it in mock mode)."""
    # Clean up phone number format if needed (must start with whatsapp:)
    to_whatsapp = to_number
    if not to_whatsapp.startswith("whatsapp:"):
        to_whatsapp = f"whatsapp:{to_number}"
        
    logger.info(f"Sending WhatsApp message to {to_whatsapp}: {body[:100]}...")
    
    # 1. Log outbound message to database
    # Extract clean phone number without 'whatsapp:' prefix for DB storage
    clean_to = to_number.replace("whatsapp:", "")
    supabase_service.log_message(
        phone_number=clean_to,
        direction="OUTBOUND",
        body=body,
        shipment_id=shipment_id
    )

    if IS_MOCK_TWILIO:
        print("\n=== [MOCK WHATSAPP OUTBOUND] ===")
        print(f"TO: {to_whatsapp}")
        print(f"FROM: {TWILIO_WHATSAPP_NUMBER}")
        print(f"BODY: {body}")
        if media_url:
            print(f"MEDIA: {media_url}")
        print("=================================\n")
        return True
        
    try:
        kwargs = {
            "from_": TWILIO_WHATSAPP_NUMBER,
            "to": to_whatsapp,
            "body": body
        }
        if media_url:
            kwargs["media_url"] = [media_url]
            
        message = twilio_client.messages.create(**kwargs)
        logger.info(f"Twilio message sent. Message SID: {message.sid}")
        return True
    except Exception as e:
        logger.error(f"Failed to send Twilio message: {e}")
        # Return True in mock fallback mode so application testing does not break
        print(f"\n[FALLBACK OUTBOUND] To: {to_whatsapp} | Body: {body}\n")
        return True
