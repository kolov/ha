from datetime import datetime, timedelta


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


global_last_seen = {}

@mqtt_trigger("zigbee2mqtt/#")
def handle_zigbee_message(topic=None, payload=None):
    from datetime import datetime

    # exlude messages starting with zigbee2mqtt/bridge
    if topic.startswith("zigbee2mqtt/bridge/"): 
        return

    # Extract everything after "zigbee2mqtt/"
    if topic.startswith("zigbee2mqtt/"):
        key = topic[len("zigbee2mqtt/"):]
    else:
        log.warning(f"⚠️ Unexpected topic prefix: {topic}")
        return

    now_str = datetime.now().isoformat()
    global_last_seen[key] = now_str

    log.debug(f"Updated global_last_seen[{key}] = {now_str}")



@time_trigger("cron(*/5 * * * *)")
def check_missing_zigbee_devices(): 
    cutoff = datetime.now() - timedelta(hours=3)
    missing = []
    now = datetime.now()

    # First check for missing devices
    for device, ts_str in global_last_seen.items():
        try:
            ts = datetime.fromisoformat(ts_str)
            if ts < cutoff:
                missing.append(device)
        except Exception as e:
            log.warning(f"Invalid timestamp for {device}: {ts_str} ({e})")

    if missing:
        log.warning(f"⚠️ No MQTT from: {', '.join(missing)} in the last 3 hours")
        # Optional: notify.notify(message=f"Zigbee devices missing: {', '.join(missing)}")
    
    # Then show status for all devices
    log.info("📱 Zigbee device status:")
    for device, ts_str in sorted(global_last_seen.items()):
        try:
            ts = datetime.fromisoformat(ts_str)
            time_ago = now - ts
            if time_ago.total_seconds() < 60:
                ago = f"{int(time_ago.total_seconds())}s ago"
            elif time_ago.total_seconds() < 3600:
                ago = f"{int(time_ago.total_seconds() / 60)}m ago"
            else:
                ago = f"{int(time_ago.total_seconds() / 3600)}h ago"
            log.info(f"  • {device}: {ago}")
        except Exception as e:
            log.warning(f"  • {device}: Invalid timestamp ({e})")
