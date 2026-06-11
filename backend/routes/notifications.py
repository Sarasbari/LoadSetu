import os
from fastapi import APIRouter, Header, HTTPException, status, Path
from services import supabase_service, notification_service
from routes.shipments import verify_admin_token

router = APIRouter(prefix="/notifications", tags=["notifications"])

@router.get("/failed")
async def get_failed_notifications(authorization: str = Header(None)):
    """GET /notifications/failed - Returns a list of failed notification attempts (requires Admin token)."""
    await verify_admin_token(authorization)
    failed_attempts = supabase_service.get_failed_notifications()
    return {"failed_notifications": failed_attempts}

@router.post("/{attempt_id}/retry")
async def retry_failed_notification(
    attempt_id: str = Path(...),
    authorization: str = Header(None)
):
    """POST /notifications/{id}/retry - Retries sending a failed notification (requires Admin token)."""
    await verify_admin_token(authorization)
    
    # 1. Fetch attempt
    attempt = supabase_service.get_notification_attempt_by_id(attempt_id)
    if not attempt:
        raise HTTPException(status_code=404, detail="Notification attempt not found")
        
    # 2. Retry sending
    success = notification_service.retry_notification(attempt_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Retry failed"
        )
        
    return {"message": "Notification retry triggered successfully", "status": "SENT"}
