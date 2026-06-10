import os
from fastapi import APIRouter, Header, HTTPException, status, Path
from services import supabase_service, pdf_service
from utils.delay_checker import calculate_delay_risk

router = APIRouter(prefix="/shipments", tags=["shipments"])

async def verify_admin_token(authorization: str):
    app_env = os.getenv("APP_ENV", "development")
    admin_token = os.getenv("ADMIN_TOKEN")
    
    if app_env == "production" and (not admin_token or admin_token == "secret_admin_token_2026"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server configuration error: Secure ADMIN_TOKEN must be configured in production"
        )
        
    expected_token = admin_token or "secret_admin_token_2026"
    
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header"
        )
    token = authorization.split(" ")[1]
    if token != expected_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin token"
        )

@router.get("")
async def get_shipments(page: int = 1, limit: int = 20, authorization: str = Header(None)):
    """GET /shipments - Returns paginated shipments with joined operator and truck details (requires Admin token)."""
    await verify_admin_token(authorization)
    
    # Validation / pagination bounds
    if page < 1:
        page = 1
    if limit < 1:
        limit = 20
    elif limit > 100:
        limit = 100
        
    # Retrieve all detailed shipments
    detailed_shipments = supabase_service.get_shipments_with_details()
    
    # Dynamically compute and attach delay risk score & level
    for s in detailed_shipments:
        risk = calculate_delay_risk(s)
        s["delay_risk_score"] = risk["score"]
        s["delay_risk_level"] = risk["level"]
        s["delay_risk_reasons"] = risk["reasons"]
        
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

@router.post("/{shipment_id}/dispute-pack")
async def generate_dispute_pack(
    shipment_id: str = Path(...),
    authorization: str = Header(None)
):
    """POST /shipments/{shipment_id}/dispute-pack - Generates a verifiable dispute packet PDF."""
    await verify_admin_token(authorization)
    
    # 1. Fetch shipment details
    shipment = supabase_service.get_shipment_by_id(shipment_id)
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
        
    # 2. Fetch Operator details
    operator = supabase_service.get_operator_by_id(shipment.get("operator_id"))
    if not operator:
        operator = {"name": "Unknown Operator", "phone": "N/A", "business_name": "N/A", "city": "N/A"}
        
    # 3. Fetch Truck details
    truck = supabase_service.get_truck_by_id(shipment.get("truck_id"))
    if not truck:
        truck = {"driver_name": "Unknown Driver", "driver_phone": "N/A", "truck_number": "N/A"}
        
    # 4. Fetch Timeline Events
    events = supabase_service.get_timeline_for_shipment(shipment_id)
    
    # 5. Fetch Chat Messages (retrieve all messages, we will filter within the generator)
    messages = supabase_service.get_all_messages()
    
    # 6. Generate PDF and get URL
    try:
        pdf_url = pdf_service.generate_dispute_pack_pdf(
            shipment=shipment,
            operator=operator,
            truck=truck,
            events=events,
            messages=messages
        )
        return {"pdf_url": pdf_url}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate dispute packet PDF: {e}"
        )


