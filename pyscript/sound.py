from datetime import datetime, timedelta
from typing import Any, Dict
import json


try:
    from utils import set_state_bool, get_state_bool, set_state_datetime, get_state_datetime, set_state_none
except ImportError:
    try:
        from modules.utils import set_state_bool, get_state_bool, set_state_datetime, get_state_datetime, set_state_none
    except ImportError:
        # In Jupyter, execute the content of utils.py in a cell first
        pass

try:
    # For the linter
    from pyscript_types import state, service, task, log, state_trigger, time_trigger, pyscript
except ImportError:
    # When running in HASS/Jupyter
    pass

SWITCH: str = "switch.stereo_amplifier"


#########################
# Sound control
# - last_off_time      | "" or isodatetime | datetime of last time speaker was turned off
#########################

## bool | 'true if audio cast is streaming
VAR_AUDIO_CAST_STREAMING: str = "audio_cast_streaming"
## bool | 'true if tv is on
VAR_TV_PLAYING: str = "tv_playing"
## bool | 'true if any music source is playing
VAR_SOMETHING_PLAYING: str = "something_playing"
## isodatetime | time since no music source is playing
VAR_SILENCE_START: str = "silence_start"
## isodatetime | datetime of last time speaker was turned off
VAR_LAST_OFF_TIME: str = "last_off_time"

# Did not manage to send IR codes from pyscript, calling existing trigerless autmations instead

def select_tv_sound_input():
    service.call("automation", "trigger", entity_id="automation.select_tv_sound_input")

def select_audio_cast_sound_input():
    service.call("automation", "trigger", entity_id="automation.select_cast_sound_input")

def volume_up():
    service.call("automation", "trigger", entity_id="automation.volume_up")

def volume_down():
    service.call("automation", "trigger", entity_id="automation.volume_down")


def audio_cast_state() -> str:
    return state.get("media_player.living_room_speaker")

def tv_state() -> str:
    return state.get("media_player.lg_webos_tv_85c7")

def set_audio_cast_streaming(audio_cast_state: str) -> None:
   set_state_bool(VAR_AUDIO_CAST_STREAMING, audio_cast_state in ['playing', 'buffering'])

set_audio_cast_streaming(audio_cast_state())

@state_trigger("media_player.living_room_speaker")
def on_audio_cast_state_change(**kwargs: Dict[str, Any]) -> None:
    new_state=kwargs["value"]
    log.info(f"🎶 Audio cast changed: {kwargs["old_value"]} → {new_state}")
    set_audio_cast_streaming(new_state)
    
    if get_state_bool(VAR_AUDIO_CAST_STREAMING):
        log.info("📡 Sending audio cast IR code")
        select_audio_cast_sound_input()

def set_tv_playing(tv_state: str) -> None:
    set_state_bool("tv_playing", tv_state in ['on'])
    
set_tv_playing(tv_state())

@state_trigger("media_player.lg_webos_tv_85c7")
def on_tv_state_change(**kwargs: Dict[str, Any]) -> None:
    new_state=kwargs["value"]
    log.info(f"🎶 Tv changed: {kwargs["old_value"]} → {new_state}")
    set_tv_playing(new_state)
    
    if pyscript.tv_playing:
        log.info("📡 Sending TV IR code")
        select_tv_sound_input()


def set_someting_playing(source1: bool, source2: bool):
    set_state_bool(VAR_SOMETHING_PLAYING,  source1 or source2) 
    
set_someting_playing(get_state_bool(VAR_AUDIO_CAST_STREAMING), get_state_bool(VAR_TV_PLAYING))

@state_trigger("pyscript.audio_cast_streaming or pyscript.tv_playing")
def on_any_sound_source_changes() -> None:
    log.info(f"Some sound source changed. {VAR_AUDIO_CAST_STREAMING}={get_state_bool(VAR_AUDIO_CAST_STREAMING)}, {VAR_TV_PLAYING}={get_state_bool(VAR_TV_PLAYING)}")
    set_someting_playing(get_state_bool(VAR_AUDIO_CAST_STREAMING), get_state_bool(VAR_TV_PLAYING)) 
    log.info(f"Set {VAR_SOMETHING_PLAYING} to {get_state_bool(VAR_SOMETHING_PLAYING)}")

def set_silence_start_now() -> None:
    set_state_datetime(VAR_SILENCE_START, datetime.now())

def clear_silence_start() -> None:
    log.info("🔊 Clearing silence start")
    set_state_none(VAR_SILENCE_START) 

@state_trigger("pyscript.something_playing == 'false'")
def on_sound_off() -> None: 
    log.info("🔊 Sound must be off")
    set_silence_start_now()

@state_trigger("pyscript.something_playing == 'true'")
async def on_sound_on() -> None:
    log.info("🔊 Sound must be on")
    task.unique("on_sound_on", kill_me=True)
    last_off_time = get_state_datetime("last_off_time") or datetime.now()
    clear_silence_start() 
    now = datetime.now()
    time_since_off = (now - last_off_time).total_seconds()

    switch_state=state.get(SWITCH)
    if switch_state == "off":
        if time_since_off < 10:
            delay = 10 - time_since_off
            log.info(f"🕒 Waiting {delay:.1f}s before turning stereo ON")
            await task.sleep(delay)
        log.info("🔊 Turning ON stereo")
        service.call("switch", "turn_on", entity_id=SWITCH)
    else:
        log.info(f"🔊 Stereo is already {switch_state}")

def turn_off() -> None:
    service.call("switch", "turn_off", entity_id=SWITCH)
    set_state_datetime(VAR_LAST_OFF_TIME, datetime.now())

@time_trigger("cron(* * * * *)")
def turn_off_if_silent() -> None:
    log.info("🔊 Checking if stereo should be turned off")
    something_playing = get_state_bool(VAR_SOMETHING_PLAYING)
    log.info(f"Something playing: {something_playing}")
    stereo_on = state.get(SWITCH) == "on"
    if stereo_on:
        log.info("stereo is on now")
        if something_playing:
            clear_silence_start()
        else:
            silence_start = get_state_datetime(VAR_SILENCE_START)
            log.info(f"Nothing is playing, silence start: {silence_start}")
            if isinstance(silence_start, datetime):     
                log.info(f"Silence for {datetime.now() - silence_start}")
                if datetime.now() - silence_start > timedelta(minutes=3):
                    log.info("🔇 Turning OFF stereo after 3 minutes of silence")
                    turn_off() 
            else:  
                set_silence_start_now()
                log.info(f"Set silence start to now: {get_state_datetime(VAR_SILENCE_START)}")

# Not depending on stated, turn stereo playing chotm cast on
@mqtt_trigger("zigbee2mqtt/big_yellow_button")
def on_big_yellow_button(payload=None):
    try:
        data = json.loads(payload)
        action = data.get("action")
        if action == "single":
            log.info("🟡 Big yellow button pressed single") 
            service.call("switch", "turn_on", entity_id=SWITCH)
            select_audio_cast_sound_input()
        elif action == 'hold':
            log.info("🟡 Big yellow button pressed hold")
            service.call("switch", "turn_off", entity_id=SWITCH)
            turn_off()    
    except Exception as e:
        log.error(f"Error decoding payload: {e}")       

@mqtt_trigger("zigbee2mqtt/white_knob")
def on_white_knob(payload=None):
    try:
        data = json.loads(payload)
        log.info(f"decoded white_knob: {data}")
        action = data.get("action")
        if action == "rotate_right":  
            volume_up()
        elif action == "rotate_left":
            volume_down()
    except Exception as e:
        log.error(f"Error decoding payload: {e}")       
