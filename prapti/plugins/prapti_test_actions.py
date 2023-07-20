"""
    test actions

    see test_actions.md for testing
"""
from typing import Optional

from ..core.execution_state import ExecutionState
from ..core.plugin import Plugin
from ..core.action import ActionNamespace
from ..core.command_message import Message

_actions: ActionNamespace = ActionNamespace()

@_actions.add_action("test.test")
def test_test(name: str, raw_args: str, state: ExecutionState) -> None|str|Message:
    state.log.debug(f"test.test {name = }, {raw_args = }, {state.root_config = }")
    return None

@_actions.add_action("teest.test")
def teest_test(name: str, raw_args: str, state: ExecutionState) -> None|str|Message:
    state.log.debug(f"teest.test {name = }, {raw_args = }, {state.root_config = }")
    return None

@_actions.add_action("teast.test")
def teast_test(name: str, raw_args: str, state: ExecutionState) -> None|str|Message:
    state.log.debug(f"teast.test {name = }, {raw_args = }, {state.root_config = }")
    return None

class TestActionsPlugin(Plugin):
    def __init__(self):
        super().__init__(
            api_version = "0.1.0",
            name = "prapti.test.actions",
            version = "0.0.1",
            description = "Test actions"
        )

    def construct_actions(self) -> Optional['ActionNamespace']:
        return _actions

prapti_plugin = TestActionsPlugin()
