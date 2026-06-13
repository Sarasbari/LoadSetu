import logging

logger = logging.getLogger(__name__)

# Standard Indian HSN Codes for common cargo types
HSN_CODES = {
    "onion": "07031010",
    "onions": "07031010",
    "pyaaz": "07031010",
    "potato": "07019000",
    "potatoes": "07019000",
    "aaloo": "07019000",
    "vegetable": "07099990",
    "vegetables": "07099990",
    "sabzi": "07099990",
    "textile": "54071019",
    "textiles": "54071019",
    "fabric": "54071019",
    "kapda": "54071019",
    "chemical": "38249999",
    "chemicals": "38249999",
    "steel": "72081000",
    "iron": "72081000",
    "cement": "25232910",
    "grain": "10019900",
    "grains": "10019900",
    "wheat": "10019900",
    "rice": "10063010",
    "coal": "27011100",
    "electronic": "85176290",
    "electronics": "85176290",
    "sugar": "17011190",
    "chini": "17011190",
    "cotton": "52010015",
    "ruyi": "52010015",
    "fertilizer": "31021000",
    "khad": "31021000",
    "plastic": "39159090",
    "plastics": "39159090",
    "fruit": "08109090",
    "fruits": "08109090",
    "phhal": "08109090",
}

# Estimated values in INR per ton for different cargo types
VALUE_PER_TON = {
    "onion": 40000,
    "onions": 40000,
    "pyaaz": 40000,
    "potato": 25000,
    "potatoes": 25000,
    "aaloo": 25000,
    "vegetable": 35000,
    "vegetables": 35000,
    "sabzi": 35000,
    "textile": 180000,
    "textiles": 180000,
    "fabric": 180000,
    "kapda": 180000,
    "chemical": 120000,
    "chemicals": 120000,
    "steel": 65000,
    "iron": 65000,
    "cement": 8000,
    "grain": 22000,
    "grains": 22000,
    "wheat": 22000,
    "rice": 30000,
    "coal": 10000,
    "electronic": 800000,
    "electronics": 800000,
    "sugar": 40000,
    "chini": 40000,
    "cotton": 160000,
    "ruyi": 160000,
    "fertilizer": 25000,
    "khad": 25000,
    "plastic": 95000,
    "plastics": 95000,
    "fruit": 60000,
    "fruits": 60000,
    "phhal": 60000,
}

def infer_hsn_code(cargo_type: str) -> str:
    """Infers the 4-8 digit HSN code from the cargo type string."""
    if not cargo_type:
        return "9973"  # Default transport service code
        
    cargo_clean = cargo_type.lower().strip()
    
    # Try exact match or substring match
    for key, code in HSN_CODES.items():
        if key in cargo_clean or cargo_clean in key:
            return code
            
    return "9973"  # Fallback

def estimate_cargo_value(cargo_type: str, weight_tons: float) -> int:
    """Estimates the approximate cargo value in INR based on cargo type and weight."""
    if not weight_tons:
        return 100000  # Default fallback ₹1 Lakh
        
    cargo_clean = cargo_type.lower().strip() if cargo_type else ""
    value_per_ton = 50000  # Default ₹50,000 per ton
    
    for key, val in VALUE_PER_TON.items():
        if key in cargo_clean or cargo_clean in key:
            value_per_ton = val
            break
            
    return int(value_per_ton * weight_tons)

def build_ewb_draft(shipment: dict, operator: dict, truck: dict) -> dict:
    """Combines shipment, operator, and truck details to build a complete E-Way Bill draft payload."""
    cargo = shipment.get("cargo_type", "General Goods")
    weight = float(shipment.get("weight_tons", 0))
    hsn_code = infer_hsn_code(cargo)
    cargo_value = estimate_cargo_value(cargo, weight)
    
    # Compile consignor info from operator details
    consignor_name = operator.get("business_name") or operator.get("name") or "MSME Consignor"
    consignor_gst = operator.get("gst_number") or "27AAAAA0000A1Z5"  # Sample GSTIN
    consignor_city = operator.get("city") or shipment.get("origin")
    
    # Compile consignee info (mocked/inferred)
    consignee_name = f"Receiver Co. at {shipment.get('destination')}"
    consignee_gst = "27BBBBB1111B2Z6"  # Sample GSTIN
    
    draft = {
        "ewb_number": "DRAFT-ONLY-NOT-ISSUED",
        "consignor_name": consignor_name,
        "consignor_gstin": consignor_gst,
        "consignor_address": f"Warehouse, {consignor_city}",
        "consignee_name": consignee_name,
        "consignee_gstin": consignee_gst,
        "consignee_address": f"Industrial Area, {shipment.get('destination')}",
        "origin_place": shipment.get("origin"),
        "destination_place": shipment.get("destination"),
        "cargo_description": cargo,
        "hsn_code": hsn_code,
        "weight_tons": weight,
        "cargo_value_inr": cargo_value,
        "scheduled_date": str(shipment.get("scheduled_date")),
        "truck_number": truck.get("truck_number") if truck else "NOT_ASSIGNED",
        "driver_name": truck.get("driver_name") if truck else "NOT_ASSIGNED",
        "driver_phone": truck.get("driver_phone") if truck else "NOT_ASSIGNED",
        "document_type": "Tax Invoice",
        "transaction_type": "Outward Supply"
    }
    
    return draft
