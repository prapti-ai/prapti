"""
    Test responder plugin
"""
from pydantic import BaseModel, ConfigDict, Field

from ..core.plugin import Plugin, PluginCapabilities, PluginContext
from ..core.command_message import Message
from ..core.configuration import VarRef, resolve_var_refs
from ..core.responder import Responder, ResponderContext

class TestResponderConfiguration(BaseModel):
    """Configuration parameters for test responder."""
    model_config = ConfigDict(
        validate_assignment=True)

    a_bool: bool = False
    an_int: int = 0
    a_float: float = 0.0
    a_string: str = "test"
    a_list_of_strings: list[str] = Field(default_factory=list)

    temperature: int = 1 # used to test late-bound vars
    model: str = "test"
    n: int = 1

class TestResponder(Responder):
    def construct_configuration(self, context: ResponderContext) -> BaseModel|tuple[BaseModel, list[tuple[str,VarRef]]]|None:
        return TestResponderConfiguration(), [("model", VarRef("model")), ("temperature", VarRef("temperature")), ("n", VarRef("n"))]

    def generate_responses(self, input_: list[Message], context: ResponderContext) -> list[Message]:
        config: TestResponderConfiguration = context.responder_config
        context.log.debug(f"prapti.test.test_responder: input: {config = }", context.state.input_file_path)
        config = resolve_var_refs(config, context.root_config, context.log)
        context.log.debug(f"prapti.test.test_responder: resolved: {config = }", context.state.input_file_path)

        context.state.test_exfil["test_responder_resolved_config"] = config

        return [Message(role="assistant", name=None, content=["Test!"])]

class TestResponderPlugin(Plugin):
    def __init__(self):
        super().__init__(
            api_version = "0.1.0",
            name = "prapti.test.test_responder",
            version = "0.0.1",
            description = "Responder used to test Prapti",
            capabilities = PluginCapabilities.RESPONDER
        )

    def construct_responder(self, context: PluginContext) -> Responder|None:
        return TestResponder()

prapti_plugin = TestResponderPlugin()
