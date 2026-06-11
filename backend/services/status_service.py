import logging
import datetime
from services import supabase_service, notification_service, timeline_service
from agents import status_agent

logger = logging.getLogger(__name__)

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
    """Handles status updates from driver or operator with POD and driver acceptance flow support."""
    # Check if sender is driver of an active shipment
    if truck_as_driver:
        shipment = supabase_service.get_active_shipment_for_driver(clean_phone)
        if not shipment:
            notification_service.send_whatsapp(from_whatsapp, "Aapki koi active trip nahi hai.")
            return
            
        shipment_id = shipment["id"]
        msg_upper = body.strip().upper()
        
        # 1. Driver Acceptance Flow (Task 7)
        if shipment["status"] == "DRIVER_PENDING_ACCEPTANCE":
            if msg_upper in ["YES", "HAAN", "OK"]:
                # Transition to DRIVER_ACCEPTED
                supabase_service.update_shipment_status(shipment_id, "DRIVER_ACCEPTED")
                timeline_service.log_event(
                    shipment_id=shipment_id,
                    phone_number=clean_phone,
                    event_type="driver_accepted",
                    title="Driver Accepted Assignment",
                    description=f"Driver {truck_as_driver['driver_name']} accepted the trip."
                )
                
                # Notify operator
                op_phone = get_operator_phone(shipment["operator_id"])
                if op_phone:
                    notification_service.send_whatsapp(
                        to_phone=f"whatsapp:{op_phone}",
                        body=f"✅ DRIVER ACCEPTED\n\nDriver {truck_as_driver['driver_name']} ne trip ID {shipment_id[:8].upper()} accept kar li hai.",
                        shipment_id=shipment_id
                    )
                    
                notification_service.send_whatsapp(from_whatsapp, "Trip accept karne ke liye dhanyawad! Maal load hone par 'LOADED' reply karein.")
                return
                
            elif msg_upper in ["NO", "NAHI", "REJECT"]:
                # Release truck
                supabase_service.update_truck_availability(
                    truck_id=shipment["truck_id"],
                    is_available=True
                )
                # Transition to DRIVER_REJECTED / REASSIGNMENT_REQUIRED
                supabase_service.update_shipment_status(shipment_id, "REASSIGNMENT_REQUIRED")
                
                timeline_service.log_event(
                    shipment_id=shipment_id,
                    phone_number=clean_phone,
                    event_type="driver_rejected",
                    title="Driver Rejected Assignment",
                    description=f"Driver {truck_as_driver['driver_name']} rejected the trip."
                )
                timeline_service.log_event(
                    shipment_id=shipment_id,
                    phone_number=clean_phone,
                    event_type="reassignment_required",
                    title="Reassignment Required",
                    description="Shipment reassignment required after driver rejection."
                )
                
                # Notify operator
                op_phone = get_operator_phone(shipment["operator_id"])
                if op_phone:
                    notification_service.send_whatsapp(
                        to_phone=f"whatsapp:{op_phone}",
                        body=f"❌ DRIVER REJECTED\n\nDriver {truck_as_driver['driver_name']} ne trip ID {shipment_id[:8].upper()} REJECT kar di hai. Kripya truck reassign karein.",
                        shipment_id=shipment_id
                    )
                    
                notification_service.send_whatsapp(from_whatsapp, "Trip reject kar di gayi hai. Hum operator ko inform kar denge.")
                return
                
            # If driver sends loaded/transit status without explicit YES, treat it as implicit acceptance:
            # Let it proceed below to handle status update, but first log implicit driver_accepted.
            elif "LOAD" in msg_upper or "NIKAL" in msg_upper or "TRANSIT" in msg_upper or "DELIVER" in msg_upper or "POHONCH" in msg_upper:
                timeline_service.log_event(
                    shipment_id=shipment_id,
                    phone_number=clean_phone,
                    event_type="driver_accepted",
                    title="Driver Accepted (Implicit)",
                    description=f"Driver {truck_as_driver['driver_name']} reported status without explicit YES. Acceptance implied."
                )
        
        # 2. Parse driver status
        parsed = status_agent.parse_status(body)
        new_status = parsed["status"]
        note = parsed["note"]
        
        # Log timeline event: driver status received
        timeline_service.log_event(
            shipment_id=shipment_id,
            phone_number=clean_phone,
            event_type="driver_status_received",
            title="Driver Status Received",
            description=f"Message: {body}",
            metadata={"parsed_status": new_status, "note": note}
        )

        if new_status == "UNKNOWN":
            # Forward unparsed message to operator as-is
            op_phone = get_operator_phone(shipment["operator_id"])
            if op_phone:
                notification_service.send_whatsapp(
                    to_phone=f"whatsapp:{op_phone}",
                    body=f"Driver ka message (Direct): \"{body}\"",
                    shipment_id=shipment_id
                )
            notification_service.send_whatsapp(from_whatsapp, "Message operator ko forward kar diya gaya hai.")
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
                pod_received_at = datetime.datetime.now(supabase_service.IST).isoformat()
                
                # Log timeline event: proof_of_delivery_received
                timeline_service.log_event(
                    shipment_id=shipment_id,
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
            shipment_id=shipment_id,
            status=new_status,
            pod_status=pod_status,
            pod_note=pod_note,
            pod_media_url=pod_media_url,
            pod_received_at=pod_received_at
        )
        
        # Log status transition timeline events
        if new_status == "LOADED":
            timeline_service.log_event(
                shipment_id=shipment_id,
                phone_number=clean_phone,
                event_type="shipment_loaded",
                title="Shipment Loaded",
                description="Maal load ho gaya hai."
            )
        elif new_status == "IN_TRANSIT":
            timeline_service.log_event(
                shipment_id=shipment_id,
                phone_number=clean_phone,
                event_type="shipment_in_transit",
                title="Shipment In Transit",
                description="Truck route par nikal chuka hai."
            )
        elif new_status == "DELIVERED":
            timeline_service.log_event(
                shipment_id=shipment_id,
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
        op_phone = get_operator_phone(shipment["operator_id"])
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
                
            notification_service.send_whatsapp(op_whatsapp, op_notification, shipment_id=shipment_id)
            
        # Respond to driver
        notification_service.send_whatsapp(from_whatsapp, f"Status updated: {status_text}. Dhanyawad!")
        
    elif operator:
        # Operator status updates (e.g. they want to manually change or check)
        shipment = supabase_service.get_active_shipment_for_operator(operator["id"])
        if not shipment:
            notification_service.send_whatsapp(from_whatsapp, "Aapki koi active trip nahi hai.")
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
            timeline_service.log_event(
                shipment_id=shipment["id"],
                phone_number=clean_phone,
                event_type=f"shipment_{new_status.lower()}",
                title=event_title,
                description=f"Status updated manually by operator to {new_status}"
            )
            notification_service.send_whatsapp(from_whatsapp, f"Trip status updated manually to: {new_status}")
        else:
            notification_service.send_whatsapp(from_whatsapp, f"Trip ID: {shipment['id'][:8].upper()} current status is: {shipment['status']}")


def get_operator_phone(operator_id: str) -> str:
    """Helper to retrieve operator phone number."""
    if supabase_service.is_mock_active():
        for op in supabase_service.MOCK_OPERATORS.values():
            if op["id"] == operator_id:
                return op["phone"]
        return None
    try:
        op_res = supabase_service.supabase_client.table("operators").select("phone").eq("id", operator_id).execute()
        return op_res.data[0]["phone"] if op_res.data else None
    except Exception as e:
        logger.error(f"Error fetching operator phone: {e}")
        return None


def handle_query(from_whatsapp: str, clean_phone: str, operator: dict, truck_as_driver: dict):
    """Handles inquiries about shipment status."""
    if operator:
        shipment = supabase_service.get_active_shipment_for_operator(operator["id"])
        if not shipment:
            notification_service.send_whatsapp(from_whatsapp, "Aapki koi active trip nahi hai.")
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
            f"Truck Number: {truck['truck_number'] if truck else 'N/A'}"
        )
        notification_service.send_whatsapp(from_whatsapp, reply, shipment_id=shipment["id"])
        
    elif truck_as_driver:
        shipment = supabase_service.get_active_shipment_for_driver(clean_phone)
        if not shipment:
            notification_service.send_whatsapp(from_whatsapp, "Aapki koi active trip nahi hai.")
            return
            
        reply = (
            f"Trip Info:\n"
            f"ID: {shipment['id'][:8].upper()}\n"
            f"Route: {shipment['origin']} -> {shipment['destination']}\n"
            f"Cargo: {shipment['cargo_type']}\n"
            f"Scheduled Date: {shipment['scheduled_date']}\n\n"
            "Status update likhein: 'LOADED', 'TRANSIT', or 'DELIVERED'"
        )
        notification_service.send_whatsapp(from_whatsapp, reply, shipment_id=shipment["id"])


def handle_other(from_whatsapp: str, clean_phone: str):
    """Fallback handler for chit-chat or generic messages."""
    reply = (
        "Namaste! 🙏\n"
        "LoadSetu automated freight assistant par aapka swagat hai.\n\n"
        "- Naya truck book karne ke liye origin, destination aur cargo likhein. (e.g. 'Surat se Mumbai 8 ton textiles')\n"
        "- Active trip status check karne ke liye 'status' likhein."
    )
    notification_service.send_whatsapp(from_whatsapp, reply)
    conversation_state.clear_state(clean_phone)

