import logging
import os
from services import twilio_service, supabase_service

logger = logging.getLogger(__name__)

def send_whatsapp(to_phone: str, body: str, shipment_id: str = None, media_url: str = None) -> bool:
    """Sends a WhatsApp message via Twilio and tracks the outcome in the notification_attempts table."""
    clean_phone = to_phone.replace("whatsapp:", "").strip()
    
    # 1. Create a PENDING notification attempt log
    attempt = supabase_service.create_notification_attempt(
        to_phone=clean_phone,
        shipment_id=shipment_id,
        body=body,
        media_url=media_url,
        status="PENDING"
    )
    attempt_id = attempt["id"] if attempt else None
    
    try:
        # 2. Call the twilio_service to send
        success = twilio_service.send_message(
            to_number=to_phone,
            body=body,
            shipment_id=shipment_id,
            media_url=media_url
        )
        
        status = "SENT"
        if supabase_service.is_mock_active() or twilio_service.IS_MOCK_TWILIO:
            status = "SENT_MOCK"
            
        if attempt_id:
            supabase_service.update_notification_attempt(
                attempt_id=attempt_id,
                status=status
            )
        return success
        
    except Exception as e:
        logger.error(f"Failed to send notification via notification_service: {e}")
        if attempt_id:
            supabase_service.update_notification_attempt(
                attempt_id=attempt_id,
                status="FAILED",
                error_message=str(e)
            )
        return False

def retry_notification(attempt_id: str) -> bool:
    """Retries a previously failed notification attempt by ID."""
    attempt = supabase_service.get_notification_attempt_by_id(attempt_id)
    if not attempt:
        logger.error(f"Notification attempt {attempt_id} not found for retry.")
        return False
        
    if attempt["status"] not in ["FAILED", "PENDING"]:
        logger.info(f"Attempt {attempt_id} already sent successfully. Skipping retry.")
        return True
        
    to_phone = attempt["to_phone"]
    if not to_phone.startswith("whatsapp:"):
        to_phone = f"whatsapp:{to_phone}"
        
    try:
        success = twilio_service.send_message(
            to_number=to_phone,
            body=attempt["body"],
            shipment_id=attempt.get("shipment_id"),
            media_url=attempt.get("media_url")
        )
        
        status = "SENT"
        if supabase_service.is_mock_active() or twilio_service.IS_MOCK_TWILIO:
            status = "SENT_MOCK"
            
        supabase_service.update_notification_attempt(
            attempt_id=attempt_id,
            status=status,
            error_message=""  # Clear error
        )
        return success
    except Exception as e:
        logger.error(f"Failed to retry notification {attempt_id}: {e}")
        supabase_service.update_notification_attempt(
            attempt_id=attempt_id,
            status="FAILED",
            error_message=str(e)
        )
        return False
