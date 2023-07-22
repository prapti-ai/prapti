"""
    Plugins are dynamically loaded extensions.
"""
from typing import Any

from ..core.action import ActionNamespace
from ..core.hooks import Hooks
from ..core.responder import Responder

class Plugin:
    """Base class for plugins"""
    def __init__(self, name: str, version: str, description: str, api_version: str):
        self.api_version: str = api_version
        self.name: str = name
        self.version: str = version
        self.description: str = description

    def construct_configuration(self) -> Any|None:
        return None

    def construct_actions(self) -> ActionNamespace|None:
        return None

    def construct_hooks(self) -> Hooks|None:
        return None

    def construct_responder(self) -> Responder|None:
        return None
