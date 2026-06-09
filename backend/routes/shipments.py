import os
from fastapi import APIRouter, Header, HTTPException, status, Path
from services import supabase_service

router = APIRouter(prefix="/shipments", tags=["shipments"])

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
async def get_shipments(page: int = 1, limit: int = 20, authorization: str = Header(None)):
    """GET /shipments - Returns paginated shipments with joined operator and truck details (requires Admin token)."""
    await verify_admin_token(authorization)
    
    # Retrieve all detailed shipments
    detailed_shipments = supabase_service.get_shipments_with_details()
    
    # Apply manual pagination
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    paginated_shipments = detailed_shipments[start_idx:end_idx]
    
    return {
        "shipments": paginated_shipments,
        "total": len(detailed_shipments),
        "page": page,
        "limit": limit
    }

@router.get("/{shipment_id}/timeline")
async def get_shipment_timeline(
    shipment_id: str = Path(...),
    authorization: str = Header(None)
):
    """GET /shipments/{shipment_id}/timeline - Returns chronological timeline events for a shipment."""
    await verify_admin_token(authorization)
    events = supabase_service.get_timeline_for_shipment(shipment_id)
    return {"timeline": events}

