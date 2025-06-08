from datetime import datetime, timedelta
from typing import Any, Dict
import json

try:
    from utils import state_inc, set_state_datetime, get_state_datetime, set_state_none
except ImportError:
    # In Jupyter, execute the content of utils.py in a cell first
    pass

try:
    # For the linter
    from pyscript_types import state, service, task, log, state_trigger, time_trigger, pyscript, mqtt_trigger
except ImportError:
    # When running in Jupyter
    pass
from datetime import datetime, timedelta

MAX_FAN_RUN_TIME = timedelta(hours=1)
# ok if humidity difference is less than this value
HUMIDITY_DIFF_OK = 10   
# max fan above this value
HUMIDITY_MAX_FAN = 80
# high fan above this value
HUMIDITY_HIGH_FAN = 70
# medium fan above this value
HUMIDITY_MEDIUM_FAN = 60

fan_start_time = None
cooldown_until = None
last_humidity = None
last_query_time = None

@time_trigger("cron(* * * * *)")
def check_bathroom_humidity():
    global fan_start_time, cooldown_until, last_humidity

    bathroom_humidity = state.get("sensor.t_h_inside_bathroom_humidity")
    room_humidity = state.get("sensor.meter_61e8_humidity")
    
    log.info(f"🛁 Bathroom humidity is {bathroom_humidity}, room humidity is {room_humidity}")

    if bathroom_humidity is not None:
        last_humidity = float(bathroom_humidity)

    now = datetime.now()

    if room_humidity is None:
        log.info("🏠 Room humidity not available — assuming 55.")
        room_humidity = 55

    if bathroom_humidity is None:
        log.warning("⚠️ Humidity sensor not available — setting fan to low.")
        service.call("rest_command", "send_fan_low")
        return

    bathroom_humidity = float(bathroom_humidity)
    room_humidity = float(room_humidity)
    humidity_diff = bathroom_humidity - room_humidity

    # In cooldown period → run only on low
    if cooldown_until and now < cooldown_until:
        log.info("⏳ In cooldown period — forcing fan to low.")
        service.call("rest_command", "send_fan_low")
        return

    # Overuse → start cooldown
    if fan_start_time and (now - fan_start_time) >= MAX_FAN_RUN_TIME:
        log.info("🔄 Fan ran on medium/max for 1h — setting to low and entering cooldown.")
        service.call("rest_command", "send_fan_low")
        fan_start_time = None
        cooldown_until = now + timedelta(minutes=15)
        return
    
    if humidity_diff < HUMIDITY_DIFF_OK:
        log.info(f"✅ Humidity difference <= {HUMIDITY_DIFF_OK}% (bathroom: {bathroom_humidity}%, room: {room_humidity}%) — setting fan to low")
        service.call("rest_command", "send_fan_low")
        fan_start_time = None
        return

    if bathroom_humidity > HUMIDITY_MAX_FAN:
        log.info(f"🔥 Bathroom humidity > {HUMIDITY_MAX_FAN}% (bathroom: {bathroom_humidity}%, room: {room_humidity}%) — setting fan to max")
        service.call("rest_command", "send_fan_max")
        if not fan_start_time:
            fan_start_time = now
    elif bathroom_humidity > HUMIDITY_HIGH_FAN:
        log.info(f"💨 Bathroom humidity > {HUMIDITY_HIGH_FAN}% (bathroom: {bathroom_humidity}%, room: {room_humidity}%) — setting fan to high")
        service.call("rest_command", "send_fan_high")
        if not fan_start_time:
            fan_start_time = now
    elif bathroom_humidity > HUMIDITY_MEDIUM_FAN:
        log.info(f"💨 Bathroom humidity > {HUMIDITY_MEDIUM_FAN}% (bathroom: {bathroom_humidity}%, room: {room_humidity}%) — setting fan to medium")
        service.call("rest_command", "send_fan_medium")
        if not fan_start_time:
            fan_start_time = now            
    else:
        log.info(f"🌬️ Bathroom humidity <= {HUMIDITY_MEDIUM_FAN}% (bathroom: {bathroom_humidity}%, room: {room_humidity}%) — setting fan to low")
        service.call("rest_command", "send_fan_low")
        fan_start_time = None

@time_trigger("cron(* * * * *)")   
def refresh_bathroom_humidity():
    global last_humidity, last_query_time
    
    now = datetime.now()
    should_query = False

    # If we don't have a last query time or last humidity, query immediately
    if last_query_time is None or last_humidity is None:
        should_query = True
    # If last humidity was high, query every minute
    elif last_humidity > HUMIDITY_MEDIUM_FAN:
        should_query = True
    # Otherwise query every 10 minutes
    else:
        should_query = (now - last_query_time) >= timedelta(minutes=10)
    
    if should_query:
        payload = {
            "device": "t_h_inside_bathroom_humidity",   
            "payload": {
                "attributes": ["humidity", "temperature"]
            }
        }

        payload_str = json.dumps(payload)
        log.info(f"📤 Publishing to Zigbee2MQTT: {payload_str}")
        
        try:
            mqtt.publish(
                topic="zigbee2mqtt/bridge/request/device/read",
                payload=payload_str
            )
            log.info("✅ Successfully published to Zigbee2MQTT")
        except Exception as e:
            log.error(f"❌ Failed to publish to Zigbee2MQTT: {e}")
            return

        last_query_time = now

@mqtt_trigger("zigbee2mqtt/t_h_inside_bathroom_humidity")
def update_last_humidity(topic=None, payload=None):
    global last_humidity
    try:
        data = json.loads(payload)
        humidity = data.get("humidity")
        if humidity is not None:
            last_humidity = float(humidity)
            log.info(f"📊 Updated last_humidity: {last_humidity}")
        else:
            log.warning("⚠️ Received payload without humidity value")
    except Exception as e:
        log.error(f"❌ Error parsing humidity payload: {e}")
