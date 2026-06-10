import json
import logging
from services import groq_service

logger = logging.getLogger(__name__)

def parse_status(message: str) -> dict:
    """Parses a driver's message to extract the trip status and notes."""
    system_prompt = (
        "You are an expert logistics coordinator parsing a truck driver's WhatsApp status updates.\n"
        "Drivers write messages in Hindi, Hinglish, or English.\n"
        "Classify the status into exactly ONE of the following categories:\n"
        "- LOADED: Truck has finished loading cargo at the origin (e.g. \"loaded ho gaya\", \"maal bhar diya\", \"loading done\").\n"
        "- IN_TRANSIT: Truck has departed the origin and is on the highway (e.g. \"nashik se nikal gaya\", \"route pe hoon\", \"on the way\").\n"
        "- DELIVERED: Cargo has successfully reached and discharged at the destination (e.g. \"mumbai pohonch gaya\", \"unloading ho gaya\", \"reached destination\", \"maal utar diya\").\n"
        "- DELAYED: Truck is stuck or delayed (e.g. \"engine kharab ho gaya\", \"accident ho gaya\", \"heavy traffic jam\").\n"
        "- UNKNOWN: The message does not communicate an actionable trip status update.\n\n"
        "Return ONLY a valid JSON object matching this schema. Do not write any explanations, markdown code blocks, or extra text:\n"
        "{\n"
        "  \"status\": \"LOADED\" | \"IN_TRANSIT\" | \"DELIVERED\" | \"DELAYED\" | \"UNKNOWN\",\n"
        "  \"note\": string (A short, clean description of the driver's message, translated to English if Hindi/Hinglish)\n"
        "}"
    )
    
    response = groq_service.chat_completion(system_prompt, message, max_tokens=128)
    
    def _clean_json_str(s: str) -> str:
        clean = s.strip()
        if clean.startswith("```json"):
            clean = clean[7:]
        elif clean.startswith("```"):
            clean = clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        return clean.strip()

    parsed = {}
    try:
        clean_response = _clean_json_str(response)
        parsed = json.loads(clean_response)
    except Exception as e:
        logger.warning(f"Initial JSON parsing of status update failed: {e}. Retrying with repair prompt...")
        repair_system_prompt = (
            "You are a strict JSON repair assistant. The user will provide a string that was supposed to be a valid JSON "
            "but failed to parse. Output ONLY a valid JSON object matching the schema below. "
            "Do not include any explanation or extra text.\n\n"
            "JSON Schema:\n"
            "{\n"
            "  \"status\": \"LOADED\" | \"IN_TRANSIT\" | \"DELIVERED\" | \"DELAYED\" | \"UNKNOWN\",\n"
            "  \"note\": string\n"
            "}"
        )
        repair_user_prompt = f"Invalid string: {response}\nError: {e}\nRepair and return valid JSON:"
        try:
            repair_response = groq_service.chat_completion(repair_system_prompt, repair_user_prompt, max_tokens=128)
            clean_repair = _clean_json_str(repair_response)
            parsed = json.loads(clean_repair)
        except Exception as retry_e:
            logger.error(f"Repair JSON parsing failed for status update: {retry_e}. Fallback to UNKNOWN.")
            parsed = {}

    # Verify keys
    if "status" not in parsed or "note" not in parsed:
        parsed = {"status": "UNKNOWN", "note": f"Failed to parse: {message}"}
        
    # Ensure status is valid
    valid_statuses = ["LOADED", "IN_TRANSIT", "DELIVERED", "DELAYED", "UNKNOWN"]
    if parsed.get("status") not in valid_statuses:
        parsed["status"] = "UNKNOWN"
        
    return parsed
