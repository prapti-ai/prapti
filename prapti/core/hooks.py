"""
    Hooks are low-level extension points that are invoked at various phases of processing
"""
from dataclasses import dataclass
import typing

from .execution_state import ExecutionState
from .configuration import RootConfiguration
from .command_message import Message

@dataclass
class HooksContext:
    state: ExecutionState
    root_config: RootConfiguration
    plugin_config: typing.Any
    hooks: 'Hooks'

# ----------------------------------------------------------------------------
# /// DANGER -- UNDER CONSTRUCTION ///////////////////////////////////////////
# we're still exploring the design space for hooks

class Hooks:
    """Base class for hooks"""

    def on_plugin_loaded(self, context: HooksContext):
        pass

    def on_generating_response(self, context: HooksContext):
        pass

    def on_lookup_active_responder(self, responder_name: str, context: HooksContext) -> str:
        return responder_name

    def on_response_completed(self, context: HooksContext):
        pass

class HooksDistributor:
    def __init__(self):
        self._hooks_contexts: list[HooksContext] = []

    def add_hooks(self, hooks_context: HooksContext):
        self._hooks_contexts.append(hooks_context)

    def remove_hooks(self, hooks_context: HooksContext):
        self._hooks_contexts.remove(hooks_context)

    def on_plugin_loaded(self):
        for context in self._hooks_contexts:
            context.hooks.on_plugin_loaded(context)

    def on_generating_response(self):
        for context in self._hooks_contexts:
            context.hooks.on_generating_response(context)

    def on_lookup_active_responder(self, responder_name: str) -> str:
        for context in self._hooks_contexts:
            responder_name = context.hooks.on_lookup_active_responder(responder_name, context)
        return responder_name

    def on_response_completed(self):
        for context in self._hooks_contexts:
            context.hooks.on_response_completed(context)

# ^^^ END UNDER CONSTRUCTION /////////////////////////////////////////////////
# ----------------------------------------------------------------------------
