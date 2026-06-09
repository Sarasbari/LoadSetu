import requests
import json
import sys

BASE_URL = "http://127.0.0.1:8000"
HEADERS = {
    "Authorization": "Bearer secret_admin_token_2026"
}


def get_shipment_ids():
    """Returns set of current shipment IDs."""
    res = requests.get(f"{BASE_URL}/shipments", headers=HEADERS)
    if res.status_code != 200:
        return set()
    data = res.json()
    shipments = data.get("shipments", [])
    return {s["id"] for s in shipments}


def find_shipment_by_id(shipment_id):
    """Fetch current state of a specific shipment from the list."""
    res = requests.get(f"{BASE_URL}/shipments", headers=HEADERS)
    if res.status_code != 200:
        return None
    data = res.json()
    for s in data.get("shipments", []):
        if s.get("id") == shipment_id:
            return s
    return None


def run_verification():
    print("==================================================")
    print("      LoadSetu Automated E2E Flow Verification    ")
    print("==================================================")

    # 1. Check health
    try:
        res = requests.get(f"{BASE_URL}/health")
        if res.status_code == 200:
            print("[PASS] Connected to backend health endpoint.")
        else:
            print(f"[FAIL] Health check failed with status: {res.status_code}")
            return False
    except Exception as e:
        print(f"[FAIL] Could not connect to backend: {e}")
        return False

    operator_phone = "+919876543210"

    # Snapshot shipment IDs before booking
    ids_before = get_shipment_ids()
    print(f"[INFO] Shipments before booking: {len(ids_before)} ({ids_before})")

    # Step 1: Send New Booking Request
    print("\n--- Step 1: Operator requests a truck ---")
    payload1 = {
        "From": f"whatsapp:{operator_phone}",
        "Body": "Surat se Mumbai 8 ton textiles kal ke liye",
        "MessageSid": "SMmock_step1"
    }
    res1 = requests.post(f"{BASE_URL}/webhook", data=payload1)
    if res1.status_code == 200:
        print("[PASS] Webhook processed operator booking request.")
    else:
        print(f"[FAIL] Webhook failed: {res1.status_code}\n{res1.text}")
        return False

    # Step 2: Confirm Selection (Option 1)
    print("\n--- Step 2: Operator confirms option 1 ---")
    payload2 = {
        "From": f"whatsapp:{operator_phone}",
        "Body": "1",
        "MessageSid": "SMmock_step2"
    }
    res2 = requests.post(f"{BASE_URL}/webhook", data=payload2)
    if res2.status_code == 200:
        print("[PASS] Webhook processed operator option selection.")
    else:
        print(f"[FAIL] Webhook failed: {res2.status_code}\n{res2.text}")
        return False

    # Find the NEW shipment by diffing IDs
    ids_after = get_shipment_ids()
    new_ids = ids_after - ids_before
    print(f"[INFO] Shipments after booking: {len(ids_after)} ({ids_after})")
    print(f"[INFO] Newly created shipment IDs: {new_ids}")

    if not new_ids:
        print("[FAIL] No new shipment was created after confirmation.")
        return False

    new_shipment_id = sorted(new_ids)[-1]  # Pick the latest by ID sort
    latest_shipment = find_shipment_by_id(new_shipment_id)

    if not latest_shipment:
        print(f"[FAIL] Could not fetch newly created shipment {new_shipment_id}")
        return False

    print(f"\n[PASS] New shipment created! ID: {latest_shipment['id']}")
    print(f"[INFO] Route: {latest_shipment['origin']} -> {latest_shipment['destination']}")
    print(f"[INFO] Cargo: {latest_shipment['cargo_type']} ({latest_shipment['weight_tons']} Tons)")
    print(f"[INFO] Status: {latest_shipment['status']}")

    # Verify the route is Surat to Mumbai
    if latest_shipment['origin'] != "Surat" or latest_shipment['destination'] != "Mumbai":
        print(f"[FAIL] Incorrect route! Expected Surat -> Mumbai, got {latest_shipment['origin']} -> {latest_shipment['destination']}")
        return False
    else:
        print("[PASS] Route is correct: Surat -> Mumbai.")

    # Verify PDF is generated
    pdf_url = latest_shipment.get("ewb_pdf_url")
    if pdf_url:
        print(f"[PASS] E-Way Bill PDF Draft URL set: {pdf_url}")
    else:
        print("[FAIL] E-Way Bill PDF Draft URL is missing.")
        return False

    # Discover the assigned driver phone from the trucks endpoint
    truck_id = latest_shipment.get("truck_id")
    driver_phone = None
    if truck_id:
        trucks_res = requests.get(f"{BASE_URL}/trucks", headers=HEADERS)
        if trucks_res.status_code == 200:
            trucks_data = trucks_res.json()
            trucks_list = trucks_data.get("trucks", trucks_data) if isinstance(trucks_data, dict) else trucks_data
            if isinstance(trucks_list, list):
                for t in trucks_list:
                    if t.get("id") == truck_id:
                        driver_phone = t.get("driver_phone")
                        print(f"[INFO] Assigned truck: {t.get('truck_number')} | Driver: {t.get('driver_name')} ({driver_phone})")
                        break

    if not driver_phone:
        print("[WARN] Could not determine driver phone from truck. Using default +919876543211")
        driver_phone = "+919876543211"

    # Step 3: Driver updates status to LOADED
    print("\n--- Step 3: Driver reports LOADED ---")
    payload3 = {
        "From": f"whatsapp:{driver_phone}",
        "Body": "loaded ho gaya bhai",
        "MessageSid": "SMmock_step3"
    }
    res3 = requests.post(f"{BASE_URL}/webhook", data=payload3)
    if res3.status_code == 200:
        print("[PASS] Webhook processed driver LOADED status update.")
    else:
        print(f"[FAIL] Webhook failed: {res3.status_code}\n{res3.text}")
        return False

    # Verify status is LOADED
    updated_shipment = find_shipment_by_id(new_shipment_id)
    if updated_shipment and updated_shipment['status'] == "LOADED":
        print("[PASS] Shipment status successfully updated to LOADED.")
    else:
        actual = updated_shipment['status'] if updated_shipment else 'NOT FOUND'
        print(f"[FAIL] Expected status LOADED, got: {actual}")
        return False

    # Step 4: Driver updates status to DELIVERED
    print("\n--- Step 4: Driver reports DELIVERED ---")
    payload4 = {
        "From": f"whatsapp:{driver_phone}",
        "Body": "Mumbai pohonch gaya, delivery completed",
        "MessageSid": "SMmock_step4"
    }
    res4 = requests.post(f"{BASE_URL}/webhook", data=payload4)
    if res4.status_code == 200:
        print("[PASS] Webhook processed driver DELIVERED status update.")
    else:
        print(f"[FAIL] Webhook failed: {res4.status_code}\n{res4.text}")
        return False

    # Verify status is DELIVERED
    final_shipment = find_shipment_by_id(new_shipment_id)
    if final_shipment and final_shipment['status'] == "DELIVERED":
        print("[PASS] Shipment status successfully updated to DELIVERED.")
    else:
        actual = final_shipment['status'] if final_shipment else 'NOT FOUND'
        print(f"[FAIL] Expected status DELIVERED, got: {actual}")
        return False

    # Step 5: Verify Dashboard API returns updated data
    print("\n--- Step 5: Dashboard API validation ---")
    dash_res = requests.get(f"{BASE_URL}/shipments", headers=HEADERS)
    if dash_res.status_code == 200:
        dash_data = dash_res.json()
        dash_shipments = dash_data.get("shipments", [])
        delivered_count = sum(1 for s in dash_shipments if s.get("status") == "DELIVERED")
        print(f"[PASS] Dashboard API returns {len(dash_shipments)} shipments ({delivered_count} delivered).")
    else:
        print(f"[FAIL] Dashboard API failed: {dash_res.status_code}")
        return False

    print("\n==================================================")
    print("      ALL END-TO-END FLOW CHECKS PASSED!          ")
    print("==================================================")
    return True

if __name__ == "__main__":
    success = run_verification()
    sys.exit(0 if success else 1)
