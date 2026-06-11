import os
import logging
import datetime
from fastapi import APIRouter, Header, HTTPException, status
from services import supabase_service, twilio_service, booking_service
from routes.shipments import verify_admin_token
from agents import matching_agent
from utils import conversation_state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/demo", tags=["demo"])

@router.post("/seed")
async def seed_demo_data(authorization: str = Header(None)):
    """POST /demo/seed - Resets and seeds demo control room data in mock memory/DB."""
    await verify_admin_token(authorization)
    
    # Reset mock database collections
    supabase_service.MOCK_OPERATORS.clear()
    supabase_service.MOCK_SHIPMENTS.clear()
    supabase_service.MOCK_MESSAGES.clear()
    supabase_service.MOCK_CONVERSATIONS.clear()
    supabase_service.MOCK_SHIPMENT_EVENTS.clear()
    if hasattr(supabase_service, "MOCK_NOTIFICATION_ATTEMPTS"):
        supabase_service.MOCK_NOTIFICATION_ATTEMPTS.clear()
    if hasattr(supabase_service, "MOCK_REVIEW_ITEMS"):
        supabase_service.MOCK_REVIEW_ITEMS.clear()
    
    # Reset home city and availability for mock trucks
    for t in supabase_service.MOCK_TRUCKS:
        t["is_available"] = True
        t["current_city"] = t["home_city"]
        
    # Re-seed default operator Rajesh Patel
    supabase_service.create_operator(
        phone="+919876543210",
        name="Rajesh Patel",
        business_name="Patel Logistics",
        city="Surat",
        onboarding_status="COMPLETED"
    )
    
    # Seed a mock low-confidence review item for demo testing
    supabase_service.create_review_item(
        phone_number="+919876543219",
        status="OPEN",
        extracted_details={
            "origin": "Surat",
            "destination": "Ahmedabad",
            "cargo_type": "Iron Rods",
            "weight_tons": None
        },
        missing_fields=["weight_tons", "scheduled_date"],
        latest_message="Mujhe Surat se Ahmedabad iron rods bhejna hai, kal ya parso"
    )
    
    # Log timeline event
    supabase_service.create_timeline_event(
        shipment_id=None,
        phone_number=None,
        event_type="operator_onboarded",
        title="Demo Control Room Seeded",
        description="Initial demo operators, truck availability, and manual review items seeded."
    )
    
    return {"message": "Demo data seeded successfully"}


@router.post("/simulate-booking")
async def simulate_booking(authorization: str = Header(None)):
    """POST /demo/simulate-booking - Simulates an incoming freight booking request."""
    await verify_admin_token(authorization)
    
    phone = "+919876543210"
    # Ensure default operator is registered and onboarded
    op = supabase_service.get_operator_by_phone(phone)
    if not op:
        op = supabase_service.create_operator(
            phone=phone,
            name="Rajesh Patel",
            business_name="Patel Logistics",
            city="Surat",
            onboarding_status="COMPLETED"
        )
    else:
        supabase_service.update_operator(phone, onboarding_status="COMPLETED")
        
    body = "Mujhe Surat se Mumbai ke liye 8 ton textiles ka truck chahiye kal ke liye"
    
    # Log incoming message
    supabase_service.log_message(phone_number=phone, direction="INBOUND", body=body)
    
    # 1. Log timeline event: booking request received
    supabase_service.create_timeline_event(
        shipment_id=None,
        phone_number=phone,
        event_type="booking_request_received",
        title="Booking Request Received",
        description=f"Message: {body}"
    )
    
    # Get relative date for tomorrow in IST
    tomorrow = (datetime.datetime.now(supabase_service.IST) + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    
    # Mock AI details extraction results
    details = {
        "origin": "Surat",
        "destination": "Mumbai",
        "cargo_type": "Textiles",
        "weight_tons": 8.0,
        "scheduled_date": tomorrow,
        "confidence": "HIGH"
    }
    
    # 2. Log timeline event: AI extraction completed
    supabase_service.create_timeline_event(
        shipment_id=None,
        phone_number=phone,
        event_type="ai_extraction_completed",
        title="AI Extraction Completed",
        description=f"Details: {details}",
        metadata={"confidence": "HIGH", "details": details}
    )
    
    # Query trucks matching origin and capacity
    matched_trucks = matching_agent.find_trucks("Surat", "Mumbai", 8.0)
    
    # 3. Log timeline event: truck matching completed
    supabase_service.create_timeline_event(
        shipment_id=None,
        phone_number=phone,
        event_type="truck_matching_completed",
        title="Truck Matching Completed",
        description=f"Matched {len(matched_trucks)} trucks for route Surat to Mumbai",
        metadata={"matched_count": len(matched_trucks), "trucks": matched_trucks}
    )
    
    # Update conversation state with details to expect CONFIRMATION selection (1, 2, or 3)
    conversation_state.update_state(
        phone=phone,
        last_intent="CONFIRMATION",
        matched_trucks=matched_trucks,
        booking_details=details
    )
    
    # Format and send truck choices
    choices_msg = matching_agent.format_truck_choices(matched_trucks)
    twilio_service.send_message(phone, choices_msg)
    
    return {
        "message": "Booking simulation succeeded",
        "extracted_details": details,
        "matched_trucks": matched_trucks,
        "choices_message": choices_msg
    }


@router.post("/simulate-confirm")
async def simulate_confirm(authorization: str = Header(None)):
    """POST /demo/simulate-confirm - Simulates operator confirming option 1 (first matched truck)."""
    await verify_admin_token(authorization)
    
    phone = "+919876543210"
    state = conversation_state.get_state(phone)
    matched_trucks = state.get("context_json", {}).get("matched_trucks", [])
    
    if not matched_trucks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No matched trucks found in active state. Please simulate booking first."
        )
        
    op = supabase_service.get_operator_by_phone(phone)
    if not op:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Demo operator Rajesh Patel is not registered."
        )
        
    # Process confirmation for Option 1
    booking_service.handle_confirmation(
        from_whatsapp=f"whatsapp:{phone}",
        clean_phone=phone,
        body="1",
        state=state,
        operator=op
    )
    
    # Find the newly confirmed shipment
    shipments = supabase_service.get_shipments_with_details()
    confirmed = [s for s in shipments if s["status"] == "CONFIRMED"]
    shipment_id = confirmed[0]["id"] if confirmed else None
    
    return {
        "message": "Confirmation simulation succeeded (confirmed option 1)",
        "shipment_id": shipment_id
    }


@router.post("/simulate-transit")
async def simulate_transit(authorization: str = Header(None)):
    """POST /demo/simulate-transit - Simulates truck departing and entering transit."""
    await verify_admin_token(authorization)
    
    shipments = supabase_service.get_shipments_with_details()
    loaded_shipments = [s for s in shipments if s["status"] in ["CONFIRMED", "LOADED"]]
    if not loaded_shipments:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No CONFIRMED or LOADED shipments found to simulate transit. Please confirm/load a booking first."
        )
        
    target = loaded_shipments[0]
    shipment_id = target["id"]
    driver_phone = target["trucks"]["driver_phone"] if target.get("trucks") else None
    
    # Update status to IN_TRANSIT
    supabase_service.update_shipment_status(shipment_id, "IN_TRANSIT")
    
    # Log timeline event
    supabase_service.create_timeline_event(
        shipment_id=shipment_id,
        phone_number=driver_phone,
        event_type="shipment_in_transit",
        title="Shipment In Transit",
        description="Driver departed from origin. Truck is now on the route."
    )
    
    # Notify operator
    operator_phone = target["operators"]["phone"] if target.get("operators") else None
    if operator_phone:
        twilio_service.send_message(
            to_number=f"whatsapp:{operator_phone}",
            body=f"ℹ️ TRIP STATUS UPDATE\n\nTrip ID: {shipment_id[:8].upper()}\nStatus: IN_TRANSIT (Truck nikal gaya hai)\nNote: Simulated transit status update.",
            shipment_id=shipment_id
        )
        
    return {"message": "Shipment status updated to IN_TRANSIT", "shipment_id": shipment_id}


@router.post("/simulate-loaded")
async def simulate_loaded(authorization: str = Header(None)):
    """POST /demo/simulate-loaded - Simulates driver reporting cargo loaded."""
    await verify_admin_token(authorization)
    
    shipments = supabase_service.get_shipments_with_details()
    confirmed_shipments = [s for s in shipments if s["status"] == "CONFIRMED"]
    if not confirmed_shipments:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="No CONFIRMED shipments found to simulate loading. Please confirm a booking first."
        )
        
    target = confirmed_shipments[0]
    shipment_id = target["id"]
    driver_phone = target["trucks"]["driver_phone"] if target.get("trucks") else None
    
    # Update shipment status
    supabase_service.update_shipment_status(shipment_id, "LOADED")
    
    # Log timeline event: shipment loaded
    supabase_service.create_timeline_event(
        shipment_id=shipment_id,
        phone_number=driver_phone,
        event_type="shipment_loaded",
        title="Shipment Loaded",
        description="Driver confirmed Maal load ho gaya hai."
    )
    
    # Notify operator
    operator_phone = target["operators"]["phone"] if target.get("operators") else None
    if operator_phone:
        twilio_service.send_message(
            to_number=f"whatsapp:{operator_phone}",
            body=f"ℹ️ TRIP STATUS UPDATE\n\nTrip ID: {shipment_id[:8].upper()}\nStatus: LOADED (Maal load ho gaya hai)\nNote: Simulated loading status update.",
            shipment_id=shipment_id
        )
        
    return {"message": "Shipment status updated to LOADED", "shipment_id": shipment_id}


@router.post("/simulate-delivered")
async def simulate_delivered(authorization: str = Header(None)):
    """POST /demo/simulate-delivered - Simulates driver delivering cargo and uploading POD."""
    await verify_admin_token(authorization)
    
    shipments = supabase_service.get_shipments_with_details()
    active_shipments = [s for s in shipments if s["status"] in ["CONFIRMED", "LOADED", "IN_TRANSIT", "DELAYED"]]
    if not active_shipments:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="No active shipments found to simulate delivery."
        )
        
    target = active_shipments[0]
    shipment_id = target["id"]
    driver_phone = target["trucks"]["driver_phone"] if target.get("trucks") else None
    
    # Mock POD details
    pod_media = "https://dummy.supabase.co/storage/v1/object/public/ewb-drafts/mock_pod_receipt.jpg"
    pod_time = datetime.datetime.now().isoformat()
    
    # Update status and save POD
    supabase_service.update_shipment_status(
        shipment_id=shipment_id,
        status="DELIVERED",
        pod_status="RECEIVED",
        pod_note="Delivery completed. Mock receipt attached.",
        pod_media_url=pod_media,
        pod_received_at=pod_time
    )
    
    # Release truck
    if target.get("truck_id"):
        supabase_service.update_truck_availability(
            truck_id=target["truck_id"],
            is_available=True,
            current_city=target["destination"]
        )
        
    # Log timeline event: proof_of_delivery_received
    supabase_service.create_timeline_event(
        shipment_id=shipment_id,
        phone_number=driver_phone,
        event_type="proof_of_delivery_received",
        title="Proof of Delivery Received",
        description="Delivery receipt image submitted by driver.",
        metadata={"pod_media_url": pod_media, "pod_note": "Delivery completed. Mock receipt attached."}
    )
    
    # Log timeline event: shipment delivered
    supabase_service.create_timeline_event(
        shipment_id=shipment_id,
        phone_number=driver_phone,
        event_type="shipment_delivered",
        title="Shipment Delivered",
        description="Cargo successfully delivered to destination."
    )
    
    # Notify operator
    operator_phone = target["operators"]["phone"] if target.get("operators") else None
    if operator_phone:
        twilio_service.send_message(
            to_number=f"whatsapp:{operator_phone}",
            body=f"✅ TRIP DELIVERED & CONFIRMED\n\nTrip ID: {shipment_id[:8].upper()}\nStatus: DELIVERED\nProof of Delivery: {pod_media}\nDriver Note: \"Delivery completed. Mock receipt attached.\"",
            shipment_id=shipment_id
        )
        
    return {"message": "Shipment status updated to DELIVERED with POD", "shipment_id": shipment_id}


@router.post("/trigger-delay")
async def trigger_delay(authorization: str = Header(None)):
    """POST /demo/trigger-delay - Triggers a simulated delay alert for the latest confirmed shipment."""
    await verify_admin_token(authorization)
    
    shipments = supabase_service.get_shipments_with_details()
    confirmed_shipments = [s for s in shipments if s["status"] == "CONFIRMED"]
    if not confirmed_shipments:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="No CONFIRMED shipments found to trigger delay."
        )
        
    target = confirmed_shipments[0]
    shipment_id = target["id"]
    
    # Update shipment delayed flag in DB
    if supabase_service.is_mock_active():
        if shipment_id in supabase_service.MOCK_SHIPMENTS:
            supabase_service.MOCK_SHIPMENTS[shipment_id]["status"] = "DELAYED"
            supabase_service.MOCK_SHIPMENTS[shipment_id]["delay_alerted"] = True
    else:
        supabase_service.supabase_client.table("shipments")\
            .update({"status": "DELAYED", "delay_alerted": True})\
            .eq("id", shipment_id).execute()
            
    # Log timeline event: delay_alert_triggered
    supabase_service.create_timeline_event(
        shipment_id=shipment_id,
        phone_number=None,
        event_type="delay_alert_triggered",
        title="Delay Alert Triggered",
        description=f"Pickup delay flagged. Scheduled date: {target.get('scheduled_date')}."
    )
    
    # Notify operator
    operator_phone = target["operators"]["phone"] if target.get("operators") else None
    if operator_phone:
        driver_name = target["trucks"]["driver_name"] if target.get("trucks") else "Driver"
        driver_phone = target["trucks"]["driver_phone"] if target.get("trucks") else "N/A"
        truck_num = target["trucks"]["truck_number"] if target.get("trucks") else "N/A"
        
        twilio_service.send_message(
            to_number=f"whatsapp:{operator_phone}",
            body=f"⚠️ DELAY ALERT!\n\nTrip ID: {shipment_id[:8].upper()}\nRoute: {target['origin']} to {target['destination']}\nDriver {driver_name} ({truck_num}) ne scheduled time ke 3 ghante baad tak loading update nahi diya hai.\n\nKripya driver se contact karein: {driver_phone}",
            shipment_id=shipment_id
        )
        
    return {"message": "Shipment marked as DELAYED and delay alert triggered", "shipment_id": shipment_id}
