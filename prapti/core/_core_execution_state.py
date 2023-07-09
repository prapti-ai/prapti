"""
    Private data used by core only. You shouldn't be here unless you're working on core.
"""
from dataclasses import dataclass, field

from .plugin import Plugin
from .action import ActionNamespace
from .responder import ResponderContext
from .hooks import HooksDistributor
from .execution_state import ExecutionState

@dataclass
class CoreExecutionState: # private to core
    loaded_plugins: set[Plugin] = field(default_factory=set)
    actions: ActionNamespace = field(default_factory=ActionNamespace)
    responder_contexts: dict[str, ResponderContext] = field(default_factory=dict) # keyed by responder instance name
    hooks_distributor: HooksDistributor = field(default_factory=HooksDistributor)

def get_private_core_state(state: ExecutionState) -> CoreExecutionState:
    """
        `state._core_state` is the back-door into the private details of core.
        this function is the access point to very low-level details
        that should only be manipulated by the core part of the package.
    """
    if not isinstance(state._core_state, CoreExecutionState):
        raise TypeError("expected a private CoreExecutionState")
    return state._core_state # intentional access of protected member
