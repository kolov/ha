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

def should_skip_device(device_name: str) -> bool:
    """Determine if a device should be skipped in status reporting.
    
    Args:
        device_name: The name of the device from the MQTT topic
        
    Returns:
        True if the device should be skipped, False otherwise
    """
    # Skip bridge messages
    if device_name.startswith("bridge/"):
        return True
    # Skip any set commands
    if "/set" in device_name:
        return True
    return False

@mqtt_trigger("zigbee2mqtt/#")
def handle_zigbee_message(topic=None, payload=None):
    from datetime import datetime

    # Extract everything after "zigbee2mqtt/"
    if topic.startswith("zigbee2mqtt/"):
        key = topic[len("zigbee2mqtt/"):]
    else:
        log.warning(f"⚠️ Unexpected topic prefix: {topic}")
        return

    # Skip any set commands or bridge messages
    if should_skip_device(key):
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
        if should_skip_device(device):
            continue
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
    
    # Create list of (device, time_ago) tuples for sorting
    device_times = []
    for device, ts_str in global_last_seen.items():
        if should_skip_device(device):
            continue
        try:
            ts = datetime.fromisoformat(ts_str)
            time_ago = now - ts
            device_times.append((device, time_ago))
        except Exception as e:
            log.warning(f"  • {device}: Invalid timestamp ({e})")
    
    # Sort by time_ago (ascending, so most recent first)
    for device, time_ago in sorted(device_times, key=lambda x: x[1]):
        if time_ago.total_seconds() < 60:
            ago = f"{int(time_ago.total_seconds())}s ago"
        elif time_ago.total_seconds() < 3600:
            ago = f"{int(time_ago.total_seconds() / 60)}m ago"
        else:
            hours = int(time_ago.total_seconds() / 3600)
            minutes = int((time_ago.total_seconds() % 3600) / 60)
            ago = f"{hours}h {minutes}m ago"
        log.info(f"  • {device}: {ago}")
