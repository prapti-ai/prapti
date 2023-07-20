"""
    Actions are wrappers for functions that are triggered by `%`-commands embedded in the markdown
"""
from dataclasses import dataclass
from typing import Callable, Any
from collections import defaultdict

from .command_message import Message
from .execution_state import ExecutionState
from .configuration import RootConfiguration
from .source_location import SourceLocation
from .logger import DiagnosticsLogger

@dataclass
class ActionContext:
    state: ExecutionState
    root_config: RootConfiguration
    plugin_config: Any
    source_loc: SourceLocation
    log: DiagnosticsLogger

@dataclass
class Action:
    # name can be fully qualified e.g. 'a.b.c' or unqualified eg 'c'
    qualified_name: str
    unqualified_name: str
    function: Callable[[str, str, ActionContext], None|str|Message]
    exclamation_only: bool = False # !-only commands may only appear in markdown with the ! prefix
    plugin_config: Any|None = None

class ActionNamespace:
    def __init__(self):
        # actions keyed by unqualified name
        self._actions: defaultdict[str, list[Action]] = defaultdict(list)

    def merge_into(self, other: 'ActionNamespace'):
        for k,v in self._actions.items():
            other._actions[k] += v

    def _add_action(self, raw_qualified_name: str, function: Callable[[str, str, ActionContext], None|str|Message], exclamation_only:bool|None=None):
        qualified_name = raw_qualified_name.lstrip("!")
        unqualified_name = qualified_name.split(".")[-1]

        # if either the provided qualified name starts with '!' or exclamation_only == True, it's a exclamation_only command
        # otherwise it's not exclamation_only
        name_has_exclamation = raw_qualified_name.startswith("!")
        if name_has_exclamation and exclamation_only is False:
            raise ValueError("conflicting parameters: name starts with '!' indicating !-only, but 'exclamation_only' argument is False")
        exclamation_only = name_has_exclamation or exclamation_only is True
        action = Action(qualified_name=qualified_name, unqualified_name=unqualified_name, function=function, exclamation_only=exclamation_only)
        self._actions[unqualified_name].append(action)

    def add_action(self, raw_qualified_name: str, exclamation_only:bool|None=None):
        """a decorator for adding actions to the namespace"""
        def decorator(func):
            self._add_action(raw_qualified_name=raw_qualified_name, function=func, exclamation_only=exclamation_only)
            return func
        return decorator

    def set_plugin_config(self, plugin_config: Any):
        for _,v in self._actions.items():
            for action in v:
                action.plugin_config = plugin_config

    def lookup_action(self, name: str) -> list[Action]:
        name_components = name.split('.')
        unqualified_name = name_components[-1]
        if matches := self._actions.get(unqualified_name, None):
            if len(matches) == 1:
                return [matches[0]]
            else:
                for action in matches:
                    if action.qualified_name == name:
                        return [action]
                return matches
        return []
