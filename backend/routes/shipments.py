import os
from fastapi import APIRouter, Header, HTTPException, status, Path
from services import supabase_service, pdf_service, notification_service
from agents import document_agent
from utils.delay_checker import calculate_delay_risk

router = APIRouter(prefix="/shipments", tags=["shipments"])

async def verify_admin_token(authorization: str):
    app_env = os.getenv("APP_ENV", "development")
    admin_token = os.getenv("ADMIN_TOKEN")
    
    if app_env == "production" and (not admin_token or admin_token == "secret_admin_token_2026"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server configuration error: Secure ADMIN_TOKEN must be configured in production"
        )
        
    expected_token = admin_token or "secret_admin_token_2026"
    
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header"
        )
    token = authorization.split(" ")[1]
    if token != expected_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin token"
        )

@router.get("")
async def get_shipments(page: int = 1, limit: int = 20, authorization: str = Header(None)):
    """GET /shipments - Returns paginated shipments with joined operator and truck details (requires Admin token)."""
    await verify_admin_token(authorization)
    
    # Validation / pagination bounds
    if page < 1:
        page = 1
    if limit < 1:
        limit = 20
    elif limit > 100:
        limit = 100
        
    # Retrieve all detailed shipments
    detailed_shipments = supabase_service.get_shipments_with_details()
    
    # Dynamically compute and attach delay risk score & level
    for s in detailed_shipments:
        risk = calculate_delay_risk(s)
        s["delay_risk_score"] = risk["score"]
        s["delay_risk_level"] = risk["level"]
        s["delay_risk_reasons"] = risk["reasons"]
        
    # Apply manual pagination
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    paginated_shipments = detailed_shipments[start_idx:end_idx]
    
    return {
        "shipments": paginated_shipments,
        "total": len(detailed_shipments),
        "page": page,
        "limit": limit
    }

@router.get("/{shipment_id}/timeline")
async def get_shipment_timeline(
    shipment_id: str = Path(...),
    authorization: str = Header(None)
):
    """GET /shipments/{shipment_id}/timeline - Returns chronological timeline events for a shipment."""
    await verify_admin_token(authorization)
    events = supabase_service.get_timeline_for_shipment(shipment_id)
    return {"timeline": events}


@router.get("/{shipment_id}/notifications")
async def get_shipment_notifications(
    shipment_id: str = Path(...),
    authorization: str = Header(None)
):
    """GET /shipments/{shipment_id}/notifications - Returns all notification attempts for a shipment."""
    await verify_admin_token(authorization)
    attempts = supabase_service.get_notifications_for_shipment(shipment_id)
    return {"notifications": attempts}

@router.post("/{shipment_id}/dispute-pack")
async def generate_dispute_pack(
    shipment_id: str = Path(...),
    authorization: str = Header(None)
):
    """POST /shipments/{shipment_id}/dispute-pack - Generates a verifiable dispute packet PDF."""
    await verify_admin_token(authorization)
    
    # 1. Fetch shipment details
    shipment = supabase_service.get_shipment_by_id(shipment_id)
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
        
    # 2. Fetch Operator details
    operator = supabase_service.get_operator_by_id(shipment.get("operator_id"))
    if not operator:
        operator = {"name": "Unknown Operator", "phone": "N/A", "business_name": "N/A", "city": "N/A"}
        
    # 3. Fetch Truck details
    truck = supabase_service.get_truck_by_id(shipment.get("truck_id"))
    if not truck:
        truck = {"driver_name": "Unknown Driver", "driver_phone": "N/A", "truck_number": "N/A"}
        
    # 4. Fetch Timeline Events
    events = supabase_service.get_timeline_for_shipment(shipment_id)
    
    # 5. Fetch Chat Messages (retrieve all messages, we will filter within the generator)
    messages = supabase_service.get_all_messages()
    
    # 6. Generate PDF and get URL
    try:
        pdf_url = pdf_service.generate_dispute_pack_pdf(
            shipment=shipment,
            operator=operator,
            truck=truck,
            events=events,
            messages=messages
        )
        return {"pdf_url": pdf_url}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate dispute packet PDF: {e}"
        )


@router.post("/{shipment_id}/cancel")
async def cancel_shipment(
    shipment_id: str = Path(...),
    authorization: str = Header(None)
):
    """POST /shipments/{shipment_id}/cancel - Cancels an active shipment (requires Admin token)."""
    await verify_admin_token(authorization)
    
    shipment = supabase_service.get_shipment_by_id(shipment_id)
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
        
    current_status = shipment.get("status", "PENDING")
    if current_status in ["CANCELLED", "DELIVERED"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel shipment in terminal status: {current_status}"
        )
        
    # Update status to CANCELLED
    supabase_service.update_shipment_status(shipment_id, "CANCELLED")
    
    # Release truck
    truck_id = shipment.get("truck_id")
    if truck_id:
        supabase_service.update_truck_availability(truck_id, is_available=True)
        
    # Log timeline event
    supabase_service.create_timeline_event(
        shipment_id=shipment_id,
        event_type="shipment_cancelled",
        title="Shipment Cancelled",
        description="Shipment cancelled by admin."
    )
    
    # Notify operator
    operator = supabase_service.get_operator_by_id(shipment.get("operator_id"))
    if operator:
        notification_service.send_whatsapp(
            to_phone=f"whatsapp:{operator['phone']}",
            body=f"❌ TRIP CANCELLED\n\nTrip ID: {shipment_id[:8].upper()} has been cancelled by dispatcher.",
            shipment_id=shipment_id
        )
        
    # Notify driver
    if truck_id:
        truck = supabase_service.get_truck_by_id(truck_id)
        if truck:
            notification_service.send_whatsapp(
                to_phone=f"whatsapp:{truck['driver_phone']}",
                body=f"Trip ID {shipment_id[:8].upper()} has been CANCELLED.",
                shipment_id=shipment_id
            )
            
    return {"message": "Shipment cancelled successfully", "status": "CANCELLED"}


@router.post("/{shipment_id}/reassign")
async def reassign_shipment(
    shipment_id: str = Path(...),
    authorization: str = Header(None)
):
    """POST /shipments/{shipment_id}/reassign - Reassigns the shipment to another available truck (requires Admin token)."""
    await verify_admin_token(authorization)
    
    shipment = supabase_service.get_shipment_by_id(shipment_id)
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
        
    current_status = shipment.get("status", "PENDING")
    if current_status in ["CANCELLED", "DELIVERED"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reassign shipment in terminal status: {current_status}"
        )
        
    old_truck_id = shipment.get("truck_id")
    origin = shipment.get("origin")
    destination = shipment.get("destination")
    weight = float(shipment.get("weight_tons", 8.0))
    
    # Match new available trucks, excluding the current/old truck
    available = supabase_service.get_available_trucks(origin, weight)
    new_truck = None
    for t in available:
        if t["id"] != old_truck_id:
            new_truck = t
            break
            
    if not new_truck:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No other available trucks found matching requirements."
        )
        
    # Update shipment status and truck assignment
    # Generate new EWB fields
    operator = supabase_service.get_operator_by_id(shipment.get("operator_id"))
    try:
        ewb_fields = document_agent.build_ewb_draft(shipment, operator, new_truck)
        pdf_url = pdf_service.generate_ewb_pdf(ewb_fields, shipment_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate EWB PDF for new truck: {e}"
        )

    # Release old truck
    if old_truck_id:
        supabase_service.update_truck_availability(old_truck_id, is_available=True)
        
    # Lock new truck
    supabase_service.update_truck_availability(new_truck["id"], is_available=False, current_city=origin)
    
    # Update shipment in DB
    supabase_service.update_shipment_status(
        shipment_id=shipment_id,
        status="DRIVER_PENDING_ACCEPTANCE",
        ewb_draft_json=ewb_fields,
        ewb_pdf_url=pdf_url
    )
    
    # Update the truck_id directly in Supabase/Mock
    if supabase_service.is_mock_active():
        supabase_service.MOCK_SHIPMENTS[shipment_id]["truck_id"] = new_truck["id"]
    else:
        supabase_service.supabase_client.table("shipments")\
            .update({"truck_id": new_truck["id"]})\
            .eq("id", shipment_id).execute()
            
    # Log timeline event
    old_truck = supabase_service.get_truck_by_id(old_truck_id) if old_truck_id else None
    old_number = old_truck["truck_number"] if old_truck else "N/A"
    
    supabase_service.create_timeline_event(
        shipment_id=shipment_id,
        event_type="truck_reassigned",
        title="Truck Reassigned",
        description=f"Truck reassigned from {old_number} to {new_truck['truck_number']}."
    )
    
    # Log driver acceptance requested
    supabase_service.create_timeline_event(
        shipment_id=shipment_id,
        phone_number=new_truck["driver_phone"],
        event_type="driver_acceptance_requested",
        title="Driver Acceptance Requested",
        description=f"Trip assignment sent to new driver {new_truck['driver_name']}."
    )
    
    # Notify new driver
    driver_whatsapp = f"whatsapp:{new_truck['driver_phone']}"
    driver_assignment_msg = (
        "🚨 TRIP ASSIGNED (REASSIGNMENT)!\n\n"
        f"Aapko ek trip assign ki gayi hai:\n"
        f"Origin: {origin}\n"
        f"Destination: {destination}\n"
        f"Cargo: {shipment['cargo_type']} ({weight} Ton)\n"
        f"Operator: {operator.get('business_name')} ({operator.get('phone')})\n\n"
        "Trip accept karne ke liye reply karein: YES\n"
        "Reject karne ke liye reply karein: NO"
    )
    driver_notified = notification_service.send_whatsapp(driver_whatsapp, driver_assignment_msg, shipment_id=shipment_id)
    
    final_status = "DRIVER_PENDING_ACCEPTANCE"
    
    if not driver_notified:
        final_status = "DRIVER_NOTIFY_FAILED"
        supabase_service.update_shipment_status(shipment_id, "DRIVER_NOTIFY_FAILED")
        supabase_service.create_timeline_event(
            shipment_id=shipment_id,
            phone_number=new_truck["driver_phone"],
            event_type="driver_notification_failed",
            title="Driver Notification Failed",
            description=f"Could not reach driver {new_truck['driver_name']} ({new_truck['driver_phone']}) during reassignment."
        )
        if operator:
            notification_service.send_whatsapp(
                to_phone=f"whatsapp:{operator['phone']}",
                body=f"⚠️ Driver Notification Fail (Reassignment)!\nTrip ID {shipment_id[:8].upper()} reassigned to {new_truck['truck_number']} but driver {new_truck['driver_name']} could not be reached.",
                shipment_id=shipment_id
            )
    else:
        # Log driver notified successfully
        supabase_service.create_timeline_event(
            shipment_id=shipment_id,
            phone_number=new_truck["driver_phone"],
            event_type="driver_notified",
            title="Driver Notified",
            description=f"Notification sent to new driver {new_truck['driver_name']}"
        )
        # Notify operator
        if operator:
            notification_service.send_whatsapp(
                to_phone=f"whatsapp:{operator['phone']}",
                body=f"🔄 TRUCK REASSIGNED\n\nTrip ID: {shipment_id[:8].upper()} has been reassigned to {new_truck['truck_number']} (Driver: {new_truck['driver_name']}). Waiting for driver acceptance.",
                shipment_id=shipment_id,
                media_url=pdf_url
            )
        
    return {"message": "Shipment reassigned successfully", "status": final_status, "truck": new_truck}



