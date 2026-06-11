import os
import logging
import re
from fastapi import APIRouter, Form, Request, Response, HTTPException
from twilio.request_validator import RequestValidator

from services import supabase_service, notification_service, booking_service, onboarding_service, status_service
from utils import conversation_state
from agents import intake_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["webhook"])

# Global in-memory set to store processed MessageSids for idempotency
PROCESSED_MESSAGE_SIDS = set()

# Initialize Twilio Request Validator
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
validator = RequestValidator(TWILIO_AUTH_TOKEN)

def validate_signature(request: Request, params: dict, signature: str) -> bool:
    """Validates the Twilio request signature (bypassed in development mode)."""
    app_env = os.getenv("APP_ENV", "development")
    if app_env == "development":
        logger.info("Bypassing Twilio signature validation in development mode.")
        return True
        
    if not signature or not TWILIO_AUTH_TOKEN:
        logger.warning("Twilio signature validation failed: signature or token missing.")
        return False
        
    # Get request URL (must match the registered Twilio webhook URL exactly)
    url = os.getenv("WEBHOOK_BASE_URL", "") + "/webhook"
    
    # Validate
    is_valid = validator.validate(url, params, signature)
    if not is_valid:
        logger.warning(f"Invalid Twilio signature. URL: {url}, Params: {params}, Signature: {signature}")
    return is_valid

@router.post("")
async def receive_webhook(
    request: Request,
    From: str = Form(...),
    Body: str = Form(...),
    MessageSid: str = Form(...),
    NumMedia: int = Form(0),
    MediaUrl0: str = Form(None),
    MediaContentType0: str = Form(None)
):
    """POST /webhook - Main Twilio incoming message handler"""
    logger.info(f"Received webhook: From={From}, MessageSid={MessageSid}, Body='{Body[:50]}', NumMedia={NumMedia}")
    
    # 1. Twilio Idempotency Check
    if MessageSid:
        if MessageSid in PROCESSED_MESSAGE_SIDS:
            logger.info(f"Duplicate MessageSid (in-memory): {MessageSid}. Ignoring.")
            return Response(content="<Response></Response>", media_type="application/xml")
            
        if not supabase_service.is_mock_active() and supabase_service.is_message_processed(MessageSid):
            logger.info(f"Duplicate MessageSid (DB): {MessageSid}. Ignoring.")
            PROCESSED_MESSAGE_SIDS.add(MessageSid)
            return Response(content="<Response></Response>", media_type="application/xml")
            
        PROCESSED_MESSAGE_SIDS.add(MessageSid)
        if len(PROCESSED_MESSAGE_SIDS) > 5000:
            PROCESSED_MESSAGE_SIDS.clear()
            
    # 2. Twilio Signature Validation
    form_data = await request.form()
    params = dict(form_data)
    signature = request.headers.get("X-Twilio-Signature", "")
    
    if not validate_signature(request, params, signature):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")
        
    # 3. Extract and validate phone number format
    clean_phone = From.replace("whatsapp:", "").strip()
    if not re.match(r'^\+?[1-9]\d{1,14}$', clean_phone):
        logger.warning(f"Rejected request from invalid phone format: {clean_phone}")
        return Response(content="<Response></Response>", media_type="application/xml")
        
    # 4. Log inbound message to database
    supabase_service.log_message(
        phone_number=clean_phone,
        direction="INBOUND",
        body=Body,
        message_sid=MessageSid
    )
    
    # 5. Determine User Role (Operator, Driver, or New Operator)
    operator = supabase_service.get_operator_by_phone(clean_phone)
    truck_as_driver = supabase_service.get_truck_by_driver_phone(clean_phone)
    
    # 6. Check for WhatsApp commands (help, status, cancel, driver details, etc.)
    command_handled = booking_service.handle_whatsapp_command(clean_phone, Body, operator, truck_as_driver)
    if command_handled:
        return Response(content="<Response></Response>", media_type="application/xml")
        
    # 7. Load/Update Conversation State
    state = conversation_state.get_state(clean_phone)
    
    # Onboarding intercept
    if not truck_as_driver:
        if not operator:
            logger.info(f"New number detected: {clean_phone}. Creating pending operator for onboarding.")
            operator = supabase_service.create_operator(
                phone=clean_phone,
                name="New Operator",
                business_name=None,
                city=None,
                onboarding_status="PENDING"
            )
            # Initialize onboarding state
            state["context_json"]["onboarding_step"] = "business_name"
            conversation_state.update_state(clean_phone, "ONBOARDING", booking_details=state["context_json"])
            
            welcome_msg = (
                "Namaste! LoadSetu par aapka swagat hai. 🙏\n"
                "Hum aapka profile setup karenge.\n\n"
                "Kripya apni Business Name (Vyapaar ka naam) likh kar bhejein."
            )
            notification_service.send_whatsapp(From, welcome_msg)
            return Response(content="<Response></Response>", media_type="application/xml")
            
        onboarding_step = state["context_json"].get("onboarding_step")
        if not onboarding_step and operator.get("onboarding_status") == "PENDING":
            onboarding_step = "business_name"
            state["context_json"]["onboarding_step"] = "business_name"
            conversation_state.update_state(clean_phone, "ONBOARDING", booking_details=state["context_json"])
            
        if onboarding_step in ["business_name", "gst_number", "city"]:
            onboarding_service.handle_onboarding_step(From, clean_phone, Body, onboarding_step, state, operator)
            return Response(content="<Response></Response>", media_type="application/xml")
            
    # Update state with incoming message
    state = conversation_state.update_state(clean_phone, state.get("last_intent", "OTHER"), new_message=Body)
    history = state["context_json"]["history"]
    
    # 8. Classify Intent
    intent = intake_agent.classify_intent(history)
    logger.info(f"Classified intent: {intent} for number {clean_phone}")
    
    # 9. Intent State Machine routing
    if intent == "NEW_BOOKING":
        booking_service.handle_new_booking(From, clean_phone, Body, history, state)
        
    elif intent == "CONFIRMATION":
        booking_service.handle_confirmation(From, clean_phone, Body, state, operator)
        
    elif intent == "STATUS_UPDATE":
        status_service.handle_status_update(
            From, 
            clean_phone, 
            Body, 
            operator, 
            truck_as_driver,
            num_media=NumMedia,
            media_url=MediaUrl0,
            media_content_type=MediaContentType0
        )
        
    elif intent == "QUERY":
        status_service.handle_query(From, clean_phone, operator, truck_as_driver)
        
    else:
        # OTHER - general response
        status_service.handle_other(From, clean_phone)
        
    return Response(content="<Response></Response>", media_type="application/xml")
