import os
import json
import logging
import time
from groq import Groq

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Check if using mock mode
IS_MOCK_GROQ = not GROQ_API_KEY or GROQ_API_KEY.startswith("gsk_0000") or "dummy" in GROQ_API_KEY

groq_client = None
if not IS_MOCK_GROQ:
    try:
        groq_client = Groq(api_key=GROQ_API_KEY)
        logger.info("Groq client initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize Groq client: {e}")
        IS_MOCK_GROQ = True

def chat_completion(system_prompt: str, user_message: str, max_tokens: int = 512, response_format: dict = None) -> str:
    """Calls Groq API with retries for rate limits and timeout. Falls back to mock if needed."""
    if IS_MOCK_GROQ:
        logger.info("Groq API mock active. Simulating LLM response.")
        return get_mock_response(system_prompt, user_message)
        
    retries = 1
    for attempt in range(retries + 1):
        try:
            kwargs = {
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                "temperature": 0.1,
                "max_tokens": max_tokens,
            }
            if response_format:
                kwargs["response_format"] = response_format
                
            completion = groq_client.chat.completions.create(**kwargs)
            return completion.choices[0].message.content
        except Exception as e:
            # Check for rate limit or similar retryable errors
            if "rate_limit" in str(e).lower() or "too many requests" in str(e).lower():
                if attempt < retries:
                    logger.warning(f"Groq Rate limit hit. Retrying in 2 seconds... (Attempt {attempt+1})")
                    time.sleep(2)
                    continue
            logger.error(f"Groq API Error: {e}")
            # Fallback to mock on error so the app doesn't crash
            return get_mock_response(system_prompt, user_message)
            
    return get_mock_response(system_prompt, user_message)

def get_mock_response(system_prompt: str, user_message: str) -> str:
    """Helper to mock Groq intelligence for local/offline testing and demo robustness."""
    user_msg_lower = user_message.lower()
    
    # 1. Intent Classification Mocking
    if "current message intent" in system_prompt.lower() or "intent" in system_prompt.lower():
        import re
        
        # Extract just the current message from the formatted prompt
        # The prompt format is: "...Current User Message: <message>"
        current_msg = user_message
        current_msg_match = re.search(r'Current User Message:\s*(.+?)$', user_message, re.MULTILINE | re.DOTALL)
        if current_msg_match:
            current_msg = current_msg_match.group(1).strip()
        current_msg_lower = current_msg.lower()
        
        # Check confirmation first (high priority for options)
        if current_msg.strip() in ["1", "2", "3"] or "confirm" in current_msg_lower:
            return "CONFIRMATION"
            
        # Check query
        elif "status" in current_msg_lower or "kahan" in current_msg_lower or "where" in current_msg_lower:
            return "QUERY"
            
        # Check status updates (check with specific phrases to avoid matching booking load)
        elif "loaded" in current_msg_lower or "load ho" in current_msg_lower or "load done" in current_msg_lower or "nikal" in current_msg_lower or "pohonch" in current_msg_lower or "pahunch" in current_msg_lower or "kharab" in current_msg_lower or "delivered" in current_msg_lower:
            return "STATUS_UPDATE"
            
        # Check new booking
        elif "booking" in current_msg_lower or re.search(r'\bse\b', current_msg_lower) or "ton" in current_msg_lower or "truck" in current_msg_lower or "chahiye" in current_msg_lower or "transport" in current_msg_lower:
            # Prevent greetings from matching as booking (e.g. "namaste sir kaise ho" contains "se" in "kaise")
            is_greeting = (
                "namaste" in current_msg_lower 
                or "hello" in current_msg_lower 
                or re.search(r'\bhi\b', current_msg_lower)
            )
            if is_greeting:
                if not ("se" in current_msg_lower and "ton" in current_msg_lower):
                    return "OTHER"
            return "NEW_BOOKING"
            
        else:
            return "OTHER"
            
    # 2. Status Parsing Mocking
    if "status updates" in system_prompt.lower() or "status" in system_prompt.lower():
        status = "UNKNOWN"
        note = "Unrecognized status update"
        if "loaded" in user_msg_lower or "load ho" in user_msg_lower or "bhara" in user_msg_lower:
            status = "LOADED"
            note = "Cargo loaded at origin"
        elif "nikal" in user_msg_lower or "transit" in user_msg_lower or "mumbai ke liye" in user_msg_lower or "rasta" in user_msg_lower:
            status = "IN_TRANSIT"
            note = "In transit to destination"
        elif "pohonch" in user_msg_lower or "pahunch" in user_msg_lower or "reached" in user_msg_lower or "deliver" in user_msg_lower:
            status = "DELIVERED"
            note = "Delivered successfully"
        elif "kharab" in user_msg_lower or "delay" in user_msg_lower or "accident" in user_msg_lower or "jam" in user_msg_lower:
            status = "DELAYED"
            note = "Delayed due to issue reported: " + user_message
            
        return json.dumps({"status": status, "note": note})
        
    # 3. Detail Extraction Mocking
    if "extracting" in system_prompt.lower() or "details" in system_prompt.lower():
        # Default extraction
        data = {
            "origin": None,
            "destination": None,
            "cargo_type": None,
            "weight_tons": None,
            "scheduled_date": None,
            "special_requirements": None,
            "confidence": "LOW"
        }
        
        # Extrapolate locations
        if "nashik" in user_msg_lower:
            data["origin"] = "Nashik"
        elif "surat" in user_msg_lower:
            data["origin"] = "Surat"
            
        if "mumbai" in user_msg_lower:
            data["destination"] = "Mumbai"
        elif "pune" in user_msg_lower:
            data["destination"] = "Pune"
            
        # If origin/destination missing, search for standard pairs
        if not data["origin"] and "se" in user_msg_lower:
            parts = user_msg_lower.split("se")
            # Word before "se"
            words = parts[0].strip().split()
            if words:
                data["origin"] = words[-1].capitalize()
        if not data["destination"] and "ko" in user_msg_lower:
            parts = user_msg_lower.split("ko")
            words = parts[0].strip().split()
            if words:
                data["destination"] = words[-1].capitalize()
        elif not data["destination"] and "se" in user_msg_lower:
            parts = user_msg_lower.split("se")
            if len(parts) > 1:
                dest_words = parts[1].strip().split()
                if dest_words:
                    data["destination"] = dest_words[0].replace("tak", "").capitalize()

        # Cargo
        if "pyaaz" in user_msg_lower or "onion" in user_msg_lower:
            data["cargo_type"] = "Onions"
        elif "kapda" in user_msg_lower or "textile" in user_msg_lower or "fabric" in user_msg_lower:
            data["cargo_type"] = "Textiles"
        elif "chemical" in user_msg_lower:
            data["cargo_type"] = "Chemicals"
        elif "steel" in user_msg_lower:
            data["cargo_type"] = "Steel"
            
        # Weight
        import re
        weight_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:ton|t|tan)', user_msg_lower)
        if weight_match:
            data["weight_tons"] = float(weight_match.group(1))
            
        # Date
        if "kal" in user_msg_lower or "tomorrow" in user_msg_lower:
            import datetime
            tomorrow = datetime.date.today() + datetime.timedelta(days=1)
            data["scheduled_date"] = tomorrow.isoformat()
        elif "aaj" in user_msg_lower or "today" in user_msg_lower:
            import datetime
            data["scheduled_date"] = datetime.date.today().isoformat()
            
        # Context-based matching for follow-ups (e.g. "8 ton hai")
        # In actual conversation, history is stored in user_message.
        # If user says just a number, assign to weight
        clean_num = user_message.strip().replace("ton", "").replace("t", "").strip()
        if clean_num.isdigit():
            data["weight_tons"] = float(clean_num)
            
        # Set confidence
        if data["origin"] and data["destination"]:
            data["confidence"] = "HIGH" if data["cargo_type"] and data["weight_tons"] else "MEDIUM"
            
        return json.dumps(data)

    # 4. Default Mock
    return "MOCK_RESPONSE"
