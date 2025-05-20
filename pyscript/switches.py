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

 

@mqtt_trigger("zigbee2mqtt/aqara_switch_1")
def aqara_switch_1(payload=None): 
    try:
        data = json.loads(payload)
        action =  data.get("action")
    except Exception as e:
        log.error(f"Failed to parse MQTT aqara_switch_1 payload: {e}")
        return

    if action == "single_left":
        log.info("🔌 Toggle switch desk")
        if state.get("switch.living_desk") == "on":
            service.call("switch", "turn_off", entity_id="switch.living_desk")
        else:
            service.call("switch", "turn_on", entity_id="switch.living_desk")
    else:
        log.info(f"No action for {action}") 

# Switch desk off at 20:00
@time_trigger("cron(0 20 * * *)")
def turn_off_desk_at_2000():
    service.call("switch", "turn_off", entity_id="switch.living_desk")

#switch on at 08:30
@time_trigger("cron(0 8 30 * *)")
def turn_on_desk_at_0830():
    service.call("switch", "turn_on", entity_id="switch.living_desk")

 