import requests
import sys

BASE_URL = "http://localhost:8000"

def print_menu():
    print("\n==================================================")
    print("      LoadSetu WhatsApp Webhook Simulator         ")
    print("==================================================")
    print("1. Rajesh Patel (Operator: +919876543210)")
    print("2. Ramesh Kumar (Driver: +919876543211)")
    print("3. Custom Phone Number")
    print("4. Exit")
    print("==================================================")

def main():
    phone_map = {
        "1": "+919876543210",
        "2": "+919876543211"
    }
    
    current_phone = phone_map["1"]
    
    # Check if server is running
    try:
        res = requests.get(f"{BASE_URL}/health")
        if res.status_code == 200:
            print("Connected to LoadSetu backend server successfully!")
    except Exception:
        print(f"Error: Backend server is not running at {BASE_URL}.")
        print("Please start the server first by running: uvicorn main:app --reload")
        sys.exit(1)

    while True:
        print_menu()
        print(f"Current active phone: {current_phone}")
        choice = input("Select sender option [1-4] or press Enter to keep current: ").strip()
        
        if choice == "4":
            print("Exiting simulator. Good luck with the hackathon!")
            break
        elif choice in phone_map:
            current_phone = phone_map[choice]
        elif choice == "3":
            custom = input("Enter custom phone number (e.g. +919999999999): ").strip()
            if custom:
                current_phone = custom
        
        message_body = input(f"Enter WhatsApp message from {current_phone}: ").strip()
        if not message_body:
            print("Cannot send empty message.")
            continue
            
        # Compile Twilio POST payload format
        payload = {
            "From": f"whatsapp:{current_phone}",
            "Body": message_body,
            "MessageSid": f"SMmock_{hash(message_body)}"
        }
        
        print(f"\nSending message: '{message_body}'...")
        try:
            response = requests.post(f"{BASE_URL}/webhook", data=payload)
            if response.status_code == 200:
                print("Webhook triggered successfully! (Status 200)")
                print("Check the FastAPI server console to see the LoadSetu Agent responses.")
            else:
                print(f"Webhook failed with status code: {response.status_code}")
                print(response.text)
        except Exception as e:
            print(f"Error sending request: {e}")

if __name__ == "__main__":
    main()
