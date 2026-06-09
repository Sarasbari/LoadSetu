import logging
from services import supabase_service

logger = logging.getLogger(__name__)

# Standard distances (km) and base rates (INR/ton/km) for common corridors
CORRIDORS = {
    ("nashik", "mumbai"): {"distance_km": 170, "rate_per_ton_km": 3.2},
    ("surat", "mumbai"): {"distance_km": 280, "rate_per_ton_km": 3.0},
    ("surat", "pune"): {"distance_km": 340, "rate_per_ton_km": 3.2},
    ("mumbai", "pune"): {"distance_km": 150, "rate_per_ton_km": 3.5},
    ("delhi", "jaipur"): {"distance_km": 270, "rate_per_ton_km": 2.8},
    ("delhi", "ludhiana"): {"distance_km": 310, "rate_per_ton_km": 2.8},
}

def calculate_freight_rate(origin: str, destination: str, weight_tons: float) -> int:
    """Calculates a realistic freight rate (INR) based on route and cargo weight."""
    orig_clean = origin.lower().strip() if origin else ""
    dest_clean = destination.lower().strip() if destination else ""
    weight = float(weight_tons) if weight_tons else 10.0  # Default to 10 tons if weight is unspecified
    
    # Try to find a matched corridor
    corridor_data = None
    for (o, d), data in CORRIDORS.items():
        if o in orig_clean and d in dest_clean:
            corridor_data = data
            break
            
    if corridor_data:
        distance = corridor_data["distance_km"]
        rate_per_ton_km = corridor_data["rate_per_ton_km"]
    else:
        # Fallback default distance and rate
        distance = 250
        rate_per_ton_km = 3.0
        
    total_rate = distance * rate_per_ton_km * weight
    # Round to nearest hundred rupees for realism
    return int(round(total_rate / 100.0) * 100.0)

def explain_match(truck: dict, origin: str, destination: str, weight_tons: float) -> dict:
    """Explains why a truck was matched and calculates capacity fit, home city proximity, rate, etc."""
    capacity = float(truck.get("capacity_tons", 10.0))
    weight = float(weight_tons) if weight_tons else 8.0
    home_city = truck.get("home_city", "")
    current_city = truck.get("current_city", "")
    
    reasons = []
    
    # 1. Capacity fit
    if capacity >= weight:
        reasons.append(f"Capacity fits {weight}T load (Truck capacity: {capacity}T)")
    else:
        reasons.append(f"Under-capacity load but matching route (Truck capacity: {capacity}T)")
        
    # 2. Availability
    if truck.get("is_available", True):
        reasons.append("Available now")
        
    # 3. Base Location Proximity
    if origin.lower().strip() in home_city.lower().strip():
        reasons.append(f"Based near {home_city}")
    elif origin.lower().strip() in current_city.lower().strip():
        reasons.append(f"Currently located at {current_city}")
    else:
        reasons.append(f"Based in {home_city}")
        
    # 4. Rate Explainability
    rate = calculate_freight_rate(origin, destination, weight)
    reasons.append(f"Estimated {origin.capitalize()}-{destination.capitalize()} freight rate: Rs. {rate:,}")
    
    return {
        "calculated_rate": rate,
        "match_reasons": reasons,
        "capacity_fit_tons": capacity,
        "route_note": f"Corridor {origin.capitalize()} to {destination.capitalize()}",
        "availability_note": "Available" if truck.get("is_available", True) else "Unavailable"
    }

def find_trucks(origin: str, destination: str, weight_tons: float) -> list[dict]:
    """Queries the DB for available trucks and appends a calculated rate and match explanation to each."""
    capacity = float(weight_tons) if weight_tons else 1.0
    matched_trucks = supabase_service.get_available_trucks(origin, capacity)
    
    # Calculate rates and explanations for each truck
    results = []
    for truck in matched_trucks:
        explanation = explain_match(truck, origin, destination, weight_tons)
        
        # Add rate, reasons and notes to the truck object for reference
        truck_copy = dict(truck)
        truck_copy["calculated_rate"] = explanation["calculated_rate"]
        truck_copy["match_reasons"] = explanation["match_reasons"]
        truck_copy["capacity_fit_tons"] = explanation["capacity_fit_tons"]
        truck_copy["route_note"] = explanation["route_note"]
        truck_copy["availability_note"] = explanation["availability_note"]
        results.append(truck_copy)
        
    return results

def format_truck_choices(trucks: list[dict]) -> str:
    """Formats a list of truck objects into a structured WhatsApp choice message, including short reasons."""
    if not trucks:
        return "Mafi chahte hain, is route aur weight ke liye abhi koi truck available nahi hai. Kripya thodi der baad try karein."
        
    msg = f"{len(trucks)} trucks available hain:\n\n"
    for i, t in enumerate(trucks):
        cap = t.get("capacity_tons")
        truck_type = t.get("truck_type", "open").capitalize()
        rate = t.get("calculated_rate", 5000)
        num = t.get("truck_number")
        driver = t.get("driver_name")
        
        msg += f"{i+1}. {num} ({cap}T {truck_type}) | Driver: {driver} | Rate: ₹{rate:,}\n"
        
        # Add concise match reasons
        reasons = t.get("match_reasons", [])
        if reasons:
            concise_reasons = []
            for r in reasons:
                if "Capacity fits" in r:
                    concise_reasons.append(f"Fits {cap}T")
                elif "Based near" in r:
                    concise_reasons.append(r)
                elif "Available now" in r:
                    concise_reasons.append("Available")
            if concise_reasons:
                msg += f"   - {', '.join(concise_reasons)}\n"
        
    msg += "\nConfirm karne ke liye reply karein: 1, 2 ya 3"
    return msg
