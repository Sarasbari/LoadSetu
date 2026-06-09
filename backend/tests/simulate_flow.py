import time
import requests

BASE_URL = "http://localhost:8000"
WEBHOOK_URL = f"{BASE_URL}/webhook"

# Simulating Rajesh Patel (Operator)
OPERATOR_PHONE = "+919876543210"
OPERATOR_WHATSAPP = f"whatsapp:{OPERATOR_PHONE}"

# Simulating Suresh Patel (Driver of the matched truck)
DRIVER_PHONE = "+919876543212"
DRIVER_WHATSAPP = f"whatsapp:{DRIVER_PHONE}"

def send_message(from_phone, body):
    payload = {
        "From": from_phone,
        "Body": body,
        "MessageSid": f"SMmock_{int(time.time() * 1000)}"
    }
    print(f"\n💬 Sending: '{body}' (From: {from_phone})")
    try:
        response = requests.post(WEBHOOK_URL, data=payload)
        if response.status_code == 200:
            print("✅ Webhook responded successfully.")
        else:
            print(f"❌ Webhook returned error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Failed to reach server: {e}")

def run_simulation():
    print("=========================================================")
    print("       LoadSetu End-to-End Chat Flow Simulation          ")
    print("=========================================================")
    print("This script simulates a real-life booking and tracking flow.")
    print("Make sure your FastAPI server is running on http://localhost:8000")
    print("And keep your React Dashboard open to watch real-time updates!")
    print("=========================================================\n")

    # Step 1: Operator initiates booking
    input("Press Enter to send Booking Request from Operator...")
    send_message(
        from_phone=OPERATOR_WHATSAPP,
        body="Mujhe Surat se Mumbai ke liye 8 ton textiles ka truck chahiye kal ke liye"
    )
    
    print("\n💡 [Info] Check your FastAPI console output now.")
    print("You should see the Intake Agent extract origin='Surat', destination='Mumbai', and weight='8.0'.")
    print("The Matching Agent will output the 3 closest matching trucks from the registry.")
    
    # Step 2: Operator selects truck choice
    print("\n---------------------------------------------------------")
    input("Press Enter to simulate Operator selecting Option 1 (Suresh Patel)...")
    send_message(
        from_phone=OPERATOR_WHATSAPP,
        body="1"
    )

    print("\n💡 [Info] Check your Supabase database or the Frontend Dashboard.")
    print("A shipment should now be created in the database (status: CONFIRMED).")
    print("A draft E-Way Bill PDF has been generated and uploaded to storage.")
    print("The driver (Suresh Patel) has been notified of the assignment.")

    # Step 3: Driver loads cargo
    print("\n---------------------------------------------------------")
    input("Press Enter to simulate Driver reporting LOADED status...")
    send_message(
        from_phone=DRIVER_WHATSAPP,
        body="Maal load ho gaya hai, nikal rahe hain. LOADED"
    )

    print("\n💡 [Info] Check your Frontend Dashboard.")
    print("The shipment status will transition to 'LOADED'.")
    
    # Step 4: Driver reports delivery
    print("\n---------------------------------------------------------")
    input("Press Enter to simulate Driver reporting DELIVERED status...")
    send_message(
        from_phone=DRIVER_WHATSAPP,
        body="Mumbai pahunch gaya, delivery complete. DELIVERED"
    )

    print("\n💡 [Info] Check your Frontend Dashboard.")
    print("The shipment status will transition to 'DELIVERED'.")
    print("The truck will be released back to 'Available' with its current location updated to 'Mumbai'.")
    print("\n=========================================================")
    print("Simulation complete! You can view the full history in")
    print("the Dashboard and Chat Logs pages on the React App.")
    print("=========================================================")

if __name__ == "__main__":
    run_simulation()
