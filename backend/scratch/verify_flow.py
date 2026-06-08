import requests
import json
import sys

BASE_URL = "http://127.0.0.1:8000"
HEADERS = {
    "Authorization": "Bearer secret_admin_token_2026"
}

def run_verification():
    print("==================================================")
    print("      LoadSetu Automated E2E Flow Verification    ")
    print("==================================================")

    # 1. Check health
    try:
        res = requests.get(f"{BASE_URL}/health")
        if res.status_code == 200:
            print("[INFO] Connected to backend health endpoint.")
        else:
            print(f"[FAIL] Health check failed with status: {res.status_code}")
            return False
    except Exception as e:
        print(f"[FAIL] Could not connect to backend: {e}")
        return False

    operator_phone = "+919876543210"
    driver_phone = "+919876543211"

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

    # Get conversation history & state
    state_res = requests.get(f"{BASE_URL}/conversations", headers=HEADERS)
    if state_res.status_code == 200:
        conversations = state_res.json()
        print(f"[PASS] Successfully fetched active conversations.")
    else:
        print(f"[FAIL] Failed to fetch active conversation threads: {state_res.status_code}\n{state_res.text}")
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

    # Check shipments
    shipments_res = requests.get(f"{BASE_URL}/shipments", headers=HEADERS)
    if shipments_res.status_code == 200:
        shipments_data = shipments_res.json()
        shipments_list = shipments_data.get("shipments", [])
        
        print("\n[DEBUG] Available Shipments in DB:")
        for s in shipments_list:
            print(f" - ID: {s.get('id')}, Status: {s.get('status')}, Route: {s.get('origin')} -> {s.get('destination')}")
        
        if not shipments_list:
            print("[FAIL] No shipments found after confirmation.")
            return False
        
        # Find the newly created shipment (should be shp_4 or the highest ID)
        latest_shipment = None
        for s in shipments_list:
            if s.get("id") == "shp_4":
                latest_shipment = s
                break
                
        if not latest_shipment:
            # Fallback to the first one in the list
            latest_shipment = shipments_list[0]
            
        print(f"\n[PASS] Selected shipment for E2E check! ID: {latest_shipment['id']}")
        print(f"[INFO] Route: {latest_shipment['origin']} to {latest_shipment['destination']}")
        print(f"[INFO] Cargo: {latest_shipment['cargo_type']} ({latest_shipment['weight_tons']} Tons)")
        
        # Verify the route is Surat to Mumbai (NOT Surat to Surat or Nashik to Surat)
        if latest_shipment['origin'] != "Surat" or latest_shipment['destination'] != "Mumbai":
            print(f"[FAIL] Incorrect route details! Expected Surat to Mumbai, got {latest_shipment['origin']} to {latest_shipment['destination']}")
            return False
        else:
            print("[PASS] Route is correct: Surat to Mumbai.")
            
        # Verify PDF is generated and public URL is set
        pdf_url = latest_shipment.get("ewb_pdf_url")
        if pdf_url:
            print(f"[PASS] E-Way Bill PDF Draft url set: {pdf_url}")
        else:
            print("[FAIL] E-Way Bill PDF Draft URL is missing.")
            return False
    else:
        print(f"[FAIL] Failed to fetch shipments: {shipments_res.status_code}")
        return False

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

    # Verify status in shipments
    shipments_res = requests.get(f"{BASE_URL}/shipments", headers=HEADERS)
    shipments_data = shipments_res.json()
    shipments_list = shipments_data.get("shipments", [])
    
    # Find the active shipment for driver
    driver_shipment = None
    for s in shipments_list:
        if s.get("id") == latest_shipment["id"]:
            driver_shipment = s
            break
            
    if driver_shipment and driver_shipment['status'] == "LOADED":
        print("[PASS] Shipment status successfully updated to LOADED.")
    else:
        print(f"[FAIL] Expected status LOADED, got: {driver_shipment['status'] if driver_shipment else 'None'}")
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
    shipments_res = requests.get(f"{BASE_URL}/shipments", headers=HEADERS)
    shipments_data = shipments_res.json()
    shipments_list = shipments_data.get("shipments", [])
    
    driver_shipment = None
    for s in shipments_list:
        if s.get("id") == latest_shipment["id"]:
            driver_shipment = s
            break
            
    if driver_shipment and driver_shipment['status'] == "DELIVERED":
        print("[PASS] Shipment status successfully updated to DELIVERED.")
    else:
        print(f"[FAIL] Expected status DELIVERED, got: {driver_shipment['status'] if driver_shipment else 'None'}")
        return False

    print("\n==================================================")
    print("      ALL END-TO-END FLOW CHECKS PASSED!           ")
    print("==================================================")
    return True

if __name__ == "__main__":
    success = run_verification()
    sys.exit(0 if success else 1)
