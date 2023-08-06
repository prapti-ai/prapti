"""
    Plugins are dynamically loaded extensions.
"""
from enum import Flag, auto

from pydantic import BaseModel

from ..core.action import ActionNamespace
from ..core.hooks import Hooks
from ..core.responder import Responder
from ..core.configuration import VarRef
from ..core.logger import DiagnosticsLogger

class PluginCapabilities(Flag):
    ACTIONS = auto()
    HOOKS = auto()
    RESPONDER = auto()

class Plugin:
    """Base class for plugins"""
    def __init__(self, api_version: str, name: str, version: str, description: str, capabilities: PluginCapabilities):
        self.api_version: str = api_version
        self.name: str = name
        self.version: str = version
        self.description: str = description
        self.capabilities: PluginCapabilities = capabilities

    def construct_configuration(self) -> BaseModel|tuple[BaseModel, list[tuple[str,VarRef]]]|None:
        return None

    def construct_actions(self) -> ActionNamespace|None:
        return None

    def construct_hooks(self) -> Hooks|None:
        return None

    def construct_responder(self) -> Responder|None:
        return None
