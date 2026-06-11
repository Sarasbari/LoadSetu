from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
import re

# Shipment Statuses
VALID_STATUSES = {
    "PENDING",
    "CONFIRMING",
    "CONFIRMED",
    "DOCUMENT_FAILED",
    "DRIVER_NOTIFY_FAILED",
    "DRIVER_PENDING_ACCEPTANCE",
    "DRIVER_ACCEPTED",
    "DRIVER_REJECTED",
    "REASSIGNMENT_REQUIRED",
    "LOADED",
    "IN_TRANSIT",
    "DELIVERED",
    "DELAYED",
    "CANCELLED"
}

# Validation Patterns
INDIAN_PHONE_PATTERN = r'^\+91[6-9]\d{9}$'
INDIAN_TRUCK_NUMBER_PATTERN = r'^[A-Z]{2}-\d{2}-[A-Z]{1,2}-\d{4}$'
GSTIN_PATTERN = r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$'

class ShipmentStatusTransitionHelper:
    """Helper class to validate shipment status transitions."""
    
    # Allowed transitions mapping: old_status -> set of allowed new_statuses
    ALLOWED_TRANSITIONS = {
        "PENDING": {"CONFIRMING", "CANCELLED"},
        "CONFIRMING": {"CONFIRMED", "DOCUMENT_FAILED", "CANCELLED"},
        "DOCUMENT_FAILED": {"CONFIRMING", "CANCELLED"},
        "CONFIRMED": {"DRIVER_PENDING_ACCEPTANCE", "DRIVER_NOTIFY_FAILED", "CANCELLED"},
        "DRIVER_NOTIFY_FAILED": {"DRIVER_PENDING_ACCEPTANCE", "CANCELLED", "REASSIGNMENT_REQUIRED"},
        "DRIVER_PENDING_ACCEPTANCE": {"DRIVER_ACCEPTED", "DRIVER_REJECTED", "LOADED", "CANCELLED"},
        "DRIVER_ACCEPTED": {"LOADED", "CANCELLED"},
        "DRIVER_REJECTED": {"REASSIGNMENT_REQUIRED", "CANCELLED"},
        "REASSIGNMENT_REQUIRED": {"DRIVER_PENDING_ACCEPTANCE", "CANCELLED"},
        "LOADED": {"IN_TRANSIT", "DELAYED", "CANCELLED"},
        "IN_TRANSIT": {"DELIVERED", "DELAYED", "CANCELLED"},
        "DELAYED": {"LOADED", "IN_TRANSIT", "DELIVERED", "CANCELLED"},
        "DELIVERED": set(),  # Terminal state
        "CANCELLED": set()   # Terminal state
    }
    
    @classmethod
    def is_transition_valid(cls, old_status: str, new_status: str) -> bool:
        old_status = old_status.upper()
        new_status = new_status.upper()
        
        if old_status not in VALID_STATUSES or new_status not in VALID_STATUSES:
            return False
            
        if old_status == new_status:
            return True
            
        # Support overriding status transitions in case of admin forcing, but log warnings.
        # Here we enforce the transition rules strictly.
        allowed = cls.ALLOWED_TRANSITIONS.get(old_status, set())
        return new_status in allowed


class TruckCreate(BaseModel):
    driver_name: str = Field(..., min_length=2, max_length=100)
    driver_phone: str = Field(..., pattern=INDIAN_PHONE_PATTERN)
    truck_number: str = Field(..., pattern=INDIAN_TRUCK_NUMBER_PATTERN)
    truck_type: str = Field(..., pattern=r'^(open|closed|refrigerated|flatbed)$')
    capacity_tons: float = Field(..., gt=0.1, lt=100.0)
    home_city: str = Field(..., min_length=2, max_length=100)
    notes: Optional[str] = None

class ShipmentCreate(BaseModel):
    operator_id: str
    truck_id: str
    origin: str = Field(..., min_length=2, max_length=100)
    destination: str = Field(..., min_length=2, max_length=100)
    cargo_type: str = Field(..., min_length=2, max_length=100)
    weight_tons: float = Field(..., gt=0.1, lt=100.0)
    scheduled_date: str
    status: str = "PENDING"
    
    @field_validator('status')
    def validate_status(cls, v):
        if v.upper() not in VALID_STATUSES:
            raise ValueError(f"Invalid shipment status: {v}")
        return v.upper()

class NotificationAttemptCreate(BaseModel):
    to_phone: str = Field(..., pattern=INDIAN_PHONE_PATTERN)
    shipment_id: Optional[str] = None
    body: str
    media_url: Optional[str] = None
    status: str = "PENDING"
    provider_sid: Optional[str] = None
    error_message: Optional[str] = None

class ReviewItemAction(BaseModel):
    action: str = Field(..., pattern=r'^(resolve|dismiss)$')
    notes: Optional[str] = None
