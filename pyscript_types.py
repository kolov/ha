from typing import Any, Callable, Dict, Optional, Union, Protocol
from datetime import datetime

class State:
    def get(self, entity_id: str) -> str:
        """Get the state of an entity."""
        ...

    def set(self, entity_id: str, value: Any) -> None:
        """Set the state of an entity."""
        ...

class Service:
    def call(self, domain: str, service: str, **kwargs: Any) -> None:
        """Call a service."""
        ...

class Task:
    @staticmethod
    def sleep(seconds: float) -> None:
        """Sleep for the specified number of seconds."""
        ...

    @staticmethod
    def unique(name: str, kill_me: bool = False) -> None:
        """Ensure only one instance of a task is running."""
        ...

class Log:
    def info(self, message: str) -> None:
        """Log an info message."""
        ...

    def warning(self, message: str) -> None:
        """Log a warning message."""
        ...

    def error(self, message: str) -> None:
        """Log an error message."""
        ...

class Pyscript:
    """Global variables and functions in the pyscript namespace."""
    audio_cast_streaming: bool = False
    tv_playing: bool = False
    speaker_sound: bool = False

# Module-level instances
state: State = State()
service: Service = Service()
task: Task = Task()
log: Log = Log()
pyscript: Pyscript = Pyscript()

def state_trigger(trigger: str) -> Callable:
    """Decorator for state triggers."""
    ...

def time_trigger(trigger: str) -> Callable:
    """Decorator for time triggers."""
    ... 