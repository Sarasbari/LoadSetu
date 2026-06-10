import json
import logging
from services import groq_service

logger = logging.getLogger(__name__)

def classify_intent(messages: list[str]) -> str:
    """Classifies the intent of the latest message in the conversation thread.
    
    messages: list of strings, with the last item being the most recent message.
    """
    if not messages:
        return "OTHER"
        
    current_message = messages[-1]
    history = messages[:-1]
    
    system_prompt = (
        "You are an expert freight coordination assistant for Indian MSME logistics.\n"
        "Classify the user's current message intent into exactly ONE of the following categories:\n"
        "1. NEW_BOOKING: User wants to book a new truck (e.g. \"Nashik se Mumbai pyaaz ke liye truck chahiye\", \"kal transport chahiye\").\n"
        "2. STATUS_UPDATE: Driver or operator is updating the status of a trip (e.g. \"loaded ho gaya\", \"nikal gaya\", \"pohonch gaya\", \"delivery completed\").\n"
        "3. CONFIRMATION: User is replying with a choice to confirm a truck option (e.g. \"1\", \"2\", \"3\", \"confirm first option\", \"pela walo ok\").\n"
        "4. QUERY: User is asking for status or information (e.g. \"mera truck kahan hai?\", \"is the truck available?\").\n"
        "5. OTHER: General greeting, chit-chat, or unrecognizable message (e.g. \"hi\", \"hello\", \"kya haal hai\").\n\n"
        "Return ONLY the intent word (NEW_BOOKING, STATUS_UPDATE, CONFIRMATION, QUERY, or OTHER). Nothing else."
    )
    
    user_prompt = ""
    if history:
        user_prompt += "Conversation Context:\n"
        for i, msg in enumerate(history):
            user_prompt += f"User message {i+1}: {msg}\n"
    user_prompt += f"Current User Message: {current_message}"
    
    response = groq_service.chat_completion(system_prompt, user_prompt, max_tokens=10)
    intent = response.strip().upper()
    
    # Validation fallback
    valid_intents = ["NEW_BOOKING", "STATUS_UPDATE", "CONFIRMATION", "QUERY", "OTHER"]
    for valid in valid_intents:
        if valid in intent:
            return valid
            
    return "OTHER"

def _clean_json_str(s: str) -> str:
    clean = s.strip()
    if clean.startswith("```json"):
        clean = clean[7:]
    elif clean.startswith("```"):
        clean = clean[3:]
    if clean.endswith("```"):
        clean = clean[:-3]
    return clean.strip()

def extract_freight_details(context: list[str], current_message: str) -> dict:
    """Extracts structured freight details from a natural language message and its conversation history."""
    import datetime
    IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    current_date_ist = datetime.datetime.now(IST).date().isoformat()
    
    system_prompt = (
        "You are a logistics assistant extracting freight booking details from informal Indian WhatsApp messages.\n"
        "Messages may be in Hindi, English, or Hinglish (Hindi written in Latin script).\n"
        "Analyze the conversation history and the current message to extract the following details.\n"
        "Return ONLY a valid JSON object. Do not write any explanations, markdown code blocks, or extra text.\n\n"
        "JSON Schema:\n"
        "{\n"
        "  \"origin\": string or null (Name of city where shipment starts, e.g. \"Nashik\", \"Surat\"),\n"
        "  \"destination\": string or null (Name of destination city, e.g. \"Mumbai\", \"Pune\"),\n"
        "  \"cargo_type\": string or null (Type of goods, e.g. \"Onions\", \"Textiles\", \"Chemicals\", \"Steel\"),\n"
        "  \"weight_tons\": number or null (Weight in metric tons, parse \"8 ton\" as 8.0, \"5000 kg\" as 5.0, etc.),\n"
        "  \"scheduled_date\": \"YYYY-MM-DD\" or null (Date of shipment. Parse \"kal\" relative to current date, \"aaj\"/\"today\" as current date),\n"
        "  \"special_requirements\": string or null (e.g., \"open body\", \"closed container\", \"no night driving\"),\n"
        "  \"confidence\": \"HIGH\" | \"MEDIUM\" | \"LOW\"\n"
        "}\n\n"
        "Rules:\n"
        "- Do not make up values. If origin, destination, cargo, weight, or date is missing, return null.\n"
        "- Resolve pronouns or references against conversation history (e.g., if history says \"pyaaz bhejna hai\" and current message says \"8 ton hai\", cargo_type is \"Onions\" and weight is 8.0).\n"
        f"- The current date is: {current_date_ist}. Use this to calculate relative dates like \"kal\" or \"parso\" relative to {current_date_ist}."
    )
    
    user_prompt = ""
    if context:
        user_prompt += "Conversation History:\n"
        for i, msg in enumerate(context):
            user_prompt += f"Message {i+1}: {msg}\n"
    user_prompt += f"Current Message: {current_message}"
    
    response = groq_service.chat_completion(system_prompt, user_prompt, max_tokens=256)
    
    # Parse JSON cleanly
    extracted = {}
    try:
        clean_response = _clean_json_str(response)
        extracted = json.loads(clean_response)
    except Exception as e:
        logger.warning(f"Initial JSON parsing failed: {e}. Retrying with repair prompt...")
        repair_system_prompt = (
            "You are a strict JSON repair assistant. The user will provide a string that was supposed to be a valid JSON "
            "but failed to parse. Output ONLY a valid JSON object matching the schema below. "
            "Do not include any explanation or extra text.\n\n"
            "JSON Schema:\n"
            "{\n"
            "  \"origin\": string or null,\n"
            "  \"destination\": string or null,\n"
            "  \"cargo_type\": string or null,\n"
            "  \"weight_tons\": number or null,\n"
            "  \"scheduled_date\": \"YYYY-MM-DD\" or null,\n"
            "  \"special_requirements\": string or null,\n"
            "  \"confidence\": \"HIGH\" | \"MEDIUM\" | \"LOW\"\n"
            "}"
        )
        repair_user_prompt = f"Invalid string: {response}\nError: {e}\nRepair and return valid JSON:"
        try:
            repair_response = groq_service.chat_completion(repair_system_prompt, repair_user_prompt, max_tokens=256)
            clean_repair = _clean_json_str(repair_response)
            extracted = json.loads(clean_repair)
        except Exception as retry_e:
            logger.error(f"Repair JSON parsing failed: {retry_e}. Fallback to empty details.")
            extracted = {}
        
    # Ensure all keys exist
    required_keys = ["origin", "destination", "cargo_type", "weight_tons", "scheduled_date", "special_requirements", "confidence"]
    for key in required_keys:
        if key not in extracted:
            extracted[key] = None
            
    # Set default confidence if missing
    if not extracted.get("confidence"):
        extracted["confidence"] = "LOW"
            
    return extracted
