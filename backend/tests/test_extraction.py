import os
import sys

# Ensure backend directory is in python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents import intake_agent, status_agent

# Test cases: (Input messages, Expected Intent, Expected Details/Status)
TEST_CASES = [
    # NEW_BOOKING Clean Cases
    {
        "input": ["Nashik se Mumbai 8 ton pyaaz kal chahiye"],
        "expected_intent": "NEW_BOOKING",
        "verify_details": lambda d: d["origin"] == "Nashik" and d["destination"] == "Mumbai" and d["cargo_type"] == "Onions" and d["weight_tons"] == 8.0
    },
    {
        "input": ["aaj surat se pune 6.5 ton kapda"],
        "expected_intent": "NEW_BOOKING",
        "verify_details": lambda d: d["origin"] == "Surat" and d["destination"] == "Pune" and d["cargo_type"] == "Textiles" and d["weight_tons"] == 6.5
    },
    {
        "input": ["Delhi se Ludhiana 15 ton steel kal ke liye"],
        "expected_intent": "NEW_BOOKING",
        "verify_details": lambda d: d["origin"] == "Delhi" and d["destination"] == "Ludhiana" and d["cargo_type"] == "Steel" and d["weight_tons"] == 15.0
    },
    {
        "input": ["Nashik se Mumbai 10 ton chini kal ke liye"],
        "expected_intent": "NEW_BOOKING",
        "verify_details": lambda d: d["origin"] == "Nashik" and d["destination"] == "Mumbai" and d["cargo_type"] == "Sugar" and d["weight_tons"] == 10.0
    },
    {
        "input": ["surat se pune 5 ton ruyi chahiye"],
        "expected_intent": "NEW_BOOKING",
        "verify_details": lambda d: d["origin"] == "Surat" and d["destination"] == "Pune" and d["cargo_type"] == "Cotton" and d["weight_tons"] == 5.0
    },
    
    # NEW_BOOKING Partial & Follow-up Cases
    {
        "input": ["Nashik se Mumbai truck chahiye"],
        "expected_intent": "NEW_BOOKING",
        "verify_details": lambda d: d["origin"] == "Nashik" and d["destination"] == "Mumbai" and d["weight_tons"] is None
    },
    {
        "input": ["Nashik se Mumbai truck chahiye", "8 ton hai"],
        "expected_intent": "NEW_BOOKING",
        "verify_details": lambda d: d["weight_tons"] == 8.0  # Context resolution test
    },
    {
        "input": ["Nashik se Mumbai truck chahiye", "8 ton hai", "pyaaz load karna hai"],
        "expected_intent": "NEW_BOOKING",
        "verify_details": lambda d: d["cargo_type"] == "Onions"
    },
    
    # CONFIRMATION Cases
    {
        "input": ["3 trucks available:\n1. MH15AB1234\n2. MH04CX5678\nConfirm 1, 2, 3", "1"],
        "expected_intent": "CONFIRMATION",
        "verify_details": None
    },
    {
        "input": ["Select option", "confirm first one"],
        "expected_intent": "CONFIRMATION",
        "verify_details": None
    },
    
    # STATUS_UPDATE Cases
    {
        "input": ["loaded ho gaya bhai"],
        "expected_intent": "STATUS_UPDATE",
        "verify_status": lambda s: s["status"] == "LOADED"
    },
    {
        "input": ["nashik se nikal gaya"],
        "expected_intent": "STATUS_UPDATE",
        "verify_status": lambda s: s["status"] == "IN_TRANSIT"
    },
    {
        "input": ["Mumbai pohonch gaya"],
        "expected_intent": "STATUS_UPDATE",
        "verify_status": lambda s: s["status"] == "DELIVERED"
    },
    {
        "input": ["engine kharab ho gaya check karo"],
        "expected_intent": "STATUS_UPDATE",
        "verify_status": lambda s: s["status"] == "DELAYED"
    },
    
    # QUERY Cases
    {
        "input": ["mera truck kahan hai"],
        "expected_intent": "QUERY",
        "verify_details": None
    },
    
    # OTHER Cases
    {
        "input": ["namaste sir kaise ho"],
        "expected_intent": "OTHER",
        "verify_details": None
    },
    {
        "input": ["hello loadsetu"],
        "expected_intent": "OTHER",
        "verify_details": None
    }
]

def run_tests():
    print("==================================================")
    print("      LoadSetu NLP Intent & Extraction Tests      ")
    print("==================================================")
    
    passed = 0
    total = len(TEST_CASES)
    
    for i, tc in enumerate(TEST_CASES):
        msgs = tc["input"]
        expected_intent = tc["expected_intent"]
        
        print(f"\nTest {i+1}/{total}: Input Thread = {msgs}")
        
        # 1. Test Intent Classification
        actual_intent = intake_agent.classify_intent(msgs)
        intent_ok = actual_intent == expected_intent
        
        # 2. Test Details Extraction (if intent is NEW_BOOKING)
        details_ok = True
        if expected_intent == "NEW_BOOKING" and tc.get("verify_details"):
            # We pass context as list of previous messages, and current message
            context = msgs[:-1]
            current = msgs[-1]
            details = intake_agent.extract_freight_details(context, current)
            details_ok = tc["verify_details"](details)
            if not details_ok:
                print(f"  [Details Fail] Extracted: {details}")
                
        # 3. Test Status Parsing (if intent is STATUS_UPDATE)
        status_ok = True
        if expected_intent == "STATUS_UPDATE" and tc.get("verify_status"):
            status_res = status_agent.parse_status(msgs[-1])
            status_ok = tc["verify_status"](status_res)
            if not status_ok:
                print(f"  [Status Fail] Parsed: {status_res}")
                
        if intent_ok and details_ok and status_ok:
            print(f"  [PASS] (Intent: {actual_intent})")
            passed += 1
        else:
            print(f"  [FAIL] (Expected Intent: {expected_intent}, Got: {actual_intent})")
            
    print("\n==================================================")
    print(f"Result: {passed}/{total} passed ({(passed/total)*100:.1f}%)")
    print("==================================================")
    
    # Return exit code
    return 0 if passed >= 12 else 1

if __name__ == "__main__":
    sys.exit(run_tests())
