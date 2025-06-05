from datetime import datetime, timedelta
from typing import Any, Dict
import json

try:
    from utils import state_inc, set_state_datetime, get_state_datetime, set_state_none
except ImportError:
    try:
        from modules.utils import state_inc, set_state_datetime, get_state_datetime, set_state_none
    except ImportError:
         # In Jupyter, execute the content of utils.py in a cell first
        pass

try:
    # For the linter
    from pyscript_types import state, service, task, log, state_trigger, time_trigger, pyscript
except ImportError:
    # When running in HASS/Jupyter
    pass

# Constants
SWITCH_AFTER_LOW_POWER_MINUTES: int = 6
# will detect coffi made when above
COFFE_MAKING_POWER_LOWER = 800
# will detect coffi made when above for at least
COFFEE_MAKING_DURATION_MIN_SECONDS = 10

power_history = []

@mqtt_trigger("zigbee2mqtt/espresso_machine")
def update_power_average(payload=None):
    global power_history

    try:
        data = json.loads(payload)
        power = float(data.get("power", 0))
    except Exception as e:
        log.error(f"Failed to parse MQTT power payload: {e}")
        return

    now = datetime.now()
    power_history.append((now, power))
    cutoff = now - timedelta(minutes=5)
    power_history = [(ts, val) for ts, val in power_history if ts >= cutoff]

    if power_history:
        total = 0
        for _, val in power_history:
          total += val 
        pyscript.espresso_power_avg=int(total / len(power_history))

VAR_LAST_LOW_POWER: str = "last_low_power" 
set_state_none(VAR_LAST_LOW_POWER)
 
@time_trigger("cron(* * * * *)") 
def turn_off_if_idle(value=None): 
    try:
        power = int(pyscript.espresso_power_avg)   
    except (ValueError, TypeError):
        log.error(f"Failed to parse power: {pyscript.espresso_power_avg}")
        return

    log.info(f"Espresso power: {power}W")
    if 1 < power < 400:
        now = datetime.now()
        last_low_power=get_state_datetime(VAR_LAST_LOW_POWER)
        log.info(f"Last low power: {last_low_power}")
        if not isinstance(last_low_power, datetime):
            log.info("No last low power — setting now")
            set_state_datetime(VAR_LAST_LOW_POWER, now)   
            log.info(f"Last low power set to {get_state_datetime(VAR_LAST_LOW_POWER)}")
        else:                   
            if now - last_low_power >= timedelta(minutes=SWITCH_AFTER_LOW_POWER_MINUTES):
                log.info(f"☕ Power {power}W below threshold for 6 min — cycling power")
                service.call("switch", "turn_off", entity_id="switch.espresso_machine")
                task.sleep(5)
                service.call("switch", "turn_on", entity_id="switch.espresso_machine")
                set_state_none(VAR_LAST_LOW_POWER)
    else: 
        set_state_none(VAR_LAST_LOW_POWER)      


@state_trigger("sensor.espresso_machine_power")
async def coffee_counter(value=None):
    task.unique("coffee_counter", kill_me=True)
    try:
        power = float(value)
    except (ValueError, TypeError):
        return
    if power < 800:
        return

    log.info(f"☕ Power above 800W detected ({power}W) — waiting 10 seconds to confirm...")
    await task.sleep(COFFEE_MAKING_DURATION_MIN_SECONDS)

    # Re-check the power
    current_power = float(state.get("sensor.espresso_machine_power"))
    if current_power > 800:
        log.info(f"☕ Power still above {COFFE_MAKING_POWER_LOWER}W after {COFFEE_MAKING_DURATION_MIN_SECONDS}s — counting coffee")
        state_inc("espressos_today")
    else:
        log.info(f"❌ Power dropped to {current_power}W — no coffee counted")        