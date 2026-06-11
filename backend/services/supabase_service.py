import os
import logging
import datetime
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

# Timezone helper for Asia/Kolkata (IST)
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

# Require active keys in production environment
APP_ENV = os.getenv("APP_ENV", "development")
if APP_ENV == "production" and IS_MOCK:
    raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be configured in production mode!")

supabase_client: Client = None

if not IS_MOCK:
    try:
        supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        logger.info("Supabase client initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
        if APP_ENV == "production":
            raise RuntimeError(f"Failed to initialize Supabase client in production mode: {e}")
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
MOCK_SHIPMENT_EVENTS = []
MOCK_NOTIFICATION_ATTEMPTS = {}
MOCK_REVIEW_ITEMS = {}


def is_mock_active() -> bool:
    return IS_MOCK

def handle_error(func, *args, **kwargs):
    global IS_MOCK
    if os.getenv("APP_ENV", "development") == "production":
        raise RuntimeError(f"Supabase operation failed in production mode: {func.__name__}")
    logger.warning(f"Supabase operation failed. Auto-switching to MOCK DB mode.")
    IS_MOCK = True
    return func(*args, **kwargs)

# --- Operators Operations ---

def get_operator_by_phone(phone: str):
    if IS_MOCK:
        return MOCK_OPERATORS.get(phone)
    try:
        res = supabase_client.table("operators").select("*").eq("phone", phone).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"Error getting operator: {e}")
        return handle_error(get_operator_by_phone, phone)

def get_operator_by_id(operator_id: str):
    if IS_MOCK:
        for op in MOCK_OPERATORS.values():
            if op["id"] == operator_id:
                return op
        return None
    try:
        res = supabase_client.table("operators").select("*").eq("id", operator_id).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"Error getting operator by id: {e}")
        return handle_error(get_operator_by_id, operator_id)


def create_operator(phone: str, name: str = None, business_name: str = None, city: str = None, onboarding_status: str = "PENDING"):
    if IS_MOCK:
        operator = {
            "id": f"op_{len(MOCK_OPERATORS) + 1}",
            "phone": phone,
            "name": name or "Unknown",
            "business_name": business_name,
            "gst_number": None,
            "city": city,
            "onboarding_status": onboarding_status
        }
        MOCK_OPERATORS[phone] = operator
        return operator
    try:
        data = {
            "phone": phone, 
            "name": name, 
            "business_name": business_name, 
            "city": city,
            "onboarding_status": onboarding_status
        }
        res = supabase_client.table("operators").insert(data).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"Error creating operator: {e}")
        return handle_error(create_operator, phone, name, business_name, city, onboarding_status)

def update_operator(phone: str, name: str = None, business_name: str = None, gst_number: str = None, city: str = None, onboarding_status: str = None):
    if IS_MOCK:
        op = MOCK_OPERATORS.get(phone)
        if op:
            if name is not None: op["name"] = name
            if business_name is not None: op["business_name"] = business_name
            if gst_number is not None: op["gst_number"] = gst_number
            if city is not None: op["city"] = city
            if onboarding_status is not None: op["onboarding_status"] = onboarding_status
            return op
        return None
    try:
        data = {}
        if name is not None: data["name"] = name
        if business_name is not None: data["business_name"] = business_name
        if gst_number is not None: data["gst_number"] = gst_number
        if city is not None: data["city"] = city
        if onboarding_status is not None: data["onboarding_status"] = onboarding_status
        res = supabase_client.table("operators").update(data).eq("phone", phone).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"Error updating operator: {e}")
        return handle_error(update_operator, phone, name, business_name, gst_number, city, onboarding_status)


# --- Trucks Operations ---

def get_all_trucks():
    if IS_MOCK:
        return MOCK_TRUCKS
    try:
        res = supabase_client.table("trucks").select("*").execute()
        return res.data
    except Exception as e:
        logger.error(f"Error getting trucks: {e}")
        return handle_error(get_all_trucks)

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
        return handle_error(get_available_trucks, origin, capacity)

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
        return handle_error(get_truck_by_id, truck_id)

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
        return handle_error(update_truck_availability, truck_id, is_available, current_city)

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
        return handle_error(get_truck_by_driver_phone, driver_phone)

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
        return handle_error(create_truck, driver_name, driver_phone, truck_number, truck_type, capacity_tons, home_city, notes)

# --- Shipments Operations ---

def create_shipment(operator_id: str, truck_id: str, origin: str, destination: str, cargo_type: str, weight_tons: float, scheduled_date: str, status: str = "PENDING", ai_confidence: str = "LOW", ai_metadata: dict = None):
    now_iso = datetime.datetime.now(IST).isoformat()
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
            "confirmed_at": None if status == "PENDING" else now_iso,
            "loaded_at": None,
            "delivered_at": None,
            "delay_alerted": False,
            "created_at": now_iso,
            "updated_at": now_iso,
            "ai_confidence": ai_confidence,
            "ai_metadata": ai_metadata or {},
            "delay_risk_score": 0,
            "delay_risk_level": "Low"
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
            "status": status,
            "ai_confidence": ai_confidence,
            "ai_metadata": ai_metadata or {}
        }
        if status == "CONFIRMED":
            data["confirmed_at"] = now_iso
        res = supabase_client.table("shipments").insert(data).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"Error creating shipment: {e}")
        return handle_error(create_shipment, operator_id, truck_id, origin, destination, cargo_type, weight_tons, scheduled_date, status, ai_confidence, ai_metadata)

def get_shipment_by_id(shipment_id: str):
    if IS_MOCK:
        return MOCK_SHIPMENTS.get(shipment_id)
    try:
        res = supabase_client.table("shipments").select("*").eq("id", shipment_id).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"Error getting shipment by id: {e}")
        return handle_error(get_shipment_by_id, shipment_id)

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
                "operator": operator,
                "trucks": truck,
                "operators": operator
            })
        return details
    try:
        res = supabase_client.table("shipments").select("*, trucks(*), operators(*)").order("created_at", desc=True).execute()
        return res.data
    except Exception as e:
        logger.error(f"Error getting detailed shipments: {e}")
        return handle_error(get_shipments_with_details)

def update_shipment_status(
    shipment_id: str, 
    status: str, 
    ewb_draft_json: dict = None, 
    ewb_pdf_url: str = None,
    pod_status: str = None,
    pod_note: str = None,
    pod_media_url: str = None,
    pod_received_at: str = None,
    ai_confidence: str = None,
    ai_metadata: dict = None,
    delay_risk_score: int = None,
    delay_risk_level: str = None
):
    now_iso = datetime.datetime.now(IST).isoformat()
    if IS_MOCK:
        s = MOCK_SHIPMENTS.get(shipment_id)
        if s:
            s["status"] = status
            s["updated_at"] = now_iso
            if status == "CONFIRMED" and not s.get("confirmed_at"):
                s["confirmed_at"] = now_iso
            elif status == "LOADED" and not s.get("loaded_at"):
                s["loaded_at"] = now_iso
            elif status == "DELIVERED" and not s.get("delivered_at"):
                s["delivered_at"] = now_iso
            if ewb_draft_json is not None:
                s["ewb_draft_json"] = ewb_draft_json
            if ewb_pdf_url is not None:
                s["ewb_pdf_url"] = ewb_pdf_url
            if pod_status is not None:
                s["pod_status"] = pod_status
            if pod_note is not None:
                s["pod_note"] = pod_note
            if pod_media_url is not None:
                s["pod_media_url"] = pod_media_url
            if pod_received_at is not None:
                s["pod_received_at"] = pod_received_at
            if ai_confidence is not None:
                s["ai_confidence"] = ai_confidence
            if ai_metadata is not None:
                s["ai_metadata"] = ai_metadata
            if delay_risk_score is not None:
                s["delay_risk_score"] = delay_risk_score
            if delay_risk_level is not None:
                s["delay_risk_level"] = delay_risk_level
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
        if pod_status is not None:
            data["pod_status"] = pod_status
        if pod_note is not None:
            data["pod_note"] = pod_note
        if pod_media_url is not None:
            data["pod_media_url"] = pod_media_url
        if pod_received_at is not None:
            data["pod_received_at"] = pod_received_at
        if ai_confidence is not None:
            data["ai_confidence"] = ai_confidence
        if ai_metadata is not None:
            data["ai_metadata"] = ai_metadata
        if delay_risk_score is not None:
            data["delay_risk_score"] = delay_risk_score
        if delay_risk_level is not None:
            data["delay_risk_level"] = delay_risk_level
            
        res = supabase_client.table("shipments").update(data).eq("id", shipment_id).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"Error updating shipment: {e}")
        return handle_error(update_shipment_status, shipment_id, status, ewb_draft_json, ewb_pdf_url, pod_status, pod_note, pod_media_url, pod_received_at, ai_confidence, ai_metadata, delay_risk_score, delay_risk_level)


def get_active_shipment_for_operator(operator_id: str):
    active_statuses = [
        "PENDING", "CONFIRMING", "CONFIRMED", "DRIVER_PENDING_ACCEPTANCE", 
        "DRIVER_ACCEPTED", "DRIVER_REJECTED", "DRIVER_NOTIFY_FAILED", 
        "DOCUMENT_FAILED", "REASSIGNMENT_REQUIRED", "LOADED", "IN_TRANSIT", "DELAYED"
    ]
    if IS_MOCK:
        # Return most recent active shipment
        for s in reversed(list(MOCK_SHIPMENTS.values())):
            if s["operator_id"] == operator_id and s["status"] in active_statuses:
                return s
        return None
    try:
        res = supabase_client.table("shipments").select("*")\
            .eq("operator_id", operator_id)\
            .in_("status", active_statuses)\
            .order("created_at", desc=True).limit(1).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"Error getting active shipment for operator: {e}")
        return handle_error(get_active_shipment_for_operator, operator_id)

def get_active_shipment_for_driver(driver_phone: str):
    truck = get_truck_by_driver_phone(driver_phone)
    if not truck:
        return None
    
    active_statuses = ["DRIVER_PENDING_ACCEPTANCE", "DRIVER_ACCEPTED", "CONFIRMED", "LOADED", "IN_TRANSIT", "DELAYED"]
    if IS_MOCK:
        for s in reversed(list(MOCK_SHIPMENTS.values())):
            if s["truck_id"] == truck["id"] and s["status"] in active_statuses:
                return s
        return None
    try:
        res = supabase_client.table("shipments").select("*")\
            .eq("truck_id", truck["id"])\
            .in_("status", active_statuses)\
            .order("created_at", desc=True).limit(1).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"Error getting active shipment for driver: {e}")
        return handle_error(get_active_shipment_for_driver, driver_phone)

# --- Messages Operations ---

def log_message(phone_number: str, direction: str, body: str, shipment_id: str = None, message_sid: str = None):
    now_iso = datetime.datetime.now(IST).isoformat()
    if IS_MOCK:
        msg = {
            "id": f"msg_{len(MOCK_MESSAGES) + 1}",
            "phone_number": phone_number,
            "direction": direction,
            "body": body,
            "shipment_id": shipment_id,
            "timestamp": now_iso,
            "message_sid": message_sid
        }
        MOCK_MESSAGES.append(msg)
        return msg
    try:
        data = {
            "phone_number": phone_number,
            "direction": direction,
            "body": body,
            "shipment_id": shipment_id,
            "message_sid": message_sid
        }
        res = supabase_client.table("messages").insert(data).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"Error logging message: {e}")
        return handle_error(log_message, phone_number, direction, body, shipment_id, message_sid)

def is_message_processed(message_sid: str) -> bool:
    """Checks if a message with the given MessageSid has already been processed (idempotency)."""
    if not message_sid:
        return False
    if IS_MOCK:
        return any(m.get("message_sid") == message_sid for m in MOCK_MESSAGES)
    try:
        res = supabase_client.table("messages").select("id").eq("message_sid", message_sid).execute()
        return len(res.data) > 0
    except Exception as e:
        logger.error(f"Error checking message idempotency: {e}")
        return False

def get_all_messages():
    if IS_MOCK:
        return MOCK_MESSAGES
    try:
        res = supabase_client.table("messages").select("*").order("timestamp", desc=False).execute()
        return res.data
    except Exception as e:
        logger.error(f"Error getting all messages: {e}")
        return handle_error(get_all_messages)

# --- Conversation State Operations ---

def get_conversation_state(phone_number: str):
    if IS_MOCK:
        return MOCK_CONVERSATIONS.get(phone_number)
    try:
        res = supabase_client.table("conversation_state").select("*").eq("phone_number", phone_number).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"Error getting conversation state: {e}")
        return handle_error(get_conversation_state, phone_number)

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
        return handle_error(update_conversation_state, phone_number, last_intent, context_json, active_shipment_id)

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
        return handle_error(upload_ewb_pdf_bytes, shipment_id, pdf_bytes)

# --- Shipment Events (Timeline) Operations ---

def create_timeline_event(shipment_id: str = None, phone_number: str = None, event_type: str = "", title: str = "", description: str = None, metadata: dict = None):
    import datetime
    now_iso = datetime.datetime.now().isoformat()
    try:
        if IS_MOCK:
            event = {
                "id": f"evt_{len(MOCK_SHIPMENT_EVENTS) + 1}",
                "shipment_id": shipment_id,
                "phone_number": phone_number,
                "event_type": event_type,
                "title": title,
                "description": description,
                "metadata": metadata or {},
                "created_at": now_iso
            }
            MOCK_SHIPMENT_EVENTS.append(event)
            return event

        data = {
            "shipment_id": shipment_id,
            "phone_number": phone_number,
            "event_type": event_type,
            "title": title,
            "description": description,
            "metadata": metadata or {}
        }
        res = supabase_client.table("shipment_events").insert(data).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"Error logging timeline event {event_type}: {e}")
        # Safeguard: Fallback to mock log instead of crashing
        try:
            event = {
                "id": f"evt_fallback_{len(MOCK_SHIPMENT_EVENTS) + 1}",
                "shipment_id": shipment_id,
                "phone_number": phone_number,
                "event_type": event_type,
                "title": title,
                "description": description,
                "metadata": metadata or {},
                "created_at": now_iso
            }
            MOCK_SHIPMENT_EVENTS.append(event)
            return event
        except Exception:
            return None

def get_timeline_for_shipment(shipment_id: str):
    if IS_MOCK:
        return [evt for evt in MOCK_SHIPMENT_EVENTS if evt["shipment_id"] == shipment_id]
    try:
        res = supabase_client.table("shipment_events").select("*").eq("shipment_id", shipment_id).order("created_at", desc=False).execute()
        return res.data
    except Exception as e:
        logger.error(f"Error getting timeline for shipment {shipment_id}: {e}")
        return [evt for evt in MOCK_SHIPMENT_EVENTS if evt["shipment_id"] == shipment_id]

def get_recent_timeline_events(limit: int = 50):
    if IS_MOCK:
        return sorted(MOCK_SHIPMENT_EVENTS, key=lambda x: x["created_at"], reverse=True)[:limit]
    try:
        res = supabase_client.table("shipment_events").select("*").order("created_at", desc=True).limit(limit).execute()
        return res.data
    except Exception as e:
        logger.error(f"Error getting recent timeline events: {e}")
        return sorted(MOCK_SHIPMENT_EVENTS, key=lambda x: x["created_at"], reverse=True)[:limit]


# --- Notification Attempts Operations ---

def create_notification_attempt(to_phone: str, shipment_id: str, body: str, media_url: str = None, status: str = "PENDING", provider_sid: str = None, error_message: str = None):
    now_iso = datetime.datetime.now(IST).isoformat()
    if IS_MOCK:
        attempt_id = f"att_{len(MOCK_NOTIFICATION_ATTEMPTS) + 1}"
        attempt = {
            "id": attempt_id,
            "to_phone": to_phone,
            "shipment_id": shipment_id,
            "body": body,
            "media_url": media_url,
            "status": status,
            "provider_sid": provider_sid,
            "error_message": error_message,
            "created_at": now_iso,
            "updated_at": now_iso
        }
        MOCK_NOTIFICATION_ATTEMPTS[attempt_id] = attempt
        return attempt
    try:
        data = {
            "to_phone": to_phone,
            "shipment_id": shipment_id,
            "body": body,
            "media_url": media_url,
            "status": status,
            "provider_sid": provider_sid,
            "error_message": error_message
        }
        res = supabase_client.table("notification_attempts").insert(data).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"Error creating notification attempt: {e}")
        return handle_error(create_notification_attempt, to_phone, shipment_id, body, media_url, status, provider_sid, error_message)

def update_notification_attempt(attempt_id: str, status: str, provider_sid: str = None, error_message: str = None):
    now_iso = datetime.datetime.now(IST).isoformat()
    if IS_MOCK:
        att = MOCK_NOTIFICATION_ATTEMPTS.get(attempt_id)
        if att:
            att["status"] = status
            att["updated_at"] = now_iso
            if provider_sid is not None:
                att["provider_sid"] = provider_sid
            if error_message is not None:
                att["error_message"] = error_message
            return att
        return None
    try:
        data = {"status": status, "updated_at": now_iso}
        if provider_sid is not None:
            data["provider_sid"] = provider_sid
        if error_message is not None:
            data["error_message"] = error_message
        res = supabase_client.table("notification_attempts").update(data).eq("id", attempt_id).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"Error updating notification attempt: {e}")
        return handle_error(update_notification_attempt, attempt_id, status, provider_sid, error_message)

def get_failed_notifications():
    if IS_MOCK:
        return [att for att in MOCK_NOTIFICATION_ATTEMPTS.values() if att["status"] == "FAILED"]
    try:
        res = supabase_client.table("notification_attempts").select("*").eq("status", "FAILED").order("created_at", desc=True).execute()
        return res.data
    except Exception as e:
        logger.error(f"Error getting failed notification attempts: {e}")
        return [att for att in MOCK_NOTIFICATION_ATTEMPTS.values() if att["status"] == "FAILED"]

def get_notification_attempt_by_id(attempt_id: str):
    if IS_MOCK:
        return MOCK_NOTIFICATION_ATTEMPTS.get(attempt_id)
    try:
        res = supabase_client.table("notification_attempts").select("*").eq("id", attempt_id).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"Error getting notification attempt by id: {e}")
        return handle_error(get_notification_attempt_by_id, attempt_id)

def get_notifications_for_shipment(shipment_id: str):
    if IS_MOCK:
        return [att for att in MOCK_NOTIFICATION_ATTEMPTS.values() if att["shipment_id"] == shipment_id]
    try:
        res = supabase_client.table("notification_attempts").select("*").eq("shipment_id", shipment_id).order("created_at", desc=False).execute()
        return res.data
    except Exception as e:
        logger.error(f"Error getting notifications for shipment {shipment_id}: {e}")
        return [att for att in MOCK_NOTIFICATION_ATTEMPTS.values() if att["shipment_id"] == shipment_id]


# --- Manual Review Queue Operations ---

def create_review_item(phone_number: str, status: str = "OPEN", extracted_details: dict = None, missing_fields: list = None, latest_message: str = None):
    now_iso = datetime.datetime.now(IST).isoformat()
    if IS_MOCK:
        item_id = f"rev_{len(MOCK_REVIEW_ITEMS) + 1}"
        item = {
            "id": item_id,
            "phone_number": phone_number,
            "status": status,
            "extracted_details": extracted_details or {},
            "missing_fields": missing_fields or [],
            "latest_message": latest_message,
            "created_at": now_iso,
            "updated_at": now_iso
        }
        MOCK_REVIEW_ITEMS[item_id] = item
        return item
    try:
        data = {
            "phone_number": phone_number,
            "status": status,
            "extracted_details": extracted_details or {},
            "missing_fields": missing_fields or [],
            "latest_message": latest_message
        }
        res = supabase_client.table("booking_review_items").insert(data).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"Error creating review item: {e}")
        return handle_error(create_review_item, phone_number, status, extracted_details, missing_fields, latest_message)

def update_review_item(item_id: str, status: str = None, extracted_details: dict = None, missing_fields: list = None, latest_message: str = None):
    now_iso = datetime.datetime.now(IST).isoformat()
    if IS_MOCK:
        item = MOCK_REVIEW_ITEMS.get(item_id)
        if item:
            if status is not None:
                item["status"] = status
            if extracted_details is not None:
                item["extracted_details"] = extracted_details
            if missing_fields is not None:
                item["missing_fields"] = missing_fields
            if latest_message is not None:
                item["latest_message"] = latest_message
            item["updated_at"] = now_iso
            return item
        return None
    try:
        data = {"updated_at": now_iso}
        if status is not None:
            data["status"] = status
        if extracted_details is not None:
            data["extracted_details"] = extracted_details
        if missing_fields is not None:
            data["missing_fields"] = missing_fields
        if latest_message is not None:
            data["latest_message"] = latest_message
        res = supabase_client.table("booking_review_items").update(data).eq("id", item_id).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"Error updating review item: {e}")
        return handle_error(update_review_item, item_id, status, extracted_details, missing_fields, latest_message)

def get_open_review_items():
    if IS_MOCK:
        return [item for item in MOCK_REVIEW_ITEMS.values() if item["status"] == "OPEN"]
    try:
        res = supabase_client.table("booking_review_items").select("*").eq("status", "OPEN").order("created_at", desc=True).execute()
        return res.data
    except Exception as e:
        logger.error(f"Error getting open review items: {e}")
        return [item for item in MOCK_REVIEW_ITEMS.values() if item["status"] == "OPEN"]

def get_review_item_by_phone(phone_number: str):
    if IS_MOCK:
        for item in MOCK_REVIEW_ITEMS.values():
            if item["phone_number"] == phone_number and item["status"] == "OPEN":
                return item
        return None
    try:
        res = supabase_client.table("booking_review_items").select("*").eq("phone_number", phone_number).eq("status", "OPEN").execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"Error getting review item by phone: {e}")
        return None

def get_review_item_by_id(item_id: str):
    if IS_MOCK:
        return MOCK_REVIEW_ITEMS.get(item_id)
    try:
        res = supabase_client.table("booking_review_items").select("*").eq("id", item_id).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"Error getting review item by id: {e}")
        return handle_error(get_review_item_by_id, item_id)


