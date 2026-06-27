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


# Power cycle zehnder_controller every 30 minutes
@time_trigger("cron(*/30 * * * *)")
async def power_cycle_zehnder():
    log.info("🔄 Power cycling zehnder_controller")
    service.call("switch", "turn_off", entity_id="switch.zehnder_controller")
    await task.sleep(10)  # Wait 10 seconds
    service.call("switch", "turn_on", entity_id="switch.zehnder_controller")
    log.info("✅ zehnder_controller power cycle complete")

