from fastapi import APIRouter, Header, HTTPException, status, Path
from services import supabase_service
from models.truck import TruckCreate, TruckAvailabilityUpdate
from routes.shipments import verify_admin_token

router = APIRouter(prefix="/trucks", tags=["trucks"])

@router.get("")
async def get_trucks(page: int = 1, limit: int = 20, authorization: str = Header(None)):
    """GET /trucks - Returns paginated list of all trucks (requires Admin token)."""
    await verify_admin_token(authorization)
    
    if page < 1:
        page = 1
    if limit < 1:
        limit = 20
    elif limit > 100:
        limit = 100
        
    all_trucks = supabase_service.get_all_trucks()
    
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    paginated_trucks = all_trucks[start_idx:end_idx]
    
    return {
        "trucks": paginated_trucks,
        "total": len(all_trucks),
        "page": page,
        "limit": limit
    }


@router.post("")
async def create_truck(truck_data: TruckCreate, authorization: str = Header(None)):
    """POST /trucks - Adds a new truck to the registry (requires Admin token)."""
    await verify_admin_token(authorization)
    
    # Check if truck already exists
    # For MVP we can just call create
    new_truck = supabase_service.create_truck(
        driver_name=truck_data.driver_name,
        driver_phone=truck_data.driver_phone,
        truck_number=truck_data.truck_number,
        truck_type=truck_data.truck_type,
        capacity_tons=truck_data.capacity_tons,
        home_city=truck_data.home_city,
        notes=truck_data.notes
    )
    
    if not new_truck:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register truck in database"
        )
        
    return {"message": "Truck registered successfully", "truck": new_truck}

@router.put("/{truck_id}/availability")
async def update_truck_availability(
    truck_data: TruckAvailabilityUpdate,
    truck_id: str = Path(...),
    authorization: str = Header(None)
):
    """PUT /trucks/{id}/availability - Updates availability and location (requires Admin token)."""
    await verify_admin_token(authorization)
    
    updated = supabase_service.update_truck_availability(
        truck_id=truck_id,
        is_available=truck_data.is_available,
        current_city=truck_data.current_city
    )
    
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Truck not found or update failed"
        )
        
    return {"message": "Truck availability updated", "truck": updated}
