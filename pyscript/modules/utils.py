
from datetime import datetime

try:
    # For the linter
    from pyscript_types import state
except ImportError:
    # When running in Jupyter
    pass

def set_state_bool(name: str, value: bool) -> None:
    if value:
        state.set(f"pyscript.{name}", 'true')
    else:
        state.set(f"pyscript.{name}", 'false')

def get_state_bool(name: str) -> bool:
    return state.get(f"pyscript.{name}") == 'true'

def set_state_datetime(name: str, value: datetime) -> None:
    state.set(f"pyscript.{name}", value.isoformat())

def set_state_none(name: str) -> None:
    state.set(f"pyscript.{name}", '')

def get_state_datetime(name: str) -> datetime | None:
    try:
        value = state.get(f"pyscript.{name}")
        if value != "":
            return datetime.fromisoformat(value)
    except Exception as e:
        log.error(f"Error getting datetime: {e}")
        return None
    return None

def get_state_int(name: str) -> int:
    try:
        value = state.get(f"pyscript.{name}")
        if value != "":
            return int(value)
    except NameError:
        return 0
    return 0

def state_inc(name: str) -> None:
    value = get_state_int(name)
    state.set(f"pyscript.{name}", str(value + 1))