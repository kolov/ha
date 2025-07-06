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

#########
#
# Built around https://github.com/eelcohn/nRF905-API
#
#########

MAX_FAN_RUN_TIME = timedelta(hours=1)
FAN_COOLDOWN_TIME = timedelta(minutes=5)
MIN_SERVICE_CALL_INTERVAL = timedelta(minutes=5)
# ok if humidity difference is less than this value
HUMIDITY_DIFF_OK = 10   
# max fan above this value
HUMIDITY_MAX_FAN = 85
# high fan above this value
HUMIDITY_HIGH_FAN = 70
# medium fan above this value
HUMIDITY_MEDIUM_FAN = 55

fan_start_time = None
cooldown_until = None
last_humidity = None
last_query_time = None
 

def set_fan_level(level):
    global fan_start_time
        
    if level != "low":
        if fan_start_time is None:
            fan_start_time = datetime.now()
    else:
        fan_start_time = None 
    log.info(f"🌬️ Setting fan to {level}")
    service.call("rest_command", f"send_fan_{level}")

@time_trigger("cron(* * * * *)")
def check_bathroom_humidity():
    global fan_start_time, cooldown_until, last_humidity

    bathroom_humidity = state.get("sensor.t_h_inside_sonoff_bathroom_humidity")
    bathroom_small_humidity = state.get("sensor.t_h_inside_bathroom_small_humidity")
    room_humidity = state.get("sensor.t_h_inside_sonoff_bedroom_humidity") 

    if bathroom_humidity is not None:
        last_humidity = float(bathroom_humidity)

    now = datetime.now()

    if room_humidity is None or room_humidity == 'unknown':
        log.info("🏠 Room humidity not available — assuming 55.")
        room_humidity = 55

    if bathroom_humidity is None or bathroom_humidity == 'unknown':
        log.warning("⚠️ Bathroom humidity sensor not available — assuming 60")
        bathroom_humidity = 60

    if bathroom_small_humidity is None or bathroom_small_humidity == 'unknown':
        log.warning("⚠️ Bathroom small humidity sensor not available — assuming 60")
        bathroom_small_humidity = 60

    try:
        bathroom_humidity = float(bathroom_humidity)
        bathroom_small_humidity = float(bathroom_small_humidity)
        room_humidity = float(room_humidity)
    except (ValueError, TypeError) as e:
        log.error(f"❌ Error converting humidity values to float: {e}")
        log.error(f"   bathroom_humidity: {bathroom_humidity}")
        log.error(f"   bathroom_small_humidity: {bathroom_small_humidity}")
        log.error(f"   room_humidity: {room_humidity}")
        return

    # Assume small bathroom sensor overreports humidity
    bathroom_small_humidity_adjusted = bathroom_small_humidity - 10
    most_humid = max(bathroom_humidity, bathroom_small_humidity_adjusted)
    humidity_diff = most_humid - room_humidity 

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
        cooldown_until = now + FAN_COOLDOWN_TIME
        return
    
    if humidity_diff < HUMIDITY_DIFF_OK:
        log.info(f"✅ Humidity difference <= {HUMIDITY_DIFF_OK}% (bathroom: {bathroom_humidity}%, small: {bathroom_small_humidity}%→{bathroom_small_humidity_adjusted}%, room: {room_humidity}%, max: {most_humid}%) — setting fan to low")
        set_fan_level("low")
        return
    
    
    if most_humid > HUMIDITY_MAX_FAN:
        log.info(f"🔥 Bathroom humidity > {HUMIDITY_MAX_FAN}% (bathroom: {bathroom_humidity}%, small: {bathroom_small_humidity}%→{bathroom_small_humidity_adjusted}%, room: {room_humidity}%, max: {most_humid}%) — fan should be max")
        set_fan_level("max")
    elif most_humid > HUMIDITY_HIGH_FAN:
        log.info(f"💨 Bathroom humidity > {HUMIDITY_HIGH_FAN}% (bathroom: {bathroom_humidity}%, small: {bathroom_small_humidity}%→{bathroom_small_humidity_adjusted}%, room: {room_humidity}%, max: {most_humid}%) — fan should be high")
        set_fan_level("high")
    elif most_humid > HUMIDITY_MEDIUM_FAN:
        log.info(f"💨 Bathroom humidity > {HUMIDITY_MEDIUM_FAN}% (bathroom: {bathroom_humidity}%, small: {bathroom_small_humidity}%→{bathroom_small_humidity_adjusted}%, room: {room_humidity}%, max: {most_humid}%) — fan should be medium")
        set_fan_level("medium")
    else:
        log.info(f"🌬️ Bathroom humidity <= {HUMIDITY_MEDIUM_FAN}% (bathroom: {bathroom_humidity}%, small: {bathroom_small_humidity}%→{bathroom_small_humidity_adjusted}%, room: {room_humidity}%, max: {most_humid}%) — fan should be low")
        set_fan_level("low")
 