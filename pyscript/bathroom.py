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

MIN_SERVICE_CALL_INTERVAL = timedelta(minutes=5)

# Tunable limits live in input_number helpers (ha-config/ventilation_limits.yaml)
# so they can be edited from the ventilation dashboard / HA UI without redeploying.
# The values here are the fallback defaults used when a helper is unavailable.
LIMIT_DEFAULTS = {
    "dehumidifier_off_humidity": 50,  # turn dehumidifier off below this humidity
    "humidity_diff_ok": 6,            # ok if bathroom-vs-room diff is under this
    "humidity_max_fan": 75,           # max fan above this humidity
    "humidity_high_fan": 65,          # high fan above this humidity
    "humidity_medium_fan": 55,        # medium fan above this humidity
    "max_fan_run_time_min": 60,       # force low + cooldown after this many minutes
    "fan_cooldown_min": 5,            # cooldown duration after overuse
    "presence_off_delay_sec": 180,    # wait this long after presence clears before dehumidifier on
    "night_start_hour": 23,           # dehumidifier blocked from this hour
    "night_end_hour": 8,              # ...until this hour
}


def get_limit(name):
    """Read a tunable limit from its input_number helper, falling back to the default."""
    default = LIMIT_DEFAULTS[name]
    value = state.get(f"input_number.{name}")
    if value is None or value in ("unknown", "unavailable"):
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def is_night_hours(now):
    """True during the configured night window. Handles both wrapping windows
    (e.g. 23:00–08:00) and same-day windows (e.g. 08:00–22:00)."""
    start = int(get_limit("night_start_hour"))
    end = int(get_limit("night_end_hour"))
    hour = now.hour
    if start == end:
        return False  # empty window — never night
    if start < end:
        return start <= hour < end  # same-day window
    return hour >= start or hour < end  # wraps past midnight


fan_start_time = None
cooldown_until = None
last_humidity = None
last_query_time = None
dehumidifier_delay_active = False
 

def set_fan_level(level):
    global fan_start_time
        
    if level != "low":
        if fan_start_time is None:
            fan_start_time = datetime.now()
    else:
        fan_start_time = None
    log.info(f"🌬️ Setting fan to {level}")
    service.call("rest_command", f"send_fan_{level}")
    # Publish current fan level so the dashboard can show ventilation status.
    state.set("pyscript.bathroom_fan_level", level)

@time_trigger("cron(* * * * *)")
def check_bathroom_humidity():
    global fan_start_time, cooldown_until, last_humidity

    bathroom_humidity = state.get("sensor.t_h_inside_sonoff_bathroom_humidity")
    bathroom_small_humidity = state.get("sensor.t_h_inside_bathroom_small_humidity")
    room_humidity = state.get("sensor.t_h_inside_sonoff_bedroom_humidity") 

    if bathroom_humidity is not None and bathroom_humidity not in ("unknown", "unavailable"):
        try:
            last_humidity = float(bathroom_humidity)
        except (ValueError, TypeError):
            pass

    now = datetime.now()

    if room_humidity in (None, 'unknown', 'unavailable'):
        log.info("🏠 Room humidity not available — assuming 55.")
        room_humidity = 55

    if bathroom_humidity in (None, 'unknown', 'unavailable'):
        log.warning("⚠️ Bathroom humidity sensor not available — assuming 60")
        bathroom_humidity = 60

    if bathroom_small_humidity in (None, 'unknown', 'unavailable'):
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

    humidity_diff_ok = get_limit("humidity_diff_ok")
    humidity_max_fan = get_limit("humidity_max_fan")
    humidity_high_fan = get_limit("humidity_high_fan")
    humidity_medium_fan = get_limit("humidity_medium_fan")
    max_fan_run_time = timedelta(minutes=get_limit("max_fan_run_time_min"))
    fan_cooldown = timedelta(minutes=get_limit("fan_cooldown_min"))

    # Assume small bathroom sensor overreports humidity
    bathroom_small_humidity_adjusted = bathroom_small_humidity - 10
    most_humid = max(bathroom_humidity, bathroom_small_humidity_adjusted)
    humidity_diff = most_humid - room_humidity

    # In cooldown period → run only on low
    if cooldown_until and now < cooldown_until:
        log.info("⏳ In cooldown period — forcing fan to low.")
        set_fan_level("low")
        return

    # Overuse → start cooldown
    if fan_start_time and (now - fan_start_time) >= max_fan_run_time:
        log.info(f"🔄 Fan ran on medium/max for {max_fan_run_time} — setting to low and entering cooldown.")
        set_fan_level("low")
        cooldown_until = now + fan_cooldown
        return

    if humidity_diff < humidity_diff_ok:
        log.info(f"✅ Humidity difference <= {humidity_diff_ok}% (bathroom: {bathroom_humidity}%, small: {bathroom_small_humidity}%→{bathroom_small_humidity_adjusted}%, room: {room_humidity}%, max: {most_humid}%) — setting fan to low")
        set_fan_level("low")
        return


    if most_humid > humidity_max_fan:
        log.info(f"🔥 Bathroom humidity > {humidity_max_fan}% (bathroom: {bathroom_humidity}%, small: {bathroom_small_humidity}%→{bathroom_small_humidity_adjusted}%, room: {room_humidity}%, max: {most_humid}%) — fan should be max")
        set_fan_level("max")
    elif most_humid > humidity_high_fan:
        log.info(f"💨 Bathroom humidity > {humidity_high_fan}% (bathroom: {bathroom_humidity}%, small: {bathroom_small_humidity}%→{bathroom_small_humidity_adjusted}%, room: {room_humidity}%, max: {most_humid}%) — fan should be high")
        set_fan_level("high")
    elif most_humid > humidity_medium_fan:
        log.info(f"💨 Bathroom humidity > {humidity_medium_fan}% (bathroom: {bathroom_humidity}%, small: {bathroom_small_humidity}%→{bathroom_small_humidity_adjusted}%, room: {room_humidity}%, max: {most_humid}%) — fan should be medium")
        set_fan_level("medium")
    else:
        log.info(f"🌬️ Bathroom humidity <= {humidity_medium_fan}% (bathroom: {bathroom_humidity}%, small: {bathroom_small_humidity}%→{bathroom_small_humidity_adjusted}%, room: {room_humidity}%, max: {most_humid}%) — fan should be low")
        set_fan_level("low")

def bathroom_humidity_below_threshold():
    """True if bathroom humidity is known and below the dehumidifier off threshold."""
    humidity = state.get("sensor.t_h_inside_sonoff_bathroom_humidity")
    if humidity is None or humidity == "unknown":
        return False
    try:
        return float(humidity) < get_limit("dehumidifier_off_humidity")
    except (ValueError, TypeError):
        return False


# Re-evaluates whenever the humidity or the limit helper changes.
@state_trigger("float(sensor.t_h_inside_sonoff_bathroom_humidity) < float(input_number.dehumidifier_off_humidity)")
def dehumidifier_off_on_low_humidity():
    limit = get_limit("dehumidifier_off_humidity")
    log.info(f"💧 Bathroom humidity < {limit}% — turning off dehumidifier")
    service.call("switch", "turn_off", entity_id="switch.dehumidifier")


@state_trigger("binary_sensor.presence_bathroom_occupancy")
async def control_dehumidifier_on_presence(var_name=None, value=None, old_value=None):
    global dehumidifier_delay_active
    log.info(f"🚪 Presence trigger fired! var_name={var_name}, old={old_value}, new={value}")
    now = datetime.now()
    # Block dehumidifier ON during night hours
    if is_night_hours(now):
        log.info("⏰ Night hours: dehumidifier will not turn on due to presence.")
        service.call("switch", "turn_off", entity_id="switch.dehumidifier")
        dehumidifier_delay_active = False
        return

    if value == "on":
        log.info("👤 Presence detected in bathroom — turning off dehumidifier")
        task.unique("dehumidifier_delay")  # Cancel any pending turn-on (kill the old sleeper)
        dehumidifier_delay_active = False
        service.call("switch", "turn_off", entity_id="switch.dehumidifier")
    elif value == "off":
        delay = get_limit("presence_off_delay_sec")
        log.info(f"👤 No presence in bathroom — waiting {delay}s before turning on dehumidifier")
        # kill_me defaults to False: a new presence-clear cancels the old sleeper and restarts the timer.
        task.unique("dehumidifier_delay")
        dehumidifier_delay_active = True
        await task.sleep(delay)
        # Check if still no presence after waiting
        current_presence = state.get("binary_sensor.presence_bathroom_occupancy")
        if current_presence == "off":
            if is_night_hours(datetime.now()):
                log.info("⏰ Night window started during the wait — keeping dehumidifier off")
            elif bathroom_humidity_below_threshold():
                log.info(f"💧 {delay}s passed with no presence but humidity < {get_limit('dehumidifier_off_humidity')}% — keeping dehumidifier off")
            else:
                log.info(f"⏱️ {delay}s passed with no presence — turning on dehumidifier")
                service.call("switch", "turn_on", entity_id="switch.dehumidifier")
        else:
            log.info("👤 Presence detected during wait period — keeping dehumidifier off")
        dehumidifier_delay_active = False

@time_trigger("cron(*/5 * * * *)")
def night_dehumidifier_control():
    global dehumidifier_delay_active
    now = datetime.now()
    # Block dehumidifier during night hours
    if is_night_hours(now):
        log.info("⏰ Night hours: dehumidifier will turn off.")
        service.call("switch", "turn_off", entity_id="switch.dehumidifier")
    else:
        # Check presence before turning on during day hours
        current_presence = state.get("binary_sensor.presence_bathroom_occupancy")
        if current_presence == "off":
            # Don't turn on if we're waiting for the 3-minute delay
            if dehumidifier_delay_active:
                log.info("⏰ Day hours and no presence, but waiting for delay period — skipping turn on.")
            elif bathroom_humidity_below_threshold():
                log.info(f"💧 Day hours and no presence, but humidity < {get_limit('dehumidifier_off_humidity')}% — turning off dehumidifier.")
                service.call("switch", "turn_off", entity_id="switch.dehumidifier")
            else:
                log.info("⏰ Day hours and no presence: turning on dehumidifier.")
                service.call("switch", "turn_on", entity_id="switch.dehumidifier")
        else:
            log.info("⏰ Day hours but presence detected: keeping dehumidifier off.")
