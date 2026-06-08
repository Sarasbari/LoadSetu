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

def find_trucks(origin: str, destination: str, weight_tons: float) -> list[dict]:
    """Queries the DB for available trucks and appends a calculated rate to each match."""
    capacity = float(weight_tons) if weight_tons else 1.0
    matched_trucks = supabase_service.get_available_trucks(origin, capacity)
    
    # Calculate rates for each truck
    results = []
    for truck in matched_trucks:
        # Tonnage rate can be based on the truck's capacity or requested weight
        rate = calculate_freight_rate(origin, destination, weight_tons or truck.get("capacity_tons", 10.0))
        
        # Add rate and route to the truck object for booking reference
        truck_copy = dict(truck)
        truck_copy["calculated_rate"] = rate
        results.append(truck_copy)
        
    return results

def format_truck_choices(trucks: list[dict]) -> str:
    """Formats a list of truck objects into a structured WhatsApp choice message."""
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
        
    msg += "\nConfirm karne ke liye reply karein: 1, 2 ya 3"
    return msg
