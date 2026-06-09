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
    MessageSid: str = Form(...),
    NumMedia: int = Form(0),
    MediaUrl0: str = Form(None),
    MediaContentType0: str = Form(None)
):
    """POST /webhook - Main Twilio incoming message handler"""
    logger.info(f"Received webhook: From={From}, MessageSid={MessageSid}, Body='{Body[:50]}', NumMedia={NumMedia}")
    
    # 1. Twilio Signature Validation
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
    
    # 5. Load/Update Conversation State
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
            twilio_service.send_message(From, welcome_msg)
            return Response(content="<Response></Response>", media_type="application/xml")
            
        onboarding_step = state["context_json"].get("onboarding_step")
        if not onboarding_step and operator.get("onboarding_status") == "PENDING":
            onboarding_step = "business_name"
            state["context_json"]["onboarding_step"] = "business_name"
            conversation_state.update_state(clean_phone, "ONBOARDING", booking_details=state["context_json"])
            
        if onboarding_step in ["business_name", "gst_number", "city"]:
            handle_onboarding_step(From, clean_phone, Body, onboarding_step, state, operator)
            return Response(content="<Response></Response>", media_type="application/xml")
            
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
        handle_status_update(
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
        handle_query(From, clean_phone, operator, truck_as_driver)
        
    else:
        # OTHER - general response
        handle_other(From, clean_phone)
        
    return Response(content="<Response></Response>", media_type="application/xml")


def handle_onboarding_step(from_whatsapp: str, clean_phone: str, body: str, step: str, state: dict, operator: dict):
    """Handles the sequential WhatsApp onboarding steps for operators."""
    if step == "business_name":
        business_name = body.strip()
        supabase_service.update_operator(clean_phone, business_name=business_name)
        state["context_json"]["onboarding_step"] = "gst_number"
        conversation_state.update_state(clean_phone, "ONBOARDING", booking_details=state["context_json"])
        
        reply = "Dhanyawad! Ab apna GSTIN (GST Number) bhejein. Agar nahi hai, toh 'skip' likhein."
        twilio_service.send_message(from_whatsapp, reply)
        
    elif step == "gst_number":
        gst_num = body.strip()
        if gst_num.lower() != "skip":
            supabase_service.update_operator(clean_phone, gst_number=gst_num)
        state["context_json"]["onboarding_step"] = "city"
        conversation_state.update_state(clean_phone, "ONBOARDING", booking_details=state["context_json"])
        
        reply = "Aapka city (Shahar) kaunsa hai? Shahar ka naam likh kar bhejein."
        twilio_service.send_message(from_whatsapp, reply)
        
    elif step == "city":
        city = body.strip()
        supabase_service.update_operator(clean_phone, city=city, name="Operator", onboarding_status="COMPLETED")
        state["context_json"]["onboarding_step"] = "completed"
        # Reset state to OTHER for normal booking
        conversation_state.update_state(clean_phone, "OTHER", booking_details=state["context_json"])
        
        # Log timeline event
        supabase_service.create_timeline_event(
            shipment_id=None,
            phone_number=clean_phone,
            event_type="operator_onboarded",
            title="Operator Onboarded",
            description=f"Operator onboarded successfully. Business Name: {operator.get('business_name') or 'N/A'}, City: {city}"
        )
        
        reply = (
            "Aapka onboarding safaltapoorvak ho gaya hai! 🎉\n"
            "Ab aap truck book kar sakte hain. Example:\n"
            "\"Surat se Mumbai 8 ton textiles kal ke liye\""
        )
        twilio_service.send_message(from_whatsapp, reply)



# --- Handler Functionsdef handle_new_booking(from_whatsapp: str, clean_phone: str, body: str, history: list, state: dict):
    """Handles the intake of a new booking request with details validation, merging, and clarifications."""
    # 1. Log timeline event: booking request received
    supabase_service.create_timeline_event(
        shipment_id=None,
        phone_number=clean_phone,
        event_type="booking_request_received",
        title="Booking Request Received",
        description=f"Message: {body}"
    )

    # Retrieve existing details from conversation state to merge
    existing_details = state["context_json"].get("booking_details", {})
    if not isinstance(existing_details, dict):
        existing_details = {}

    # Extract details using LLM agent
    new_details = intake_agent.extract_freight_details(history[:-1], body)
    logger.info(f"Extracted details: {new_details}")
    
    # Merge new details into existing details (only non-null/non-empty values override)
    merged_details = {}
    for key in ["origin", "destination", "cargo_type", "weight_tons", "scheduled_date", "special_requirements"]:
        merged_details[key] = new_details.get(key) or existing_details.get(key)
    
    # Parse confidence
    confidence = new_details.get("confidence") or existing_details.get("confidence") or "LOW"
    merged_details["confidence"] = confidence
    
    # Log timeline event: AI extraction completed
    supabase_service.create_timeline_event(
        shipment_id=None,
        phone_number=clean_phone,
        event_type="ai_extraction_completed",
        title="AI Extraction Completed",
        description=f"Details: {merged_details}",
        metadata={"confidence": confidence, "details": merged_details}
    )
    
    # Required fields validation before matching
    missing_fields = []
    if not merged_details.get("origin"):
        missing_fields.append("origin")
    if not merged_details.get("destination"):
        missing_fields.append("destination")
    if not merged_details.get("weight_tons"):
        missing_fields.append("weight")
    if not merged_details.get("cargo_type"):
        missing_fields.append("cargo type")
        
    # If confidence is LOW or required fields are missing, ask clarification question
    if confidence == "LOW" or missing_fields:
        if len(missing_fields) == 1:
            field_name = missing_fields[0]
            if field_name == "origin":
                question = "Kripya origin city (maal kahan se uthana hai) bata dijiye. Example: Surat"
            elif field_name == "destination":
                question = "Kripya destination city (maal kahan bhejna hai) bata dijiye. Example: Mumbai"
            elif field_name == "weight":
                question = "Kripya cargo ka weight bata dijiye. Example: 8 ton"
            else: # cargo type
                question = "Kripya cargo type (maal kya hai) bata dijiye. Example: textiles"
        elif len(missing_fields) > 1:
            named_fields = []
            examples = []
            for f in missing_fields:
                if f == "origin":
                    named_fields.append("origin city")
                    examples.append("Surat")
                elif f == "destination":
                    named_fields.append("destination city")
                    examples.append("Mumbai")
                elif f == "weight":
                    named_fields.append("weight")
                    examples.append("8 ton")
                elif f == "cargo type":
                    named_fields.append("cargo type")
                    examples.append("textiles")
            
            fields_str = " aur ".join([", ".join(named_fields[:-1]), named_fields[-1]] if len(named_fields) > 1 else named_fields)
            ex_str = " se ".join(examples[:2]) + (" " + " ".join(examples[2:]) if len(examples) > 2 else "")
            question = f"Kripya {fields_str} bata dijiye. Example: {ex_str}"
        else:
            question = "Mujhe details clear nahi lag rahi hain. Kripya naya booking details fir se bhejein. Example: Surat se Mumbai 8 ton textiles kal ke liye"
            
        twilio_service.send_message(from_whatsapp, question)
        
        # Log timeline event
        supabase_service.create_timeline_event(
            shipment_id=None,
            phone_number=clean_phone,
            event_type="clarification_requested",
            title="Clarification Requested",
            description=f"Clarified fields: {missing_fields}. Asked: {question}",
            metadata={"missing_fields": missing_fields, "confidence": confidence}
        )
        
        # Keep intent as NEW_BOOKING, save merged booking details
        conversation_state.update_state(clean_phone, "NEW_BOOKING", booking_details=merged_details)
        return
        
    # All fields present, perform matching
    origin = merged_details["origin"]
    destination = merged_details["destination"]
    weight = float(merged_details["weight_tons"])
    
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
        
    # Log timeline event: truck matching completed
    supabase_service.create_timeline_event(
        shipment_id=None,
        phone_number=clean_phone,
        event_type="truck_matching_completed",
        title="Truck Matching Completed",
        description=f"Matched {len(matched_trucks)} trucks for route {origin} to {destination}",
        metadata={"matched_count": len(matched_trucks), "trucks": matched_trucks}
    )

    # Format and send choices
    choices_msg = matching_agent.format_truck_choices(matched_trucks)
    
    # Store options in conversation state context to allow selection
    conversation_state.update_state(
        phone=clean_phone,
        last_intent="CONFIRMATION",
        matched_trucks=matched_trucks,
        booking_details=merged_details
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
    
    # Use booking_details strictly (do not reconstruct from history/truck fields)
    origin = booking_details.get("origin")
    destination = booking_details.get("destination")
    cargo = booking_details.get("cargo_type")
    weight = float(booking_details.get("weight_tons", selected_truck.get("capacity_tons") or 8.0))
    scheduled_date = booking_details.get("scheduled_date") or "2026-06-09"
    
    # Log timeline event: truck option selected
    supabase_service.create_timeline_event(
        shipment_id=None,
        phone_number=clean_phone,
        event_type="truck_option_selected",
        title="Truck Option Selected",
        description=f"Option {choice_idx + 1} chosen: {selected_truck['truck_number']}",
        metadata={"choice_index": choice_idx + 1, "truck": selected_truck, "booking_details": booking_details}
    )

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
        
    # Log timeline event: shipment confirmed
    supabase_service.create_timeline_event(
        shipment_id=shipment["id"],
        phone_number=clean_phone,
        event_type="shipment_confirmed",
        title="Shipment Confirmed",
        description=f"Shipment ID SHP_{shipment['id'][:4].upper()} created.",
        metadata={"shipment": shipment}
    )

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
    
    # Log timeline event: EWB draft generated
    supabase_service.create_timeline_event(
        shipment_id=shipment["id"],
        phone_number=clean_phone,
        event_type="ewb_draft_generated",
        title="E-Way Bill Draft Generated",
        description=f"Draft PDF available at {pdf_url}",
        metadata={"ewb_fields": ewb_fields, "pdf_url": pdf_url}
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
    
    # Log timeline event: driver notified
    supabase_service.create_timeline_event(
        shipment_id=shipment["id"],
        phone_number=selected_truck["driver_phone"],
        event_type="driver_notified",
        title="Driver Notified",
        description=f"Notification sent to driver {selected_truck['driver_name']}"
    )


def handle_status_update(
    from_whatsapp: str, 
    clean_phone: str, 
    body: str, 
    operator: dict, 
    truck_as_driver: dict,
    num_media: int = 0,
    media_url: str = None,
    media_content_type: str = None
):
    """Handles status updates from driver or operator with POD support."""
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
        
        # Log timeline event: driver status received
        supabase_service.create_timeline_event(
            shipment_id=shipment["id"],
            phone_number=clean_phone,
            event_type="driver_status_received",
            title="Driver Status Received",
            description=f"Message: {body}",
            metadata={"parsed_status": new_status, "note": note}
        )

        if new_status == "UNKNOWN":
            # Forward unparsed message to operator as-is
            op_phone = None
            if not supabase_service.is_mock_active():
                try:
                    op_res = supabase_service.supabase_client.table("operators").select("phone").eq("id", shipment["operator_id"]).execute()
                    if op_res.data:
                        op_phone = op_res.data[0]["phone"]
                except Exception as e:
                    logger.error(f"Error fetching operator phone for forwarding: {e}")
            else:
                for op in supabase_service.MOCK_OPERATORS.values():
                    if op["id"] == shipment["operator_id"]:
                        op_phone = op["phone"]
            if op_phone:
                op_whatsapp = f"whatsapp:{op_phone}"
                forward_msg = f"Driver ka message (Direct): \"{body}\""
                twilio_service.send_message(op_whatsapp, forward_msg, shipment_id=shipment["id"])
            twilio_service.send_message(from_whatsapp, "Message operator ko forward kar diya gaya hai.")
            return
            
        # Check if DELIVERED and media present (Proof of Delivery)
        pod_status = None
        pod_note = None
        pod_media_url = None
        pod_received_at = None
        
        if new_status == "DELIVERED":
            if num_media > 0 or media_url:
                pod_status = "RECEIVED"
                pod_note = body
                pod_media_url = media_url
                import datetime
                pod_received_at = datetime.datetime.now().isoformat()
                
                # Log timeline event: proof_of_delivery_received
                supabase_service.create_timeline_event(
                    shipment_id=shipment["id"],
                    phone_number=clean_phone,
                    event_type="proof_of_delivery_received",
                    title="Proof of Delivery Received",
                    description=f"POD Note: {body}",
                    metadata={"pod_media_url": media_url, "pod_note": body}
                )
            else:
                pod_status = "PENDING"
        
        # Update shipment status (and POD if DELIVERED)
        supabase_service.update_shipment_status(
            shipment_id=shipment["id"],
            status=new_status,
            pod_status=pod_status,
            pod_note=pod_note,
            pod_media_url=pod_media_url,
            pod_received_at=pod_received_at
        )
        
        # Log status transition timeline events
        if new_status == "LOADED":
            supabase_service.create_timeline_event(
                shipment_id=shipment["id"],
                phone_number=clean_phone,
                event_type="shipment_loaded",
                title="Shipment Loaded",
                description="Maal load ho gaya hai."
            )
        elif new_status == "IN_TRANSIT":
            supabase_service.create_timeline_event(
                shipment_id=shipment["id"],
                phone_number=clean_phone,
                event_type="shipment_in_transit",
                title="Shipment In Transit",
                description="Truck route par nikal chuka hai."
            )
        elif new_status == "DELIVERED":
            supabase_service.create_timeline_event(
                shipment_id=shipment["id"],
                phone_number=clean_phone,
                event_type="shipment_delivered",
                title="Shipment Delivered",
                description="Trip safaltapoorvak deliver ho gayi."
            )
            
        # If DELIVERED, release the truck and set current_city
        if new_status == "DELIVERED":
            supabase_service.update_truck_availability(
                truck_id=shipment["truck_id"],
                is_available=True,
                current_city=shipment["destination"]
            )
            
        status_text = {
            "LOADED": "LOADED (Maal load ho gaya hai)",
            "IN_TRANSIT": "IN_TRANSIT (Truck nikal gaya hai)",
            "DELIVERED": "DELIVERED (Trip safaltapoorvak deliver ho gayi)",
            "DELAYED": "DELAYED (Trip mein delay reported)"
        }.get(new_status, new_status)
        
        # Notify operator
        op_phone = None
        if not supabase_service.is_mock_active():
            try:
                op_res = supabase_service.supabase_client.table("operators").select("phone").eq("id", shipment["operator_id"]).execute()
                if op_res.data:
                    op_phone = op_res.data[0]["phone"]
            except Exception as e:
                logger.error(f"Error fetching operator phone for notification: {e}")
        else:
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
            if pod_media_url:
                op_notification += f"\nProof of Delivery: {pod_media_url}"
                
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
            
            event_title = f"Shipment {new_status.replace('_', ' ').capitalize()}"
            supabase_service.create_timeline_event(
                shipment_id=shipment["id"],
                phone_number=clean_phone,
                event_type=f"shipment_{new_status.lower()}",
                title=event_title,
                description=f"Status updated manually by operator to {new_status}"
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

