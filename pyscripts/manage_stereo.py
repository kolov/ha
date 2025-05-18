from datetime import datetime, timedelta
from typing import Any, Dict

try:
    # For the linter
    from pyscript_types import state, service, task, log, state_trigger, time_trigger, pyscript
except ImportError:
    # When running in Jupyter
    pass

SPLITTER_AUDIO_CAST: str = 'B+cjexGwAscB4BUDATgG4CED4CtLByyc5yOkCLAC'
SPLITTER_TV: str = 'BbMjrxFAAuAXAQGjBuAZA8ABwCvgBwHgBxfAD0AHD3+csyO2CIAC//+zI7YIQAI='
SWITCH: str = "switch.stereo_amplifier"
IR_TEXT_ENTITY: str = "text.ab35847d2a960e673d91dc3955ea60ef"

last_off_time: datetime = datetime.now()

def audio_cast_state() -> str:
    return state.get("media_player.living_room_speaker")

def set_audio_cast_playing(audio_cast_state: str) -> None:
    pyscript.audio_cast_playing = audio_cast_state in ['playing', 'buffering']

set_audio_cast_playing(audio_cast_state())

@state_trigger("media_player.living_room_speaker")
def update_audio_cast_playing(**kwargs: Dict[str, Any]) -> None:
    log.info(f"🎶 Audio cast changed: {kwargs["old_value"]} → {kwargs["value"]}")
    set_audio_cast_playing(audio_cast_state())
    
    if pyscript.audio_cast_playing:
        log.info("📡 Sending audio cast IR code")
        service.call("text", "set_value", 
                    entity_id=IR_TEXT_ENTITY,
                    value=SPLITTER_AUDIO_CAST)

def tv_state() -> str:
    return state.get("media_player.lg_webos_tv_85c7")

def set_tv_playing(tv_state: str) -> None:
    pyscript.tv_playing = tv_state in ['on']
    
set_tv_playing(tv_state())

@state_trigger("media_player.lg_webos_tv_85c7")
def update_tv_playing(**kwargs: Dict[str, Any]) -> None:
    new_state=kwargs["value"]
    log.info(f"🎶 Tv changed: {kwargs["old_value"]} → {new_state}")
    set_tv_playing(new_state)
    
    if pyscript.tv_playing:
        log.info("📡 Sending TV IR code")
        service.call("text", "set_value", 
                    entity_id=IR_TEXT_ENTITY,
                    value=SPLITTER_TV)

def to_bool(v):
    return str(v).lower() in ["true", "on", "1"]

def set_speaker_sound(audio_cast_playing, tv_playing):
    if to_bool(audio_cast_playing) or to_bool(tv_playing):
        pyscript.speaker_sound = 'on'
    else:
        pyscript.speaker_sound = 'off'
    
set_speaker_sound(pyscript.audio_cast_playing, pyscript.tv_playing)

@state_trigger("pyscript.audio_cast_playing or pyscript.tv_playing")
def on_something_playing_changed() -> None:
    log.info(f"some sound source changed. pyscript.audio_cast_playing={pyscript.audio_cast_playing}, pyscript.tv_playing={pyscript.tv_playing}")
    set_speaker_sound(pyscript.audio_cast_playing, pyscript.tv_playing) 
    log.info(f"Set speaker_sound to {pyscript.speaker_sound}")

@state_trigger("pyscript.speaker_sound == 'off'")
def start_off_timer() -> None:
    state.set("pyscript.silence_start", datetime.now().isoformat())
    
def set_silence_start(s):
    pyscript.silence_start=s

set_silence_start("")

@state_trigger("pyscript.speaker_sound == 'on'")
async def turn_on_amp() -> None:
    task.unique("turn_on_amp", kill_me=True)
    global last_off_time

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
        set_silence_start("")
    else:
        log.info(f"🔊 Stereo is already {switch_state}")

@time_trigger("cron(* * * * *)")
def turn_off_if_silent() -> None:
    silence_start_str = pyscript.silence_start
    if silence_start_str != "":
        silence_start = datetime.fromisoformat(silence_start_str)
        if datetime.now() - silence_start > timedelta(minutes=3):
            if state.get(SWITCH) == "on":
                log.info("🔇 Turning OFF stereo after 3 minutes of silence")
                service.call("switch", "turn_off", entity_id=SWITCH)
                global last_off_time
                last_off_time = datetime.now()
                set_silence_start("")
    