import os
import logging
import re
from fastapi import APIRouter, Form, Request, Response, HTTPException
from twilio.request_validator import RequestValidator

from services import supabase_service, twilio_service, pdf_service
from utils import conversation_state
from agents import intake_agent, matching_agent, status_agent, document_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["webhook"])

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
    MessageSid: str = Form(...)
):
    """POST /webhook - Main Twilio incoming message handler"""
    logger.info(f"Received webhook: From={From}, MessageSid={MessageSid}, Body='{Body[:50]}'")
    
    # 1. Twilio Signature Validation
    # Twilio sends form data, so we reconstruct parameters for signature validation
    form_data = await request.form()
    params = dict(form_data)
    signature = request.headers.get("X-Twilio-Signature", "")
    
    if not validate_signature(request, params, signature):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")
        
    # 2. Extract clean phone number (remove 'whatsapp:' prefix)
    clean_phone = From.replace("whatsapp:", "").strip()
    
    # 3. Log inbound message to database
    supabase_service.log_message(
        phone_number=clean_phone,
        direction="INBOUND",
        body=Body
    )
    
    # 4. Determine User Role (Operator, Driver, or New Operator)
    operator = supabase_service.get_operator_by_phone(clean_phone)
    truck_as_driver = supabase_service.get_truck_by_driver_phone(clean_phone)
    
    # If not registered as operator and not driver, auto-onboard as operator
    if not operator and not truck_as_driver:
        logger.info(f"New number detected: {clean_phone}. Auto-onboarding operator.")
        # Auto-create operator record
        operator = supabase_service.create_operator(
            phone=clean_phone,
            name="New Operator",
            business_name="New Business",
            city="Unknown"
        )
        
        # Send onboarding message
        onboarding_msg = (
            "Namaste! LoadSetu par aapka swagat hai. 🙏\n"
            "Aapka account register ho gaya hai.\n\n"
            "Truck book karne ke liye details bhejein. Example:\n"
            "\"Surat se Mumbai 8 ton textiles kal ke liye\""
        )
        twilio_service.send_message(From, onboarding_msg)
        return Response(content="<Response></Response>", media_type="application/xml")
        
    # 5. Load/Update Conversation State
    state = conversation_state.get_state(clean_phone)
    context_history = state["context_json"]["history"]
    
    # Update state with incoming message
    state = conversation_state.update_state(clean_phone, state.get("last_intent", "OTHER"), new_message=Body)
    history = state["context_json"]["history"]
    
    # 6. Classify Intent
    intent = intake_agent.classify_intent(history)
    logger.info(f"Classified intent: {intent} for number {clean_phone}")
    
    # 7. Intent State Machine
    if intent == "NEW_BOOKING":
        handle_new_booking(From, clean_phone, Body, history, state)
        
    elif intent == "CONFIRMATION":
        handle_confirmation(From, clean_phone, Body, state, operator)
        
    elif intent == "STATUS_UPDATE":
        handle_status_update(From, clean_phone, Body, operator, truck_as_driver)
        
    elif intent == "QUERY":
        handle_query(From, clean_phone, operator, truck_as_driver)
        
    else:
        # OTHER - general response
        handle_other(From, clean_phone)
        
    return Response(content="<Response></Response>", media_type="application/xml")


# --- Handler Functions ---

def handle_new_booking(from_whatsapp: str, clean_phone: str, body: str, history: list, state: dict):
    """Handles the intake of a new booking request."""
    # Extract details using LLM agent
    details = intake_agent.extract_freight_details(history[:-1], body)
    logger.info(f"Extracted details: {details}")
    
    origin = details.get("origin")
    destination = details.get("destination")
    cargo = details.get("cargo_type")
    weight = details.get("weight_tons")
    
    # Check if we have key fields
    if not origin or not destination:
        clarification = (
            "Kripya details thoda clear likhein.\n"
            "Mujhe Origin aur Destination city chahiye.\n"
            "Example: 'Surat se Mumbai 10 ton kapda'"
        )
        twilio_service.send_message(from_whatsapp, clarification)
        # Keep intent as NEW_BOOKING so follow-up maintains context
        conversation_state.update_state(clean_phone, "NEW_BOOKING", booking_details=details)
        return
        
    # Query trucks matching origin and capacity
    matched_trucks = matching_agent.find_trucks(origin, destination, weight)
    
    if not matched_trucks:
        no_trucks_msg = (
            f"Mafi chahte hain, {origin} se {destination} corridor pe abhi koi truck available nahi hai.\n"
            "Kripya thodi der baad try karein ya customer care se contact karein."
        )
        twilio_service.send_message(from_whatsapp, no_trucks_msg)
        conversation_state.clear_state(clean_phone)
        return
        
    # Format and send choices
    choices_msg = matching_agent.format_truck_choices(matched_trucks)
    
    # Store options in conversation state context to allow selection
    conversation_state.update_state(
        phone=clean_phone,
        last_intent="CONFIRMATION",
        matched_trucks=matched_trucks,
        booking_details=details
    )
    
    # Send WhatsApp choices
    twilio_service.send_message(from_whatsapp, choices_msg)


def handle_confirmation(from_whatsapp: str, clean_phone: str, body: str, state: dict, operator: dict):
    """Handles truck option confirmation selection (1, 2, or 3)."""
    matched_trucks = state["context_json"].get("matched_trucks", [])
    booking_details = state["context_json"].get("booking_details", {})
    
    if not matched_trucks:
        # No active truck choices, treat as new booking attempt
        handle_new_booking(from_whatsapp, clean_phone, body, [body], state)
        return
        
    # Parse choice (look for a number 1, 2, 3)
    choice_digits = re.findall(r'\b[1-3]\b', body)
    if not choice_digits:
        retry_msg = "Kripya valid option select karein: 1, 2 ya 3 reply karke confirm karein."
        twilio_service.send_message(from_whatsapp, retry_msg)
        return
        
    choice_idx = int(choice_digits[0]) - 1
    selected_truck = matched_trucks[choice_idx]
    
    # Use booking_details if available, fallback to defaults/history reconstruction if missing
    origin = booking_details.get("origin") or selected_truck.get("home_city")
    destination = booking_details.get("destination") or "Destination"
    cargo = booking_details.get("cargo_type") or "General Goods"
    
    weight = booking_details.get("weight_tons")
    if weight is None:
        weight = selected_truck.get("capacity_tons") or 8.0
    else:
        weight = float(weight)
        
    scheduled_date = booking_details.get("scheduled_date")
    if not scheduled_date:
        scheduled_date = "2026-06-09"  # Default tomorrow
        history_str = " ".join(state["context_json"].get("history", [])).lower()
        date_match = re.search(r'\b\d{4}-\d{2}-\d{2}\b', history_str)
        if date_match:
            scheduled_date = date_match.group(0)
        
    # Create the shipment in the DB
    shipment = supabase_service.create_shipment(
        operator_id=operator["id"],
        truck_id=selected_truck["id"],
        origin=origin,
        destination=destination,
        cargo_type=cargo,
        weight_tons=weight,
        scheduled_date=scheduled_date,
        status="CONFIRMED"
    )
    
    if not shipment:
        error_msg = "Mafi chahte hain, booking system error aagaya. Kripya resend karein."
        twilio_service.send_message(from_whatsapp, error_msg)
        return
        
    # Mark truck as unavailable and update current city to origin
    supabase_service.update_truck_availability(
        truck_id=selected_truck["id"],
        is_available=False,
        current_city=origin
    )
    
    # Generate E-Way Bill Draft and PDF
    ewb_fields = document_agent.build_ewb_draft(shipment, operator, selected_truck)
    pdf_url = pdf_service.generate_ewb_pdf(ewb_fields, shipment["id"])
    
    # Update shipment in DB with EWB details
    supabase_service.update_shipment_status(
        shipment_id=shipment["id"],
        status="CONFIRMED",
        ewb_draft_json=ewb_fields,
        ewb_pdf_url=pdf_url
    )
    
    # Clear matching state, set active shipment
    conversation_state.update_state(
        phone=clean_phone,
        last_intent="OTHER",
        matched_trucks=[],
        booking_details={},
        active_shipment_id=shipment["id"]
    )
    
    # Send confirmation to Operator
    confirmation_msg = (
        "✅ Booking CONFIRMED!\n\n"
        f"Trip ID: {shipment['id'][:8].upper()}\n"
        f"Truck Number: {selected_truck['truck_number']}\n"
        f"Driver Name: {selected_truck['driver_name']} ({selected_truck['driver_phone']})\n"
        f"Route: {origin} to {destination}\n"
        f"Estimated Rate: ₹{selected_truck.get('calculated_rate', 5000):,}\n\n"
        "Draft E-Way Bill PDF nichhe bheja gaya hai."
    )
    
    twilio_service.send_message(
        to_number=from_whatsapp,
        body=confirmation_msg,
        shipment_id=shipment["id"],
        media_url=pdf_url
    )
    
    # Notify Driver of assignment
    driver_whatsapp = f"whatsapp:{selected_truck['driver_phone']}"
    driver_assignment_msg = (
        "🚨 TRIP ASSIGNED!\n\n"
        f"Aapko ek trip assign ki gayi hai:\n"
        f"Origin: {origin}\n"
        f"Destination: {destination}\n"
        f"Cargo: {cargo} ({weight} Ton)\n"
        f"Operator: {operator.get('business_name')} ({operator.get('phone')})\n\n"
        "Maal load hone par reply karein: 'LOADED'"
    )
    twilio_service.send_message(
        to_number=driver_whatsapp,
        body=driver_assignment_msg,
        shipment_id=shipment["id"]
    )


def handle_status_update(from_whatsapp: str, clean_phone: str, body: str, operator: dict, truck_as_driver: dict):
    """Handles status updates from driver or operator."""
    # Check if sender is driver of an active shipment
    if truck_as_driver:
        shipment = supabase_service.get_active_shipment_for_driver(clean_phone)
        if not shipment:
            twilio_service.send_message(from_whatsapp, "Aapki koi active trip nahi hai.")
            return
            
        # Parse driver status
        parsed = status_agent.parse_status(body)
        new_status = parsed["status"]
        note = parsed["note"]
        
        if new_status == "UNKNOWN":
            # Forward unparsed message to operator as-is
            op_whatsapp = f"whatsapp:{supabase_service.get_operator_by_phone(shipment['operator_id'])}"
            forward_msg = f"Driver ka message (Direct): \"{body}\""
            twilio_service.send_message(op_whatsapp, forward_msg, shipment_id=shipment["id"])
            twilio_service.send_message(from_whatsapp, "Message operator ko forward kar diya gaya hai.")
            return
            
        # Update shipment status
        supabase_service.update_shipment_status(shipment["id"], new_status)
        
        # If DELIVERED, release the truck and set current_city
        if new_status == "DELIVERED":
            supabase_service.update_truck_availability(
                truck_id=shipment["truck_id"],
                is_available=True,
                current_city=shipment["destination"]
            )
            
        # Relay update to Operator
        operator_data = supabase_service.get_operator_by_phone(clean_phone) # fallback
        # In reality, fetch operator phone
        # Get operator details
        try:
            # Look up operator phone
            # Simple query using operator_id
            # In supabase_service we don't have get_operator_by_id directly, but we can query by ID
            # Let's fallback or fetch operator
            pass
        except:
            pass
            
        # For simplicity, we can fetch operator by querying the DB
        # To notify operator, let's look up phone
        # Let's print update to console and send notification
        status_text = {
            "LOADED": "LOADED (Maal load ho gaya hai)",
            "IN_TRANSIT": "IN_TRANSIT (Truck nikal gaya hai)",
            "DELIVERED": "DELIVERED (Trip safaltapoorvak deliver ho gayi)",
            "DELAYED": "DELAYED (Trip mein delay reported)"
        }.get(new_status, new_status)
        
        # Notify operator (we can do it if operator records have phone numbers)
        # Let's fetch operator phone from operators table
        # We can implement a get_operator_by_id helper or query directly
        # Let's query operators table if supabase is active
        op_phone = None
        if not supabase_service.is_mock_active():
            try:
                op_res = supabase_service.supabase_client.table("operators").select("phone").eq("id", shipment["operator_id"]).execute()
                if op_res.data:
                    op_phone = op_res.data[0]["phone"]
            except Exception as e:
                logger.error(f"Error fetching operator phone for notification: {e}")
        else:
            # Mock lookup
            for op in supabase_service.MOCK_OPERATORS.values():
                if op["id"] == shipment["operator_id"]:
                    op_phone = op["phone"]
                    
        if op_phone:
            op_whatsapp = f"whatsapp:{op_phone}"
            op_notification = (
                f"ℹ️ TRIP STATUS UPDATE\n\n"
                f"Trip ID: {shipment['id'][:8].upper()}\n"
                f"Driver {truck_as_driver['driver_name']} ne status update kiya hai:\n"
                f"Status: {status_text}\n"
                f"Note: {note}"
            )
            twilio_service.send_message(op_whatsapp, op_notification, shipment_id=shipment["id"])
            
        # Respond to driver
        twilio_service.send_message(from_whatsapp, f"Status updated: {status_text}. Dhanyawad!")
        
    elif operator:
        # Operator status updates (e.g. they want to manually change or check)
        shipment = supabase_service.get_active_shipment_for_operator(operator["id"])
        if not shipment:
            twilio_service.send_message(from_whatsapp, "Aapki koi active trip nahi hai.")
            return
            
        parsed = status_agent.parse_status(body)
        new_status = parsed["status"]
        if new_status != "UNKNOWN":
            supabase_service.update_shipment_status(shipment["id"], new_status)
            if new_status == "DELIVERED":
                supabase_service.update_truck_availability(
                    truck_id=shipment["truck_id"],
                    is_available=True,
                    current_city=shipment["destination"]
                )
            twilio_service.send_message(from_whatsapp, f"Trip status updated manually to: {new_status}")
        else:
            twilio_service.send_message(from_whatsapp, f"Trip ID: {shipment['id'][:8].upper()} current status is: {shipment['status']}")


def handle_query(from_whatsapp: str, clean_phone: str, operator: dict, truck_as_driver: dict):
    """Handles inquiries about shipment status."""
    if operator:
        shipment = supabase_service.get_active_shipment_for_operator(operator["id"])
        if not shipment:
            twilio_service.send_message(from_whatsapp, "Aapki koi active trip nahi hai.")
            return
            
        truck = supabase_service.get_truck_by_id(shipment["truck_id"])
        status = shipment["status"]
        route = f"{shipment['origin']} se {shipment['destination']}"
        driver = f"{truck['driver_name']} ({truck['driver_phone']})" if truck else "Not Assigned"
        
        reply = (
            f"📊 TRIP STATUS REPORT\n\n"
            f"Trip ID: {shipment['id'][:8].upper()}\n"
            f"Route: {route}\n"
            f"Cargo: {shipment['cargo_type']}\n"
            f"Status: {status}\n"
            f"Driver: {driver}\n"
            f"Truck Number: {truck['truck_number'] if truck else 'N/A'}\n"
        )
        twilio_service.send_message(from_whatsapp, reply, shipment_id=shipment["id"])
        
    elif truck_as_driver:
        shipment = supabase_service.get_active_shipment_for_driver(clean_phone)
        if not shipment:
            twilio_service.send_message(from_whatsapp, "Aapki koi active trip nahi hai.")
            return
            
        reply = (
            f"Trip Info:\n"
            f"ID: {shipment['id'][:8].upper()}\n"
            f"Route: {shipment['origin']} -> {shipment['destination']}\n"
            f"Cargo: {shipment['cargo_type']}\n"
            f"Scheduled Date: {shipment['scheduled_date']}\n\n"
            "Status update likhein: 'LOADED', 'TRANSIT', or 'DELIVERED'"
        )
        twilio_service.send_message(from_whatsapp, reply, shipment_id=shipment["id"])


def handle_other(from_whatsapp: str, clean_phone: str):
    """Fallback handler for chit-chat or generic messages."""
    reply = (
        "Namaste! 🙏\n"
        "LoadSetu automated freight assistant par aapka swagat hai.\n\n"
        "- Naya truck book karne ke liye origin, destination aur cargo likhein. (e.g. 'Surat se Mumbai 8 ton textiles')\n"
        "- Active trip status check karne ke liye 'status' likhein."
    )
    twilio_service.send_message(from_whatsapp, reply)
    conversation_state.clear_state(clean_phone)
