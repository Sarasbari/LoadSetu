import logging
from services import supabase_service

logger = logging.getLogger(__name__)

def get_state(phone: str) -> dict:
    """Retrieves conversation state for a phone number. Returns default state if none exists."""
    state = supabase_service.get_conversation_state(phone)
    if not state:
        return {
            "phone_number": phone,
            "last_intent": "OTHER",
            "context_json": {
                "history": [],
                "matched_trucks": []
            },
            "active_shipment_id": None
        }
    
    # Ensure context_json is structured correctly
    context = state.get("context_json")
    if not isinstance(context, dict):
        # Convert legacy list format to dictionary format
        history = context if isinstance(context, list) else []
        state["context_json"] = {
            "history": history,
            "matched_trucks": []
        }
    else:
        if "history" not in context:
            context["history"] = []
        if "matched_trucks" not in context:
            context["matched_trucks"] = []
            
    return state

def update_state(phone: str, last_intent: str, new_message: str = None, matched_trucks: list = None, active_shipment_id: str = None) -> dict:
    """Updates the conversation state with new messages and/or matched truck data."""
    state = get_state(phone)
    
    shipment_id = active_shipment_id or state.get("active_shipment_id")
    context = state["context_json"]
    
    # Append message to history if provided
    if new_message:
        context["history"].append(new_message)
        # Keep history capped at 5 messages
        if len(context["history"]) > 5:
            context["history"] = context["history"][-5:]
            
    # Update matched trucks if provided
    if matched_trucks is not None:
        context["matched_trucks"] = matched_trucks
        
    updated_state = supabase_service.update_conversation_state(
        phone_number=phone,
        last_intent=last_intent,
        context_json=context,
        active_shipment_id=shipment_id
    )
    
    return updated_state

def clear_state(phone: str):
    """Resets message history and matching details for a fresh conversation, retaining the active shipment."""
    state = get_state(phone)
    supabase_service.update_conversation_state(
        phone_number=phone,
        last_intent="OTHER",
        context_json={
            "history": [],
            "matched_trucks": []
        },
        active_shipment_id=state.get("active_shipment_id")
    )
