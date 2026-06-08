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
    
    try:
        # Clean markdown wrappers if any
        clean_response = response.strip()
        if clean_response.startswith("```json"):
            clean_response = clean_response[7:]
        if clean_response.endswith("```"):
            clean_response = clean_response[:-3]
        clean_response = clean_response.strip()
        
        parsed = json.loads(clean_response)
        
        # Verify keys
        if "status" not in parsed or "note" not in parsed:
            parsed = {"status": "UNKNOWN", "note": "Failed to parse required keys"}
            
        # Ensure status is valid
        valid_statuses = ["LOADED", "IN_TRANSIT", "DELIVERED", "DELAYED", "UNKNOWN"]
        if parsed["status"] not in valid_statuses:
            parsed["status"] = "UNKNOWN"
            
        return parsed
    except Exception as e:
        logger.error(f"Error parsing status update: {e}. Raw response: {response}")
        return {
            "status": "UNKNOWN",
            "note": f"Error parsing: {message}"
        }
