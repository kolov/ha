from typing import Any, Callable, Dict, Optional, Union, Protocol
from datetime import datetime

# Global variables
audio_cast_playing: bool
tv_playing: bool
speaker_sound: bool

# State management
class State:
    def get(self, entity_id: str) -> str: ...
    def set(self, entity_id: str, value: Any) -> None: ...

state: State

# Service calls
class Service:
    def call(self, domain: str, service: str, **kwargs: Any) -> None: ...

service: Service

# Task management
class Task:
    @staticmethod
    def sleep(seconds: float) -> None: ...
    
    @staticmethod
    def unique(name: str, kill_me: bool = False) -> None: ...

task: Task

# Logging
class Log:
    def info(self, message: str) -> None: ...
    def warning(self, message: str) -> None: ...
    def error(self, message: str) -> None: ...

log: Log

# Decorators
def state_trigger(trigger: str) -> Callable: ...
def time_trigger(trigger: str) -> Callable: ... 