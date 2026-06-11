import os
from fastapi import APIRouter, Header, HTTPException, status, Path
from pydantic import BaseModel
from services import supabase_service
from routes.shipments import verify_admin_token
from models.domain import ReviewItemAction

router = APIRouter(prefix="/review-items", tags=["review-items"])

@router.get("")
async def get_review_items(authorization: str = Header(None)):
    """GET /review-items - Returns all OPEN manual review queue items (requires Admin token)."""
    await verify_admin_token(authorization)
    items = supabase_service.get_open_review_items()
    return {"review_items": items}

@router.post("/{item_id}/resolve")
async def resolve_review_item(
    item_id: str = Path(...),
    action_data: ReviewItemAction = None,
    authorization: str = Header(None)
):
    """POST /review-items/{id}/resolve - Marks a low-confidence review item as RESOLVED (requires Admin token)."""
    await verify_admin_token(authorization)
    
    item = supabase_service.get_review_item_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
        
    updated = supabase_service.update_review_item(item_id=item_id, status="RESOLVED")
    return {"message": "Review item resolved", "review_item": updated}

@router.post("/{item_id}/dismiss")
async def dismiss_review_item(
    item_id: str = Path(...),
    authorization: str = Header(None)
):
    """POST /review-items/{id}/dismiss - Marks a low-confidence review item as DISMISSED (requires Admin token)."""
    await verify_admin_token(authorization)
    
    item = supabase_service.get_review_item_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
        
    updated = supabase_service.update_review_item(item_id=item_id, status="DISMISSED")
    return {"message": "Review item dismissed", "review_item": updated}
