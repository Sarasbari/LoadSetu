from pydantic import BaseModel, Field
from typing import Optional

class TruckCreate(BaseModel):
    driver_name: str = Field(..., min_length=2, max_length=100)
    driver_phone: str = Field(..., pattern=r'^\+?[1-9]\d{1,14}$')  # Valid E.164 phone number
    truck_number: str = Field(..., pattern=r'^[A-Z]{2}-\d{2}-[A-Z]{1,2}-\d{4}$')  # Valid Indian truck number MH-12-AB-1234
    truck_type: str = Field(..., pattern=r'^(open|closed|refrigerated|flatbed)$')
    capacity_tons: float = Field(..., gt=0, lt=100.0)
    home_city: str = Field(..., min_length=2, max_length=100)
    notes: Optional[str] = None

class TruckAvailabilityUpdate(BaseModel):
    is_available: bool
    current_city: Optional[str] = None
