import os
import sys
import datetime
import asyncio

# Ensure backend directory is in python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import supabase_service, status_service, notification_service
from routes import shipments, review_items

async def run_tests():
    print("==================================================")
    print("    LoadSetu Production Features Integration Tests ")
    print("==================================================")
    
    passed = 0
    total = 0
    
    # Force mock mode
    supabase_service.IS_MOCK = True
    
    # Seed base operator and truck
    operator = supabase_service.create_operator(
        phone="+919876543210",
        name="Rajesh Patel",
        business_name="Patel Logistics",
        city="Surat",
        onboarding_status="COMPLETED"
    )
    
    trucks = supabase_service.get_all_trucks()
    assert len(trucks) >= 2, "Need at least 2 trucks seeded in MOCK_TRUCKS"
    truck1 = trucks[0]
    truck2 = trucks[1]
    
    # ----------------------------------------------------
    # TEST 1: Driver Acceptance Flow (YES/NO/Implicit)
    # ----------------------------------------------------
    total += 1
    print("\nTest 1: Driver Acceptance Flow (YES)...")
    try:
        # Create a shipment pending driver acceptance
        shipment = supabase_service.create_shipment(
            operator_id=operator["id"],
            truck_id=truck1["id"],
            origin="Surat",
            destination="Mumbai",
            cargo_type="Textiles",
            weight_tons=8.0,
            scheduled_date="2026-06-12",
            status="DRIVER_PENDING_ACCEPTANCE"
        )
        
        # Simulate Driver responding "YES"
        status_service.handle_status_update(
            from_whatsapp=f"whatsapp:{truck1['driver_phone']}",
            clean_phone=truck1['driver_phone'],
            body="YES",
            operator=None,
            truck_as_driver=truck1
        )
        
        # Verify status transitioned to DRIVER_ACCEPTED
        updated = supabase_service.get_shipment_by_id(shipment["id"])
        assert updated["status"] == "DRIVER_ACCEPTED", f"Expected DRIVER_ACCEPTED, got {updated['status']}"
        
        # Verify timeline log contains acceptance event
        timeline = supabase_service.get_timeline_for_shipment(shipment["id"])
        assert any(t["event_type"] == "driver_accepted" for t in timeline), "Driver accepted event not found in timeline"
        
        print("  [PASS] Driver YES acceptance verified.")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] Driver YES acceptance test failed: {e}")

    # NO Acceptance Test
    total += 1
    print("\nTest 1b: Driver Acceptance Flow (NO)...")
    try:
        # Create another shipment pending acceptance
        shipment2 = supabase_service.create_shipment(
            operator_id=operator["id"],
            truck_id=truck2["id"],
            origin="Surat",
            destination="Pune",
            cargo_type="Polyester",
            weight_tons=8.0,
            scheduled_date="2026-06-12",
            status="DRIVER_PENDING_ACCEPTANCE"
        )
        
        # Lock truck2 initially
        supabase_service.update_truck_availability(truck2["id"], is_available=False)
        
        # Simulate Driver responding "NO"
        status_service.handle_status_update(
            from_whatsapp=f"whatsapp:{truck2['driver_phone']}",
            clean_phone=truck2['driver_phone'],
            body="NO",
            operator=None,
            truck_as_driver=truck2
        )
        
        # Verify status transitioned to REASSIGNMENT_REQUIRED
        updated2 = supabase_service.get_shipment_by_id(shipment2["id"])
        assert updated2["status"] == "REASSIGNMENT_REQUIRED", f"Expected REASSIGNMENT_REQUIRED, got {updated2['status']}"
        
        # Verify truck2 released (is_available = True)
        tr = supabase_service.get_truck_by_id(truck2["id"])
        assert tr["is_available"] is True, "Truck was not released after rejection"
        
        # Verify timeline log contains rejection event
        timeline2 = supabase_service.get_timeline_for_shipment(shipment2["id"])
        assert any(t["event_type"] == "driver_rejected" for t in timeline2), "Driver rejected event not found in timeline"
        
        print("  [PASS] Driver NO rejection verified.")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] Driver NO rejection test failed: {e}")

    # Implicit Acceptance Test
    total += 1
    print("\nTest 1c: Driver Implicit Acceptance Flow...")
    try:
        # Create shipment pending acceptance
        shipment3 = supabase_service.create_shipment(
            operator_id=operator["id"],
            truck_id=truck1["id"],
            origin="Surat",
            destination="Mumbai",
            cargo_type="Steel",
            weight_tons=8.0,
            scheduled_date="2026-06-12",
            status="DRIVER_PENDING_ACCEPTANCE"
        )
        
        # Driver says "LOADED" directly without saying "YES"
        status_service.handle_status_update(
            from_whatsapp=f"whatsapp:{truck1['driver_phone']}",
            clean_phone=truck1['driver_phone'],
            body="LOADED",
            operator=None,
            truck_as_driver=truck1
        )
        
        # Verify status transitioned directly to LOADED (implicit acceptance logic)
        updated3 = supabase_service.get_shipment_by_id(shipment3["id"])
        assert updated3["status"] == "LOADED", f"Expected LOADED, got {updated3['status']}"
        
        # Verify timeline contains implicit acceptance
        timeline3 = supabase_service.get_timeline_for_shipment(shipment3["id"])
        assert any(t["event_type"] == "driver_accepted" for t in timeline3), "Implicit driver acceptance event not logged"
        
        print("  [PASS] Driver implicit acceptance verified.")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] Driver implicit acceptance test failed: {e}")

    # ----------------------------------------------------
    # TEST 2: Reassign Truck Endpoint
    # ----------------------------------------------------
    total += 1
    print("\nTest 2: Reassign Shipment Truck...")
    try:
        # Create shipment with truck1 assigned
        shipment_re = supabase_service.create_shipment(
            operator_id=operator["id"],
            truck_id=truck1["id"],
            origin="Surat",
            destination="Mumbai",
            cargo_type="Metals",
            weight_tons=8.0,
            scheduled_date="2026-06-12",
            status="CONFIRMED"
        )
        
        # Setup truck2 to be available at Surat for reassignment
        supabase_service.update_truck_availability(truck2["id"], is_available=True, current_city="Surat")
        
        # Trigger reassignment via router function (using helper bypass auth checks or directly calling DB update/reassign logic)
        from routes.shipments import reassign_shipment
        res = await reassign_shipment(shipment_id=shipment_re["id"], authorization="Bearer secret_admin_token_2026")
        
        assert res["status"] == "DRIVER_PENDING_ACCEPTANCE", f"Expected status DRIVER_PENDING_ACCEPTANCE, got {res['status']}"
        
        # Verify truck2 is assigned now
        updated_re = supabase_service.get_shipment_by_id(shipment_re["id"])
        assert updated_re["truck_id"] == truck2["id"], "Truck reassignment failed to swap truck IDs"
        
        # Verify truck1 released
        t1 = supabase_service.get_truck_by_id(truck1["id"])
        assert t1["is_available"] is True, "Old truck was not released"
        
        print("  [PASS] Reassignment logic and DB updates verified.")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] Reassign shipment test failed: {e}")

    # ----------------------------------------------------
    # TEST 3: Cancel Shipment Endpoint
    # ----------------------------------------------------
    total += 1
    print("\nTest 3: Cancel Shipment...")
    try:
        # Create shipment
        shipment_can = supabase_service.create_shipment(
            operator_id=operator["id"],
            truck_id=truck1["id"],
            origin="Surat",
            destination="Mumbai",
            cargo_type="Sugar",
            weight_tons=8.0,
            scheduled_date="2026-06-12",
            status="CONFIRMED"
        )
        
        # Lock truck1
        supabase_service.update_truck_availability(truck1["id"], is_available=False)
        
        # Call cancel_shipment endpoint function
        from routes.shipments import cancel_shipment
        res = await cancel_shipment(shipment_id=shipment_can["id"], authorization="Bearer secret_admin_token_2026")
        
        assert res["status"] == "CANCELLED"
        
        # Verify status updated
        updated_can = supabase_service.get_shipment_by_id(shipment_can["id"])
        assert updated_can["status"] == "CANCELLED"
        
        # Verify truck1 released
        t1 = supabase_service.get_truck_by_id(truck1["id"])
        assert t1["is_available"] is True, "Truck was not released on cancellation"
        
        print("  [PASS] Cancellation logic and truck release verified.")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] Cancel shipment test failed: {e}")

    # ----------------------------------------------------
    # TEST 4: Manual Review Queue
    # ----------------------------------------------------
    total += 1
    print("\nTest 4: Manual Review Queue (Create, Resolve, Dismiss)...")
    try:
        # Create low-confidence extraction review item
        item = supabase_service.create_review_item(
            phone_number="+919876543219",
            status="OPEN",
            extracted_details={"origin": "Surat"},
            missing_fields=["destination"],
            latest_message="Surat se booking karni hai"
        )
        
        assert item is not None
        assert item["status"] == "OPEN"
        
        # Retrieve open items
        open_items = supabase_service.get_open_review_items()
        assert any(i["id"] == item["id"] for i in open_items), "Created item not found in open items list"
        
        # Resolve via router resolver
        from routes.review_items import resolve_review_item
        res_resolve = await resolve_review_item(item_id=item["id"], authorization="Bearer secret_admin_token_2026")
        assert res_resolve["review_item"]["status"] == "RESOLVED"
        
        # Verify it is no longer in open items list
        open_items = supabase_service.get_open_review_items()
        assert not any(i["id"] == item["id"] for i in open_items), "Resolved item still found in open items list"
        
        # Create another and Dismiss it
        item2 = supabase_service.create_review_item(
            phone_number="+919876543219",
            status="OPEN",
            extracted_details={"origin": "Nashik"},
            missing_fields=["destination"],
            latest_message="Nashik se booking karni hai"
        )
        
        from routes.review_items import dismiss_review_item
        res_dismiss = await dismiss_review_item(item_id=item2["id"], authorization="Bearer secret_admin_token_2026")
        assert res_dismiss["review_item"]["status"] == "DISMISSED"
        
        print("  [PASS] Manual review queue state transitions verified.")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] Manual review queue test failed: {e}")

    # ----------------------------------------------------
    # TEST 5: Outbound Attempts Retry & Logging
    # ----------------------------------------------------
    total += 1
    print("\nTest 5: Outbound Notification Attempt Retry and Logs...")
    try:
        # Log failed attempt
        attempt = supabase_service.create_notification_attempt(
            to_phone="+919876543210",
            shipment_id="shp_dummy",
            body="Test body",
            status="FAILED",
            error_message="Gateway Timeout"
        )
        
        assert attempt["status"] == "FAILED"
        assert attempt["error_message"] == "Gateway Timeout"
        
        # Retry attempt
        success = notification_service.retry_notification(attempt["id"])
        assert success is True, "Retry should return True in mock mode"
        
        # Verify status is now SENT_MOCK
        retried = supabase_service.get_notification_attempt_by_id(attempt["id"])
        assert retried["status"] == "SENT_MOCK"
        assert retried["error_message"] == ""
        
        print("  [PASS] Outbound notification logging and retry verified.")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] Outbound notification test failed: {e}")

    print("\n==================================================")
    print(f"Result: {passed}/{total} passed ({(passed/total)*100:.1f}%)")
    print("==================================================")
    
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(asyncio.run(run_tests()))
