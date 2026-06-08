import os
import logging
from supabase import create_client, Client

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://dummy.supabase.co")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "dummy_service_key")

# Flag to check if we are using mock database operations (when credentials are placeholders)
IS_MOCK = (
    "dummy" in SUPABASE_URL 
    or "dummy" in SUPABASE_SERVICE_KEY 
    or SUPABASE_URL == "https://xxxxxxxxxxxx.supabase.co"
)

supabase_client: Client = None

if not IS_MOCK:
    try:
        supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        logger.info("Supabase client initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
        IS_MOCK = True

# Mock DB store for local testing without Supabase credentials
MOCK_OPERATORS = {}
MOCK_TRUCKS = [
    {"id": "t1", "driver_name": "Ramesh Kumar", "driver_phone": "+919876543211", "truck_number": "MH-15-AB-1234", "truck_type": "open", "capacity_tons": 10.0, "home_city": "Nashik", "current_city": "Nashik", "is_available": True},
    {"id": "t2", "driver_name": "Suresh Patel", "driver_phone": "+919876543212", "truck_number": "MH-04-CX-5678", "truck_type": "closed", "capacity_tons": 8.5, "home_city": "Surat", "current_city": "Surat", "is_available": True},
    {"id": "t3", "driver_name": "Dinesh Singh", "driver_phone": "+919876543213", "truck_number": "MH-12-GH-9012", "truck_type": "open", "capacity_tons": 5.0, "home_city": "Mumbai", "current_city": "Mumbai", "is_available": True},
    {"id": "t4", "driver_name": "Jaspreet Singh", "driver_phone": "+919876543214", "truck_number": "PB-10-CZ-2468", "truck_type": "closed", "capacity_tons": 16.0, "home_city": "Ludhiana", "current_city": "Ludhiana", "is_available": True},
    {"id": "t5", "driver_name": "Vikram Rathore", "driver_phone": "+919876543215", "truck_number": "RJ-14-GH-1357", "truck_type": "flatbed", "capacity_tons": 20.0, "home_city": "Jaipur", "current_city": "Jaipur", "is_available": True}
]
MOCK_SHIPMENTS = {}
MOCK_MESSAGES = []
MOCK_CONVERSATIONS = {}

def is_mock_active() -> bool:
    return IS_MOCK

# --- Operators Operations ---

def get_operator_by_phone(phone: str):
    if IS_MOCK:
        return MOCK_OPERATORS.get(phone)
    try:
        res = supabase_client.table("operators").select("*").eq("phone", phone).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"Error getting operator: {e}")
        return None

def create_operator(phone: str, name: str = None, business_name: str = None, city: str = None):
    if IS_MOCK:
        operator = {
            "id": f"op_{len(MOCK_OPERATORS) + 1}",
            "phone": phone,
            "name": name or "Unknown",
            "business_name": business_name or "Unknown Business",
            "city": city or "Unknown City"
        }
        MOCK_OPERATORS[phone] = operator
        return operator
    try:
        data = {"phone": phone, "name": name, "business_name": business_name, "city": city}
        res = supabase_client.table("operators").insert(data).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"Error creating operator: {e}")
        return None

# --- Trucks Operations ---

def get_all_trucks():
    if IS_MOCK:
        return MOCK_TRUCKS
    try:
        res = supabase_client.table("trucks").select("*").execute()
        return res.data
    except Exception as e:
        logger.error(f"Error getting trucks: {e}")
        return []

def get_available_trucks(origin: str, capacity: float):
    if IS_MOCK:
        # Simple match: check if available and has capacity >= weight
        # Also matching home_city case-insensitively
        results = [
            t for t in MOCK_TRUCKS 
            if t["is_available"] 
            and float(t["capacity_tons"]) >= float(capacity)
            and t["home_city"].lower() == origin.lower()
        ]
        # Fallback to state level or any if none found
        if not results:
            results = [
                t for t in MOCK_TRUCKS 
                if t["is_available"] 
                and float(t["capacity_tons"]) >= float(capacity)
            ]
        return results[:3]
    try:
        # Query matching home_city
        res = supabase_client.table("trucks").select("*")\
            .eq("is_available", True)\
            .gte("capacity_tons", capacity)\
            .eq("home_city", origin).execute()
        
        if not res.data:
            # Fallback: get any available truck with capacity
            res = supabase_client.table("trucks").select("*")\
                .eq("is_available", True)\
                .gte("capacity_tons", capacity).execute()
        
        # Sort by capacity fit (closest capacity)
        sorted_trucks = sorted(res.data, key=lambda x: float(x["capacity_tons"]) - float(capacity))
        return sorted_trucks[:3]
    except Exception as e:
        logger.error(f"Error matching trucks: {e}")
        return []

def get_truck_by_id(truck_id: str):
    if IS_MOCK:
        for t in MOCK_TRUCKS:
            if t["id"] == truck_id:
                return t
        return None
    try:
        res = supabase_client.table("trucks").select("*").eq("id", truck_id).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"Error getting truck by id: {e}")
        return None

def update_truck_availability(truck_id: str, is_available: bool, current_city: str = None):
    if IS_MOCK:
        for t in MOCK_TRUCKS:
            if t["id"] == truck_id:
                t["is_available"] = is_available
                if current_city:
                    t["current_city"] = current_city
                return t
        return None
    try:
        data = {"is_available": is_available}
        if current_city:
            data["current_city"] = current_city
        res = supabase_client.table("trucks").update(data).eq("id", truck_id).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"Error updating truck availability: {e}")
        return None

def get_truck_by_driver_phone(driver_phone: str):
    if IS_MOCK:
        for t in MOCK_TRUCKS:
            if t["driver_phone"] == driver_phone:
                return t
        return None
    try:
        res = supabase_client.table("trucks").select("*").eq("driver_phone", driver_phone).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"Error getting truck by driver phone: {e}")
        return None

def create_truck(driver_name: str, driver_phone: str, truck_number: str, truck_type: str, capacity_tons: float, home_city: str, notes: str = None):
    if IS_MOCK:
        truck = {
            "id": f"t_{len(MOCK_TRUCKS) + 1}",
            "driver_name": driver_name,
            "driver_phone": driver_phone,
            "truck_number": truck_number,
            "truck_type": truck_type,
            "capacity_tons": capacity_tons,
            "home_city": home_city,
            "current_city": home_city,
            "is_available": True,
            "notes": notes
        }
        MOCK_TRUCKS.append(truck)
        return truck
    try:
        data = {
            "driver_name": driver_name,
            "driver_phone": driver_phone,
            "truck_number": truck_number,
            "truck_type": truck_type,
            "capacity_tons": capacity_tons,
            "home_city": home_city,
            "current_city": home_city,
            "notes": notes
        }
        res = supabase_client.table("trucks").insert(data).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"Error creating truck: {e}")
        return None

# --- Shipments Operations ---

def create_shipment(operator_id: str, truck_id: str, origin: str, destination: str, cargo_type: str, weight_tons: float, scheduled_date: str, status: str = "PENDING"):
    if IS_MOCK:
        shipment_id = f"shp_{len(MOCK_SHIPMENTS) + 1}"
        shipment = {
            "id": shipment_id,
            "operator_id": operator_id,
            "truck_id": truck_id,
            "origin": origin,
            "destination": destination,
            "cargo_type": cargo_type,
            "weight_tons": weight_tons,
            "scheduled_date": scheduled_date,
            "status": status,
            "ewb_draft_json": {},
            "ewb_pdf_url": None,
            "confirmed_at": None if status == "PENDING" else "2026-06-08T12:00:00Z",
            "loaded_at": None,
            "delivered_at": None,
            "delay_alerted": False,
            "created_at": "2026-06-08T12:00:00Z",
            "updated_at": "2026-06-08T12:00:00Z"
        }
        MOCK_SHIPMENTS[shipment_id] = shipment
        return shipment
    try:
        data = {
            "operator_id": operator_id,
            "truck_id": truck_id,
            "origin": origin,
            "destination": destination,
            "cargo_type": cargo_type,
            "weight_tons": weight_tons,
            "scheduled_date": scheduled_date,
            "status": status
        }
        if status == "CONFIRMED":
            import datetime
            data["confirmed_at"] = datetime.datetime.now().isoformat()
        res = supabase_client.table("shipments").insert(data).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"Error creating shipment: {e}")
        return None

def get_shipment_by_id(shipment_id: str):
    if IS_MOCK:
        return MOCK_SHIPMENTS.get(shipment_id)
    try:
        res = supabase_client.table("shipments").select("*").eq("id", shipment_id).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"Error getting shipment by id: {e}")
        return None

def get_shipments_with_details():
    if IS_MOCK:
        # Format joined details
        details = []
        for s in MOCK_SHIPMENTS.values():
            # Find truck details
            truck = next((t for t in MOCK_TRUCKS if t["id"] == s["truck_id"]), None)
            # Find operator details
            operator = next((op for op in MOCK_OPERATORS.values() if op["id"] == s["operator_id"]), None)
            details.append({
                **s,
                "truck": truck,
                "operator": operator
            })
        return details
    try:
        res = supabase_client.table("shipments").select("*, trucks(*), operators(*)").order("created_at", desc=True).execute()
        return res.data
    except Exception as e:
        logger.error(f"Error getting detailed shipments: {e}")
        return []

def update_shipment_status(shipment_id: str, status: str, ewb_draft_json: dict = None, ewb_pdf_url: str = None):
    import datetime
    now_iso = datetime.datetime.now().isoformat()
    if IS_MOCK:
        s = MOCK_SHIPMENTS.get(shipment_id)
        if s:
            s["status"] = status
            s["updated_at"] = now_iso
            if status == "CONFIRMED":
                s["confirmed_at"] = now_iso
            elif status == "LOADED":
                s["loaded_at"] = now_iso
            elif status == "DELIVERED":
                s["delivered_at"] = now_iso
            if ewb_draft_json is not None:
                s["ewb_draft_json"] = ewb_draft_json
            if ewb_pdf_url is not None:
                s["ewb_pdf_url"] = ewb_pdf_url
            return s
        return None
    try:
        data = {"status": status, "updated_at": now_iso}
        if status == "CONFIRMED":
            data["confirmed_at"] = now_iso
        elif status == "LOADED":
            data["loaded_at"] = now_iso
        elif status == "DELIVERED":
            data["delivered_at"] = now_iso
        if ewb_draft_json is not None:
            data["ewb_draft_json"] = ewb_draft_json
        if ewb_pdf_url is not None:
            data["ewb_pdf_url"] = ewb_pdf_url
        res = supabase_client.table("shipments").update(data).eq("id", shipment_id).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"Error updating shipment: {e}")
        return None

def get_active_shipment_for_operator(operator_id: str):
    if IS_MOCK:
        # Return most recent pending/confirmed/loaded/transit shipment
        active_statuses = ["PENDING", "CONFIRMED", "LOADED", "IN_TRANSIT", "DELAYED"]
        for s in reversed(list(MOCK_SHIPMENTS.values())):
            if s["operator_id"] == operator_id and s["status"] in active_statuses:
                return s
        return None
    try:
        active_statuses = ["PENDING", "CONFIRMED", "LOADED", "IN_TRANSIT", "DELAYED"]
        res = supabase_client.table("shipments").select("*")\
            .eq("operator_id", operator_id)\
            .in_("status", active_statuses)\
            .order("created_at", desc=True).limit(1).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"Error getting active shipment for operator: {e}")
        return None

def get_active_shipment_for_driver(driver_phone: str):
    truck = get_truck_by_driver_phone(driver_phone)
    if not truck:
        return None
    
    if IS_MOCK:
        active_statuses = ["CONFIRMED", "LOADED", "IN_TRANSIT", "DELAYED"]
        for s in reversed(list(MOCK_SHIPMENTS.values())):
            if s["truck_id"] == truck["id"] and s["status"] in active_statuses:
                return s
        return None
    try:
        active_statuses = ["CONFIRMED", "LOADED", "IN_TRANSIT", "DELAYED"]
        res = supabase_client.table("shipments").select("*")\
            .eq("truck_id", truck["id"])\
            .in_("status", active_statuses)\
            .order("created_at", desc=True).limit(1).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"Error getting active shipment for driver: {e}")
        return None

# --- Messages Operations ---

def log_message(phone_number: str, direction: str, body: str, shipment_id: str = None):
    if IS_MOCK:
        msg = {
            "id": f"msg_{len(MOCK_MESSAGES) + 1}",
            "phone_number": phone_number,
            "direction": direction,
            "body": body,
            "shipment_id": shipment_id,
            "timestamp": "2026-06-08T12:00:00Z"
        }
        MOCK_MESSAGES.append(msg)
        return msg
    try:
        data = {
            "phone_number": phone_number,
            "direction": direction,
            "body": body,
            "shipment_id": shipment_id
        }
        res = supabase_client.table("messages").insert(data).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"Error logging message: {e}")
        return None

def get_all_messages():
    if IS_MOCK:
        return MOCK_MESSAGES
    try:
        res = supabase_client.table("messages").select("*").order("timestamp", desc=False).execute()
        return res.data
    except Exception as e:
        logger.error(f"Error getting all messages: {e}")
        return []

# --- Conversation State Operations ---

def get_conversation_state(phone_number: str):
    if IS_MOCK:
        return MOCK_CONVERSATIONS.get(phone_number)
    try:
        res = supabase_client.table("conversation_state").select("*").eq("phone_number", phone_number).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"Error getting conversation state: {e}")
        return None

def update_conversation_state(phone_number: str, last_intent: str, context_json: list, active_shipment_id: str = None):
    import datetime
    now_iso = datetime.datetime.now().isoformat()
    if IS_MOCK:
        state = {
            "phone_number": phone_number,
            "last_intent": last_intent,
            "context_json": context_json,
            "active_shipment_id": active_shipment_id,
            "updated_at": now_iso
        }
        MOCK_CONVERSATIONS[phone_number] = state
        return state
    try:
        data = {
            "phone_number": phone_number,
            "last_intent": last_intent,
            "context_json": context_json,
            "active_shipment_id": active_shipment_id,
            "updated_at": now_iso
        }
        # Upsert
        res = supabase_client.table("conversation_state").upsert(data, on_conflict="phone_number").execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"Error updating conversation state: {e}")
        return None

def upload_ewb_pdf_bytes(shipment_id: str, pdf_bytes: bytes) -> str:
    """Uploads PDF bytes to Supabase Storage and returns the public URL"""
    if IS_MOCK:
        return f"https://dummy.supabase.co/storage/v1/object/public/ewb-drafts/ewb_draft_{shipment_id}.pdf"
    try:
        filename = f"ewb_draft_{shipment_id}.pdf"
        # Upload file
        res = supabase_client.storage.from_("ewb-drafts").upload(
            path=filename,
            file=pdf_bytes,
            file_options={"content-type": "application/pdf", "x-upsert": "true"}
        )
        # Get public URL
        url_res = supabase_client.storage.from_("ewb-drafts").get_public_url(filename)
        return url_res
    except Exception as e:
        logger.error(f"Error uploading PDF: {e}")
        return ""
