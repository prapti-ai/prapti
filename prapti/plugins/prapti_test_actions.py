"""
    test actions

    see test_actions.md for testing
"""
from ..core.plugin import Plugin, PluginCapabilities
from ..core.action import ActionNamespace, ActionContext
from ..core.command_message import Message

_actions: ActionNamespace = ActionNamespace()

@_actions.add_action("test.test")
def test_test(name: str, raw_args: str, context: ActionContext) -> None|str|Message:
    context.log.debug(f"test.test {name = }, {raw_args = }, {context.root_config = }", context.source_loc)
    return None

@_actions.add_action("teest.test")
def teest_test(name: str, raw_args: str, context: ActionContext) -> None|str|Message:
    context.log.debug(f"teest.test {name = }, {raw_args = }, {context.root_config = }", context.source_loc)
    return None

@_actions.add_action("teast.test")
def teast_test(name: str, raw_args: str, context: ActionContext) -> None|str|Message:
    context.log.debug(f"teast.test {name = }, {raw_args = }, {context.root_config = }", context.source_loc)
    return None

class TestActionsPlugin(Plugin):
    def __init__(self):
        super().__init__(
            api_version = "0.1.0",
            name = "prapti.test.test_actions",
            version = "0.0.1",
            description = "Actions used to test Prapti",
            capabilities = PluginCapabilities.ACTIONS
        )

    def construct_actions(self) -> ActionNamespace|None:
        return _actions

prapti_plugin = TestActionsPlugin()
