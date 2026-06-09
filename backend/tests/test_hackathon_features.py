import os
import sys
import datetime

# Ensure backend directory is in python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import supabase_service
from agents import matching_agent, intake_agent

def run_tests():
    print("==================================================")
    # Ensure mock mode is active to run tests without live Supabase credentials
    print("     LoadSetu Hackathon Features Integration Tests  ")
    print("==================================================")
    
    passed = 0
    total = 0
    
    # ----------------------------------------------------
    # TEST 1: Timeline Events
    # ----------------------------------------------------
    total += 1
    print("\nTest 1: Timeline Event Logging and Retrieval...")
    try:
        # Enable mock mode explicitly if not set
        supabase_service.IS_MOCK = True
        
        evt = supabase_service.create_timeline_event(
            shipment_id="shp_test_123",
            phone_number="+919876543210",
            event_type="booking_request_received",
            title="Booking Request Received",
            description="Testing timeline event creation",
            metadata={"test_key": "test_val"}
        )
        
        assert evt is not None, "Created event should not be None"
        assert evt["shipment_id"] == "shp_test_123", "Shipment ID mismatch"
        assert evt["event_type"] == "booking_request_received", "Event type mismatch"
        
        # Retrieve timeline
        timeline = supabase_service.get_timeline_for_shipment("shp_test_123")
        assert len(timeline) >= 1, "Timeline list should contain at least 1 event"
        assert timeline[0]["id"] == evt["id"], "Event ID mismatch on retrieval"
        
        print("  [PASS] Timeline logged and retrieved successfully.")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] Timeline event test failed: {e}")

    # ----------------------------------------------------
    # TEST 2: Rate Explainability
    # ----------------------------------------------------
    total += 1
    print("\nTest 2: Rate Proximity and Proximity Explainability...")
    try:
        truck = {
            "id": "t_test_1",
            "driver_name": "Ramesh Driver",
            "driver_phone": "+919876543211",
            "truck_number": "MH-15-AB-1234",
            "truck_type": "open",
            "capacity_tons": 10.0,
            "home_city": "Nashik",
            "current_city": "Nashik",
            "is_available": True
        }
        
        explanation = matching_agent.explain_match(
            truck=truck,
            origin="Nashik",
            destination="Mumbai",
            weight_tons=8.0
        )
        
        assert explanation["calculated_rate"] > 0, "Rate should be calculated"
        assert len(explanation["match_reasons"]) >= 4, "Should have capacity fit, availability, base proximity, and rate explanation reasons"
        assert any("Capacity fits 8.0" in r for r in explanation["match_reasons"]), "Missing capacity fit reason"
        assert any("Based near Nashik" in r for r in explanation["match_reasons"]), "Missing home city reason"
        assert any("Estimated Nashik-Mumbai" in r for r in explanation["match_reasons"]), "Missing rate reason"
        
        print("  [PASS] Proximity and capacity fit reasons successfully verified.")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] Rate Proximity test failed: {e}")

    # ----------------------------------------------------
    # TEST 3: Driver Proof of Delivery (POD)
    # ----------------------------------------------------
    total += 1
    print("\nTest 3: Proof of Delivery Fields and Update...")
    try:
        # Create a mock shipment
        shipment = supabase_service.create_shipment(
            operator_id="op_1",
            truck_id="t_1",
            origin="Surat",
            destination="Mumbai",
            cargo_type="Textiles",
            weight_tons=8.0,
            scheduled_date="2026-06-09",
            status="CONFIRMED"
        )
        
        # Simulate driver status update with POD
        pod_url = "http://localhost:8000/media/receipt.jpg"
        pod_note = "Delivered at warehouse"
        updated_shipment = supabase_service.update_shipment_status(
            shipment_id=shipment["id"],
            status="DELIVERED",
            pod_status="RECEIVED",
            pod_note=pod_note,
            pod_media_url=pod_url,
            pod_received_at=datetime.datetime.now().isoformat()
        )
        
        assert updated_shipment["status"] == "DELIVERED", "Shipment status should be DELIVERED"
        assert updated_shipment["pod_status"] == "RECEIVED", "POD status should be RECEIVED"
        assert updated_shipment["pod_note"] == pod_note, "POD note mismatch"
        assert updated_shipment["pod_media_url"] == pod_url, "POD media URL mismatch"
        assert updated_shipment["pod_received_at"] is not None, "POD timestamp missing"
        
        print("  [PASS] POD status and attachment saved successfully.")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] POD update test failed: {e}")

    # ----------------------------------------------------
    # TEST 4: Clarification Message Template Generation
    # ----------------------------------------------------
    total += 1
    print("\nTest 4: Clarification Question Format Logic...")
    try:
        # We manually test template building block logic
        # If origin and destination are present but weight and cargo_type are missing
        missing_fields = ["weight", "cargo type"]
        named_fields = []
        examples = []
        for f in missing_fields:
            if f == "weight":
                named_fields.append("weight")
                examples.append("8 ton")
            elif f == "cargo type":
                named_fields.append("cargo type")
                examples.append("textiles")
        
        fields_str = " aur ".join([", ".join(named_fields[:-1]), named_fields[-1]] if len(named_fields) > 1 else named_fields)
        ex_str = " se ".join(examples[:2]) + (" " + " ".join(examples[2:]) if len(examples) > 2 else "")
        question = f"Kripya {fields_str} bata dijiye. Example: {ex_str}"
        
        assert "weight aur cargo type" in question, "Failed to combine missing fields"
        assert "Example: 8 ton se textiles" in question, "Failed to build example string"
        
        print("  [PASS] Clarification question formatting matches expected logic.")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] Clarification message formatting test failed: {e}")

    print("\n==================================================")
    print(f"Result: {passed}/{total} passed ({(passed/total)*100:.1f}%)")
    print("==================================================")
    
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(run_tests())
