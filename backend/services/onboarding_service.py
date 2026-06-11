import logging
import re
from services import supabase_service, notification_service, timeline_service
from utils import conversation_state

logger = logging.getLogger(__name__)

def handle_onboarding_step(from_whatsapp: str, clean_phone: str, body: str, step: str, state: dict, operator: dict):
    """Handles the sequential WhatsApp onboarding steps for operators."""
    if step == "business_name":
        business_name = body.strip()
        if len(business_name) < 2 or len(business_name) > 100:
            reply = "⚠️ Business Name 2 se 100 characters ke beech hona chahiye. Kripya fir se likhein."
            notification_service.send_whatsapp(from_whatsapp, reply)
            return
            
        supabase_service.update_operator(clean_phone, business_name=business_name)
        state["context_json"]["onboarding_step"] = "gst_number"
        conversation_state.update_state(clean_phone, "ONBOARDING", booking_details=state["context_json"])
        
        reply = "Dhanyawad! Ab apna GSTIN (GST Number) bhejein. Agar nahi hai, toh 'skip' likhein."
        notification_service.send_whatsapp(from_whatsapp, reply)
        
    elif step == "gst_number":
        gst_num = body.strip().upper()
        if gst_num.lower() != "skip":
            gst_pattern = r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$'
            if not re.match(gst_pattern, gst_num):
                reply = "⚠️ Invalid GSTIN format. Kripya 15-digit ka valid GSTIN bhejein ya 'skip' likhein."
                notification_service.send_whatsapp(from_whatsapp, reply)
                return
            supabase_service.update_operator(clean_phone, gst_number=gst_num)
            
        state["context_json"]["onboarding_step"] = "city"
        conversation_state.update_state(clean_phone, "ONBOARDING", booking_details=state["context_json"])
        
        reply = "Aapka city (Shahar) kaunsa hai? Shahar ka naam likh kar bhejein."
        notification_service.send_whatsapp(from_whatsapp, reply)
        
    elif step == "city":
        city = body.strip()
        if not re.match(r'^[a-zA-Z\s\.\-]{2,50}$', city):
            reply = "⚠️ Shahar ka naam invalid hai. Kripya sahi shahar ka naam (sirf letters) likhein."
            notification_service.send_whatsapp(from_whatsapp, reply)
            return
            
        # Refetch operator details to get business name
        op_updated = supabase_service.get_operator_by_phone(clean_phone)
        bus_name = op_updated.get("business_name") if op_updated else None
        
        supabase_service.update_operator(clean_phone, city=city, name="Operator", onboarding_status="COMPLETED")
        state["context_json"]["onboarding_step"] = "completed"
        
        # Reset state to OTHER for normal booking
        conversation_state.update_state(clean_phone, "OTHER", booking_details=state["context_json"])
        
        # Log timeline event
        timeline_service.log_event(
            shipment_id=None,
            phone_number=clean_phone,
            event_type="operator_onboarded",
            title="Operator Onboarded",
            description=f"Operator onboarded successfully. Business Name: {bus_name or 'N/A'}, City: {city}"
        )
        
        reply = (
            "Aapka onboarding safaltapoorvak ho gaya hai! 🎉\n"
            "Ab aap truck book kar sakte hain. Example:\n"
            "\"Surat se Mumbai 8 ton textiles kal ke liye\""
        )
        notification_service.send_whatsapp(from_whatsapp, reply)
