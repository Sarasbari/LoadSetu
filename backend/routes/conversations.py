from fastapi import APIRouter, Header, HTTPException, status, Path
from services import supabase_service
from routes.shipments import verify_admin_token

router = APIRouter(prefix="/conversations", tags=["conversations"])

@router.get("")
async def get_conversations(page: int = 1, limit: int = 20, authorization: str = Header(None)):
    """GET /conversations - Returns unique conversations grouped by phone number (requires Admin token)."""
    await verify_admin_token(authorization)
    
    if page < 1:
        page = 1
    if limit < 1:
        limit = 20
    elif limit > 100:
        limit = 100
        
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
    
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    paginated_threads = sorted_threads[start_idx:end_idx]
    
    return {
        "conversations": paginated_threads,
        "total": len(sorted_threads),
        "page": page,
        "limit": limit
    }


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
