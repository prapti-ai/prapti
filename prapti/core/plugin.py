"""
    Plugins are dynamically loaded extensions.
"""
from enum import Flag, auto
from typing import Any
from dataclasses import dataclass

from pydantic import BaseModel

from ..core.execution_state import ExecutionState
from ..core.action import ActionNamespace
from ..core.hooks import Hooks
from ..core.responder import Responder
from ..core.configuration import RootConfiguration, VarRef
from ..core.logger import DiagnosticsLogger

class PluginCapabilities(Flag):
    ACTIONS = auto()
    HOOKS = auto()
    RESPONDER = auto()

@dataclass
class PluginContext:
    state: ExecutionState
    plugin_name: str
    root_config: RootConfiguration
    plugin_config: Any
    # NOTE: ^^^ plugin_config will be None before construct_configuration is called
    log: DiagnosticsLogger

class Plugin:
    """Base class for plugins"""
    def __init__(self, api_version: str, name: str, version: str, description: str, capabilities: PluginCapabilities):
        self.api_version: str = api_version
        self.name: str = name
        self.version: str = version
        self.description: str = description
        self.capabilities: PluginCapabilities = capabilities

    def construct_configuration(self, context: PluginContext) -> BaseModel|tuple[BaseModel, list[tuple[str,VarRef]]]|None:
        return None

    def construct_actions(self, context: PluginContext) -> ActionNamespace|None:
        return None

    def construct_hooks(self, context: PluginContext) -> Hooks|None:
        return None

    def construct_responder(self, context: PluginContext) -> Responder|None:
        return None
