# zigbee_last_seen.py

import json
from datetime import datetime, timedelta

# Load persistent last_seen dictionary
global_last_seen = pyscript.persist.get("global_last_seen", {})

@mqtt_trigger("zigbee2mqtt/+/#")
def handle_zigbee_message(topic=None, payload=None):
    """
    Updates global_last_seen for each Zigbee device when any MQTT message is received.
    Stores the result in persistent storage.
    """
    device = topic.split("/")[1]
    now_iso = datetime.now().isoformat()

    global_last_seen[device] = now_iso
    pyscript.persist["global_last_seen"] = global_last_seen

    log.debug(f"[zigbee_last_seen] {device} seen at {now_iso}")


@time_trigger("period(5min)")
def check_zigbee_devices():
    """
    Every 5 minutes, checks if any Zigbee device has not been seen in over 3 hours.
    Logs a warning or success message accordingly.
    """
    now = datetime.now()
    cutoff = now - timedelta(hours=3)
    missing = []

    for device, ts_str in global_last_seen.items():
        try:
            ts = datetime.fromisoformat(ts_str)
            if ts < cutoff:
                missing.append(f"{device} (last: {ts.strftime('%H:%M')})")
        except Exception as e:
            log.warning(f"[zigbee_last_seen] Bad timestamp for {device}: {ts_str} ({e})")

    if missing:
        msg = f"⚠️ Missing Zigbee devices: {', '.join(missing)}"
        log.warning(f"[zigbee_last_seen] {msg}")
        # notify.notify(message=msg)  # Optional: uncomment to push to mobile
    else:
        log.info("[zigbee_last_seen] ✅ All Zigbee devices recently active.")
