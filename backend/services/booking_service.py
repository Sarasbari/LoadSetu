import logging
import re
import datetime
from services import supabase_service, notification_service, timeline_service, pdf_service
from utils import conversation_state
from agents import intake_agent, matching_agent, document_agent

logger = logging.getLogger(__name__)

def handle_new_booking(from_whatsapp: str, clean_phone: str, body: str, history: list, state: dict):
    """Handles the intake of a new booking request with details validation, merging, and clarifications."""
    # 1. Log timeline event: booking request received
    timeline_service.log_event(
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
    
    # Merge new details into existing details
    merged_details = {}
    for key in ["origin", "destination", "cargo_type", "weight_tons", "scheduled_date", "special_requirements"]:
        merged_details[key] = new_details.get(key) or existing_details.get(key)
    
    # Parse confidence
    confidence = new_details.get("confidence") or existing_details.get("confidence") or "LOW"
    merged_details["confidence"] = confidence
    
    # Server-side validations on parsed details
    origin = merged_details.get("origin")
    destination = merged_details.get("destination")
    cargo = merged_details.get("cargo_type")
    weight = merged_details.get("weight_tons")
    
    if origin and not re.match(r'^[a-zA-Z\s\.\-]{2,50}$', origin):
        question = "⚠️ Origin city invalid hai. Kripya sahi city ka naam likhein. Example: Surat"
        notification_service.send_whatsapp(from_whatsapp, question)
        merged_details["origin"] = None
        conversation_state.update_state(clean_phone, "NEW_BOOKING", booking_details=merged_details)
        return
        
    if destination and not re.match(r'^[a-zA-Z\s\.\-]{2,50}$', destination):
        question = "⚠️ Destination city invalid hai. Kripya sahi city ka naam likhein. Example: Mumbai"
        notification_service.send_whatsapp(from_whatsapp, question)
        merged_details["destination"] = None
        conversation_state.update_state(clean_phone, "NEW_BOOKING", booking_details=merged_details)
        return
        
    if cargo and (len(cargo.strip()) < 2 or len(cargo.strip()) > 100):
        question = "⚠️ Cargo name invalid. Kripya maal ka naam short mein likhein. Example: textiles"
        notification_service.send_whatsapp(from_whatsapp, question)
        merged_details["cargo_type"] = None
        conversation_state.update_state(clean_phone, "NEW_BOOKING", booking_details=merged_details)
        return
        
    if weight is not None:
        try:
            wt = float(weight)
            if wt <= 0.1 or wt > 100.0:
                question = "⚠️ Cargo weight 0.1 ton aur 100 ton ke beech hona chahiye. Kripya sahi weight bhejein. Example: 8 ton"
                notification_service.send_whatsapp(from_whatsapp, question)
                merged_details["weight_tons"] = None
                conversation_state.update_state(clean_phone, "NEW_BOOKING", booking_details=merged_details)
                return
        except ValueError:
            merged_details["weight_tons"] = None
            
    # Log timeline event: AI extraction completed
    timeline_service.log_event(
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
        
    # If confidence is LOW or required fields are missing, ask clarification question and log to manual review queue
    if confidence == "LOW" or missing_fields:
        # Create or update manual review queue item
        review_item = supabase_service.get_review_item_by_phone(clean_phone)
        if review_item:
            supabase_service.update_review_item(
                item_id=review_item["id"],
                extracted_details=merged_details,
                missing_fields=missing_fields,
                latest_message=body
            )
        else:
            supabase_service.create_review_item(
                phone_number=clean_phone,
                status="OPEN",
                extracted_details=merged_details,
                missing_fields=missing_fields,
                latest_message=body
            )
            
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
            
        notification_service.send_whatsapp(from_whatsapp, question)
        
        # Log timeline event
        timeline_service.log_event(
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
        notification_service.send_whatsapp(from_whatsapp, no_trucks_msg)
        conversation_state.clear_state(clean_phone)
        return
        
    # Resolve any open review item for this phone number
    review_item = supabase_service.get_review_item_by_phone(clean_phone)
    if review_item:
        supabase_service.update_review_item(item_id=review_item["id"], status="RESOLVED")
        
    # Log timeline event: truck matching completed
    timeline_service.log_event(
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
    notification_service.send_whatsapp(from_whatsapp, choices_msg)


def orchestrate_booking_confirmation(from_whatsapp: str, clean_phone: str, choice_idx: int, state: dict, operator: dict) -> dict:
    """Orchestrates reliable booking confirmation steps, preventing silent failures and half-booked states."""
    matched_trucks = state["context_json"].get("matched_trucks", [])
    booking_details = state["context_json"].get("booking_details", {})
    
    selected_truck = matched_trucks[choice_idx]
    origin = booking_details.get("origin")
    destination = booking_details.get("destination")
    cargo = booking_details.get("cargo_type")
    weight = float(booking_details.get("weight_tons", selected_truck.get("capacity_tons") or 8.0))
    
    tomorrow = (datetime.datetime.now(supabase_service.IST) + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    scheduled_date = booking_details.get("scheduled_date") or tomorrow
    
    missing_fields = []
    for f in ["origin", "destination", "cargo_type", "weight_tons", "scheduled_date"]:
        if not booking_details.get(f):
            missing_fields.append(f)
            
    match_reason = f"Truck {selected_truck['truck_number']} has {selected_truck['capacity_tons']}T capacity matching required {weight}T on route {origin}-{destination}."
    
    ai_metadata = {
        "extracted_fields": {
            "origin": origin,
            "destination": destination,
            "cargo_type": cargo,
            "weight_tons": weight,
            "scheduled_date": scheduled_date,
            "special_requirements": booking_details.get("special_requirements")
        },
        "missing_fields": missing_fields,
        "match_reason": match_reason
    }
    
    # 1. Log timeline event: Option selected
    timeline_service.log_event(
        shipment_id=None,
        phone_number=clean_phone,
        event_type="truck_option_selected",
        title="Truck Option Selected",
        description=f"Option {choice_idx + 1} chosen: {selected_truck['truck_number']}",
        metadata={"choice_index": choice_idx + 1, "truck": selected_truck, "booking_details": booking_details}
    )
    
    # 2. Create Shipment with CONFIRMING status
    shipment = supabase_service.create_shipment(
        operator_id=operator["id"],
        truck_id=selected_truck["id"],
        origin=origin,
        destination=destination,
        cargo_type=cargo,
        weight_tons=weight,
        scheduled_date=scheduled_date,
        status="CONFIRMING",
        ai_confidence=booking_details.get("confidence", "LOW"),
        ai_metadata=ai_metadata
    )
    
    if not shipment:
        error_msg = "Mafi chahte hain, booking system error aagaya. Kripya resend karein."
        notification_service.send_whatsapp(from_whatsapp, error_msg)
        return None
        
    shipment_id = shipment["id"]
    
    # 3. Log timeline event: confirming
    timeline_service.log_event(
        shipment_id=shipment_id,
        phone_number=clean_phone,
        event_type="shipment_confirming",
        title="Shipment Confirming",
        description="Booking initiated. Compiling documentation..."
    )
    
    # 4. Mark truck unavailable
    supabase_service.update_truck_availability(
        truck_id=selected_truck["id"],
        is_available=False,
        current_city=origin
    )
    
    # 5. Generate E-Way Bill PDF
    try:
        ewb_fields = document_agent.build_ewb_draft(shipment, operator, selected_truck)
        pdf_url = pdf_service.generate_ewb_pdf(ewb_fields, shipment_id)
        
        # Log timeline event: EWB draft generated
        timeline_service.log_event(
            shipment_id=shipment_id,
            phone_number=clean_phone,
            event_type="ewb_draft_generated",
            title="E-Way Bill Draft Generated",
            description=f"Draft PDF available at {pdf_url}",
            metadata={"ewb_fields": ewb_fields, "pdf_url": pdf_url}
        )
    except Exception as e:
        logger.error(f"E-Way bill PDF generation failed: {e}")
        # Set status to DOCUMENT_FAILED
        supabase_service.update_shipment_status(
            shipment_id=shipment_id,
            status="DOCUMENT_FAILED"
        )
        timeline_service.log_event(
            shipment_id=shipment_id,
            phone_number=clean_phone,
            event_type="ewb_generation_failed",
            title="E-Way Bill PDF Failed",
            description=f"Error: {str(e)}"
        )
        
        # Notify operator
        err_msg = (
            f"⚠️ TRIP DOCUMENTATION FAILED!\n\n"
            f"Trip ID: {shipment_id[:8].upper()}\n"
            f"E-way bill draft generation fail ho gaya hai. Hum jald hi call karenge."
        )
        notification_service.send_whatsapp(from_whatsapp, err_msg, shipment_id=shipment_id)
        
        # Clear state
        conversation_state.update_state(
            phone=clean_phone,
            last_intent="OTHER",
            matched_trucks=[],
            booking_details={},
            active_shipment_id=shipment_id
        )
        return shipment
        
    # 6. Update status to CONFIRMED
    supabase_service.update_shipment_status(
        shipment_id=shipment_id,
        status="CONFIRMED",
        ewb_draft_json=ewb_fields,
        ewb_pdf_url=pdf_url
    )
    
    timeline_service.log_event(
        shipment_id=shipment_id,
        phone_number=clean_phone,
        event_type="shipment_confirmed",
        title="Shipment Confirmed",
        description=f"Shipment ID SHP_{shipment_id[:4].upper()} created."
    )
    
    # 7. Notify Operator of Confirmation
    confirmation_msg = (
        "✅ Booking CONFIRMED!\n\n"
        f"Trip ID: {shipment_id[:8].upper()}\n"
        f"Truck Number: {selected_truck['truck_number']}\n"
        f"Driver Name: {selected_truck['driver_name']} ({selected_truck['driver_phone']})\n"
        f"Route: {origin} to {destination}\n"
        f"Estimated Rate: ₹{selected_truck.get('calculated_rate', 5000):,}\n\n"
        "Draft E-Way Bill PDF nichhe bheja gaya hai.\n"
        "Driver assignment pending acceptance."
    )
    notification_service.send_whatsapp(
        to_phone=from_whatsapp,
        body=confirmation_msg,
        shipment_id=shipment_id,
        media_url=pdf_url
    )
    
    # 8. Notify Driver and ask for Acceptance (YES/NO)
    driver_whatsapp = f"whatsapp:{selected_truck['driver_phone']}"
    driver_assignment_msg = (
        "🚨 TRIP ASSIGNED!\n\n"
        f"Aapko ek trip assign ki gayi hai:\n"
        f"Origin: {origin}\n"
        f"Destination: {destination}\n"
        f"Cargo: {cargo} ({weight} Ton)\n"
        f"Operator: {operator.get('business_name')} ({operator.get('phone')})\n\n"
        "Trip accept karne ke liye reply karein: YES\n"
        "Reject karne ke liye reply karein: NO"
    )
    
    # Move status to DRIVER_PENDING_ACCEPTANCE
    supabase_service.update_shipment_status(shipment_id, "DRIVER_PENDING_ACCEPTANCE")
    
    # Log timeline event: driver_acceptance_requested
    timeline_service.log_event(
        shipment_id=shipment_id,
        phone_number=selected_truck["driver_phone"],
        event_type="driver_acceptance_requested",
        title="Driver Acceptance Requested",
        description=f"Trip assignment sent to driver {selected_truck['driver_name']} for route {origin} to {destination}."
    )
    
    driver_notified = notification_service.send_whatsapp(
        to_phone=driver_whatsapp,
        body=driver_assignment_msg,
        shipment_id=shipment_id
    )
    
    if not driver_notified:
        # Mark status as DRIVER_NOTIFY_FAILED but keep shipment confirmed/intact
        supabase_service.update_shipment_status(shipment_id, "DRIVER_NOTIFY_FAILED")
        timeline_service.log_event(
            shipment_id=shipment_id,
            phone_number=selected_truck["driver_phone"],
            event_type="driver_notification_failed",
            title="Driver Notification Failed",
            description=f"Could not reach driver {selected_truck['driver_name']} ({selected_truck['driver_phone']})."
        )
        
        # Notify operator of communication failure
        warning_msg = (
            f"⚠️ Driver Notification Fail!\n"
            f"Trip ID: {shipment_id[:8].upper()} booked but driver {selected_truck['driver_name']} ko reach nahi kiya ja saka. Reassignment request trigger kar sakte hain."
        )
        notification_service.send_whatsapp(from_whatsapp, warning_msg, shipment_id=shipment_id)
    else:
        # Log driver notified successfully
        timeline_service.log_event(
            shipment_id=shipment_id,
            phone_number=selected_truck["driver_phone"],
            event_type="driver_notified",
            title="Driver Notified",
            description=f"Notification sent to driver {selected_truck['driver_name']}"
        )
        
    # Clear conversation state
    conversation_state.update_state(
        phone=clean_phone,
        last_intent="OTHER",
        matched_trucks=[],
        booking_details={},
        active_shipment_id=shipment_id
    )
    
    return shipment

def handle_whatsapp_command(clean_phone: str, message_body: str, operator: dict, truck_as_driver: dict) -> str:
    """Processes exact WhatsApp commands. Returns TwiML response string if matched, otherwise None."""
    cmd = message_body.strip().lower()
    from_whatsapp = f"whatsapp:{clean_phone}"
    
    if cmd == "help":
        reply = (
            "📌 LoadSetu Command Menu:\n\n"
            "- 'help': Bhejein commands dekhne ke liye.\n"
            "- 'status': Active shipment status dekhne ke liye.\n"
            "- 'send eway bill': E-Way Bill PDF fir se pane ke liye.\n"
            "- 'driver contact': Driver details pane ke liye.\n"
            "- 'cancel booking': Active trip cancel karne ke liye.\n"
            "- 'change truck': Truck re-assign karne ke liye."
        )
        notification_service.send_whatsapp(from_whatsapp, reply)
        return "COMMAND_PROCESSED"
        
    elif cmd == "status":
        if operator:
            shipment = supabase_service.get_active_shipment_for_operator(operator["id"])
            if not shipment:
                notification_service.send_whatsapp(from_whatsapp, "Aapki koi active trip nahi hai.")
                return "COMMAND_PROCESSED"
            truck = supabase_service.get_truck_by_id(shipment["truck_id"])
            route = f"{shipment['origin']} se {shipment['destination']}"
            driver = f"{truck['driver_name']} ({truck['driver_phone']})" if truck else "Not Assigned"
            reply = (
                f"📊 TRIP STATUS REPORT\n\n"
                f"Trip ID: {shipment['id'][:8].upper()}\n"
                f"Route: {route}\n"
                f"Cargo: {shipment['cargo_type']}\n"
                f"Status: {shipment['status']}\n"
                f"Driver: {driver}\n"
                f"Truck Number: {truck['truck_number'] if truck else 'N/A'}"
            )
            notification_service.send_whatsapp(from_whatsapp, reply, shipment_id=shipment["id"])
        elif truck_as_driver:
            shipment = supabase_service.get_active_shipment_for_driver(clean_phone)
            if not shipment:
                notification_service.send_whatsapp(from_whatsapp, "Aapki koi active trip nahi hai.")
                return "COMMAND_PROCESSED"
            reply = (
                f"Trip Info:\n"
                f"ID: {shipment['id'][:8].upper()}\n"
                f"Route: {shipment['origin']} -> {shipment['destination']}\n"
                f"Cargo: {shipment['cargo_type']}\n"
                f"Scheduled Date: {shipment['scheduled_date']}\n"
                f"Status: {shipment['status']}\n\n"
                "Status update likhein: 'LOADED', 'TRANSIT', or 'DELIVERED'"
            )
            notification_service.send_whatsapp(from_whatsapp, reply, shipment_id=shipment["id"])
        return "COMMAND_PROCESSED"
        
    elif cmd == "send eway bill":
        if not operator:
            notification_service.send_whatsapp(from_whatsapp, "Yeh command sirf operator use kar sakte hain.")
            return "COMMAND_PROCESSED"
        shipment = supabase_service.get_active_shipment_for_operator(operator["id"])
        if not shipment:
            notification_service.send_whatsapp(from_whatsapp, "Aapki koi active trip nahi hai.")
            return "COMMAND_PROCESSED"
        pdf_url = shipment.get("ewb_pdf_url")
        if pdf_url:
            notification_service.send_whatsapp(
                to_phone=from_whatsapp,
                body=f"Trip ID: {shipment['id'][:8].upper()} ka draft E-Way Bill PDF:",
                shipment_id=shipment["id"],
                media_url=pdf_url
            )
        else:
            notification_service.send_whatsapp(from_whatsapp, "Is trip ka E-Way Bill available nahi hai.")
        return "COMMAND_PROCESSED"
        
    elif cmd == "driver contact":
        if not operator:
            notification_service.send_whatsapp(from_whatsapp, "Yeh command sirf operator use kar sakte hain.")
            return "COMMAND_PROCESSED"
        shipment = supabase_service.get_active_shipment_for_operator(operator["id"])
        if not shipment:
            notification_service.send_whatsapp(from_whatsapp, "Aapki koi active trip nahi hai.")
            return "COMMAND_PROCESSED"
        truck = supabase_service.get_truck_by_id(shipment["truck_id"])
        if truck:
            reply = (
                f"📞 DRIVER CONTACT DETAILS\n\n"
                f"Driver Name: {truck['driver_name']}\n"
                f"Phone Number: {truck['driver_phone']}\n"
                f"Truck Number: {truck['truck_number']}"
            )
            notification_service.send_whatsapp(from_whatsapp, reply, shipment_id=shipment["id"])
        else:
            notification_service.send_whatsapp(from_whatsapp, "Is shipment ko abhi tak koi driver/truck assigned nahi hai.")
        return "COMMAND_PROCESSED"
        
    elif cmd == "cancel booking":
        if not operator:
            notification_service.send_whatsapp(from_whatsapp, "Yeh command sirf operator use kar sakte hain.")
            return "COMMAND_PROCESSED"
        shipment = supabase_service.get_active_shipment_for_operator(operator["id"])
        if not shipment:
            notification_service.send_whatsapp(from_whatsapp, "Aapki koi active trip nahi hai.")
            return "COMMAND_PROCESSED"
            
        if shipment["status"] not in ["PENDING", "CONFIRMING", "CONFIRMED", "DRIVER_PENDING_ACCEPTANCE", "DRIVER_NOTIFY_FAILED", "DRIVER_ACCEPTED", "DRIVER_REJECTED", "DOCUMENT_FAILED"]:
            notification_service.send_whatsapp(from_whatsapp, f"Maafi, status '{shipment['status']}' wale shipment ko cancel nahi kiya ja sakta.")
            return "COMMAND_PROCESSED"
            
        # Perform cancel
        supabase_service.update_shipment_status(shipment["id"], "CANCELLED")
        # Release truck
        supabase_service.update_truck_availability(shipment["truck_id"], is_available=True)
        # Log event
        timeline_service.log_event(
            shipment_id=shipment["id"],
            phone_number=clean_phone,
            event_type="shipment_cancelled",
            title="Shipment Cancelled",
            description="Cancelled via WhatsApp command cancel booking by operator."
        )
        
        # Notify operator
        notification_service.send_whatsapp(from_whatsapp, f"✅ Trip ID {shipment['id'][:8].upper()} ko cancel kar diya gaya hai aur truck release kar diya gaya.")
        
        # Notify driver
        truck = supabase_service.get_truck_by_id(shipment["truck_id"])
        if truck:
            notification_service.send_whatsapp(f"whatsapp:{truck['driver_phone']}", f"Trip ID {shipment['id'][:8].upper()} has been CANCELLED by operator.", shipment_id=shipment["id"])
            
        return "COMMAND_PROCESSED"
        
    elif cmd == "change truck":
        if not operator:
            notification_service.send_whatsapp(from_whatsapp, "Yeh command sirf operator use kar sakte hain.")
            return "COMMAND_PROCESSED"
        shipment = supabase_service.get_active_shipment_for_operator(operator["id"])
        if not shipment:
            notification_service.send_whatsapp(from_whatsapp, "Aapki koi active trip nahi hai.")
            return "COMMAND_PROCESSED"
            
        # Mark REASSIGNMENT_REQUIRED
        supabase_service.update_shipment_status(shipment["id"], "REASSIGNMENT_REQUIRED")
        # Log event
        timeline_service.log_event(
            shipment_id=shipment["id"],
            phone_number=clean_phone,
            event_type="reassignment_required",
            title="Reassignment Required",
            description="Operator marked reassignment required via WhatsApp change truck command."
        )
        
        notification_service.send_whatsapp(from_whatsapp, f"Reassignment request received. Dashboard par 'Reassign Truck' use karein ya naya choice karein.")
        return "COMMAND_PROCESSED"
        
    return None


def handle_confirmation(from_whatsapp: str, clean_phone: str, body: str, state: dict, operator: dict):
    """Handles truck option confirmation selection (1, 2, or 3)."""
    matched_trucks = state["context_json"].get("matched_trucks", [])
    if not matched_trucks:
        # No active truck choices, treat as new booking attempt
        handle_new_booking(from_whatsapp, clean_phone, body, [body], state)
        return
        
    # Parse choice (look for a number 1, 2, 3)
    choice_digits = re.findall(r'\b[1-3]\b', body)
    if not choice_digits:
        retry_msg = "Kripya valid option select karein: 1, 2 ya 3 reply karke confirm karein."
        notification_service.send_whatsapp(from_whatsapp, retry_msg)
        return
        
    choice_idx = int(choice_digits[0]) - 1
    orchestrate_booking_confirmation(from_whatsapp, clean_phone, choice_idx, state, operator)

