import os
import asyncio
import datetime
import logging
from services import supabase_service, twilio_service

logger = logging.getLogger(__name__)

# Interval to check for delays (default: 30 minutes in seconds)
CHECK_INTERVAL_SECONDS = 30 * 60

# Delay window (default: 3 hours)
DELAY_WINDOW_HOURS = int(os.getenv("DELAY_CHECK_INTERVAL_HOURS", 3))

async def start_delay_checker():
    """Starts the background task loop to check for delayed shipments."""
    logger.info("Starting background delay checker loop...")
    while True:
        try:
            await check_delayed_shipments()
        except Exception as e:
            logger.error(f"Error in background delay checker: {e}")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)

async def check_delayed_shipments():
    """Queries active shipments and checks if any are past their scheduled pickup with no updates."""
    logger.info("Checking for delayed shipments...")
    
    # 1. Fetch shipments that are CONFIRMED and haven't been alerted yet
    # Note: If status is LOADED or IN_TRANSIT, they have updated progress, so they are not delayed in terms of pickup.
    # We check shipments where status == "CONFIRMED" and delay_alerted == False.
    active_shipments = []
    
    if supabase_service.is_mock_active():
        # Read from mock memory
        for s in supabase_service.MOCK_SHIPMENTS.values():
            if s["status"] == "CONFIRMED" and not s.get("delay_alerted", False):
                active_shipments.append(dict(s))
    else:
        try:
            res = supabase_service.supabase_client.table("shipments")\
                .select("*")\
                .eq("status", "CONFIRMED")\
                .eq("delay_alerted", False).execute()
            active_shipments = res.data
        except Exception as e:
            logger.error(f"Error querying active shipments for delay check: {e}")
            return
            
    now = datetime.datetime.now()
    
    for shipment in active_shipments:
        scheduled_date_str = shipment.get("scheduled_date")
        if not scheduled_date_str:
            continue
            
        try:
            # Parse scheduled date (YYYY-MM-DD)
            sched_date = datetime.datetime.strptime(scheduled_date_str, "%Y-%m-%d").date()
            # Combine with standard pickup time of 10:00 AM local time
            sched_time = datetime.datetime.combine(sched_date, datetime.time(10, 0, 0))
            
            # Calculate deadline (scheduled time + delay window)
            deadline = sched_time + datetime.timedelta(hours=DELAY_WINDOW_HOURS)
            
            # Check if current time is past the deadline
            if now > deadline:
                logger.warning(f"Shipment {shipment['id']} is flagged as DELAYED (Deadline: {deadline}, Now: {now})")
                
                # Update status in DB
                # Note: We set status to "DELAYED" and delay_alerted to True
                if supabase_service.is_mock_active():
                    s_id = shipment["id"]
                    if s_id in supabase_service.MOCK_SHIPMENTS:
                        supabase_service.MOCK_SHIPMENTS[s_id]["status"] = "DELAYED"
                        supabase_service.MOCK_SHIPMENTS[s_id]["delay_alerted"] = True
                else:
                    supabase_service.supabase_client.table("shipments")\
                        .update({"status": "DELAYED", "delay_alerted": True})\
                        .eq("id", shipment["id"]).execute()
                
                # Fetch driver details
                truck = supabase_service.get_truck_by_id(shipment["truck_id"])
                driver_name = truck.get("driver_name", "Driver") if truck else "Driver"
                driver_phone = truck.get("driver_phone", "N/A") if truck else "N/A"
                truck_number = truck.get("truck_number", "N/A") if truck else "N/A"
                
                # Fetch operator details to get phone
                operator_phone = None
                if supabase_service.is_mock_active():
                    for op in supabase_service.MOCK_OPERATORS.values():
                        if op["id"] == shipment["operator_id"]:
                            operator_phone = op["phone"]
                else:
                    op_res = supabase_service.supabase_client.table("operators")\
                        .select("phone").eq("id", shipment["operator_id"]).execute()
                    if op_res.data:
                        operator_phone = op_res.data[0]["phone"]
                        
                if operator_phone:
                    # Send alert to operator
                    alert_body = (
                        f"⚠️ DELAY ALERT!\n\n"
                        f"Trip ID: {shipment['id'][:8].upper()}\n"
                        f"Route: {shipment['origin']} to {shipment['destination']}\n"
                        f"Driver {driver_name} ({truck_number}) ne scheduled time (10:00 AM, {scheduled_date_str}) ke 3 ghante baad tak loading update nahi diya hai.\n\n"
                        f"Kripya driver se contact karein: {driver_phone}"
                    )
                    twilio_service.send_message(
                        to_number=f"whatsapp:{operator_phone}",
                        body=alert_body,
                        shipment_id=shipment["id"]
                    )
                    
        except Exception as e:
            logger.error(f"Error processing delay check for shipment {shipment.get('id')}: {e}")
