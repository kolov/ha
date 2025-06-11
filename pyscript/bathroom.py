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
# ok if humidity difference is less than this value
HUMIDITY_DIFF_OK = 10   
# max fan above this value
HUMIDITY_MAX_FAN = 85
# high fan above this value
HUMIDITY_HIGH_FAN = 60
# medium fan above this value
HUMIDITY_MEDIUM_FAN = 50

fan_start_time = None
cooldown_until = None
last_humidity = None
last_query_time = None

@time_trigger("cron(* * * * *)")
def check_bathroom_humidity():
    global fan_start_time, cooldown_until, last_humidity

    bathroom_humidity = state.get("sensor.t_h_inside_bathroom_humidity")
    room_humidity = state.get("sensor.meter_61e8_humidity") 

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
 