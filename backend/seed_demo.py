import os
import sys
from dotenv import load_dotenv

# Ensure backend directory is in python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

from services import supabase_service

def run_seed():
    print("Starting demo seeding...")
    is_mock = supabase_service.is_mock_active()
    if is_mock:
        print("NOTE: Running in MOCK DB mode. Seeding local in-memory data.")

    # 1. Seed Operators
    op1 = supabase_service.create_operator(
        phone="+919876543210",
        name="Rajesh Patel",
        business_name="Patel Agro Surat",
        city="Surat"
    )
    op2 = supabase_service.create_operator(
        phone="+919988776655",
        name="Harish Shah",
        business_name="Shah Textiles Nashik",
        city="Nashik"
    )
    
    print(f"Operators seeded: {op1['name']} ({op1['id']}), {op2['name']} ({op2['id']})")

    # 2. Get Trucks for matching
    trucks = supabase_service.get_all_trucks()
    if not trucks:
        print("No trucks found in registry. Make sure database is initialized and trucks are seeded.")
        return
    
    print(f"Found {len(trucks)} trucks in registry.")

    # 3. Seed Shipments
    # Shipment 1: DELIVERED from Nashik to Mumbai (Onions)
    truck_nashik = next((t for t in trucks if t["home_city"].lower() == "nashik"), trucks[0])
    s1 = supabase_service.create_shipment(
        operator_id=op2["id"],
        truck_id=truck_nashik["id"],
        origin="Nashik",
        destination="Mumbai",
        cargo_type="Onions",
        weight_tons=8.0,
        scheduled_date="2026-06-05",
        status="DELIVERED"
    )
    supabase_service.update_shipment_status(
        s1["id"], 
        "DELIVERED", 
        ewb_draft_json={
            "consignor": "Shah Textiles Nashik",
            "consignee": "Mumbai Agro Mart",
            "origin": "Nashik",
            "destination": "Mumbai",
            "cargo_description": "Onions",
            "weight_tons": 8.0,
            "scheduled_date": "2026-06-05",
            "truck_number": truck_nashik["truck_number"],
            "driver_name": truck_nashik["driver_name"],
            "approximate_value": 450000,
            "hsn_code": "07031010"
        },
        ewb_pdf_url=f"https://dummy.supabase.co/storage/v1/object/public/ewb-drafts/ewb_draft_{s1['id']}.pdf"
    )
    # Update truck state
    supabase_service.update_truck_availability(truck_nashik["id"], is_available=True, current_city="Mumbai")

    # Shipment 2: IN_TRANSIT from Surat to Pune (Textiles)
    truck_surat = next((t for t in trucks if t["home_city"].lower() == "surat"), trucks[1])
    s2 = supabase_service.create_shipment(
        operator_id=op1["id"],
        truck_id=truck_surat["id"],
        origin="Surat",
        destination="Pune",
        cargo_type="Polyester Fabric",
        weight_tons=6.5,
        scheduled_date="2026-06-08",
        status="IN_TRANSIT"
    )
    supabase_service.update_shipment_status(
        s2["id"], 
        "IN_TRANSIT", 
        ewb_draft_json={
            "consignor": "Patel Agro Surat",
            "consignee": "Pune Textile Hub",
            "origin": "Surat",
            "destination": "Pune",
            "cargo_description": "Polyester Fabric",
            "weight_tons": 6.5,
            "scheduled_date": "2026-06-08",
            "truck_number": truck_surat["truck_number"],
            "driver_name": truck_surat["driver_name"],
            "approximate_value": 1200000,
            "hsn_code": "5407"
        },
        ewb_pdf_url=f"https://dummy.supabase.co/storage/v1/object/public/ewb-drafts/ewb_draft_{s2['id']}.pdf"
    )
    # Update truck state
    supabase_service.update_truck_availability(truck_surat["id"], is_available=False, current_city="Surat")

    # Shipment 3: PENDING/CONFIRMED from Surat to Mumbai (Chemicals)
    truck_surat2 = next((t for t in trucks if t["home_city"].lower() == "surat" and t["id"] != truck_surat["id"]), trucks[2])
    s3 = supabase_service.create_shipment(
        operator_id=op1["id"],
        truck_id=truck_surat2["id"],
        origin="Surat",
        destination="Mumbai",
        cargo_type="Industrial Chemicals",
        weight_tons=12.0,
        scheduled_date="2026-06-09",
        status="CONFIRMED"
    )
    supabase_service.update_truck_availability(truck_surat2["id"], is_available=False, current_city="Surat")

    print(f"Demo shipments seeded:")
    print(f" - S1 (Delivered): {s1['id']}")
    print(f" - S2 (In Transit): {s2['id']}")
    print(f" - S3 (Confirmed): {s3['id']}")
    print("Demo seeding completed successfully!")

if __name__ == "__main__":
    run_seed()
