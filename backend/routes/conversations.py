import os
from fastapi import APIRouter, Header, HTTPException, status, Path
from services import supabase_service

router = APIRouter(prefix="/conversations", tags=["conversations"])

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "secret_admin_token_2026")

async def verify_admin_token(authorization: str):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header"
        )
    token = authorization.split(" ")[1]
    if token != ADMIN_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin token"
        )

@router.get("")
async def get_conversations(authorization: str = Header(None)):
    """GET /conversations - Returns unique conversations grouped by phone number (requires Admin token)."""
    await verify_admin_token(authorization)
    
    all_messages = supabase_service.get_all_messages()
    
    # Group messages by phone number and find the latest message per thread
    threads = {}
    for msg in all_messages:
        phone = msg.get("phone_number")
        if not phone:
            continue
            
        timestamp = msg.get("timestamp", "")
        body = msg.get("body", "")
        direction = msg.get("direction", "INBOUND")
        
        if phone not in threads:
            threads[phone] = {
                "phone_number": phone,
                "last_message": body,
                "last_timestamp": timestamp,
                "last_direction": direction,
                "message_count": 0
            }
            
        threads[phone]["message_count"] += 1
        
        # Check if this message is newer
        if timestamp > threads[phone]["last_timestamp"]:
            threads[phone]["last_message"] = body
            threads[phone]["last_timestamp"] = timestamp
            threads[phone]["last_direction"] = direction
            
    # Sort threads by latest message timestamp descending
    sorted_threads = sorted(threads.values(), key=lambda x: x["last_timestamp"], reverse=True)
    return {"conversations": sorted_threads}

@router.get("/{phone_number}")
async def get_conversation_thread(
    phone_number: str = Path(...),
    authorization: str = Header(None)
):
    """GET /conversations/{phone_number} - Returns chronological message thread for a phone number (requires Admin token)."""
    await verify_admin_token(authorization)
    
    all_messages = supabase_service.get_all_messages()
    
    # Filter for this phone number
    thread = [m for m in all_messages if m.get("phone_number") == phone_number]
    
    # Sort chronologically (ascending)
    thread.sort(key=lambda x: x.get("timestamp", ""))
    
    return {"thread": thread}
