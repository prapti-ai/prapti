"""
    Test responder plugin
"""
from typing import AsyncGenerator

from pydantic import BaseModel, ConfigDict, Field
from cancel_token import CancellationToken

from ..core.plugin import Plugin, PluginCapabilities, PluginContext
from ..core.command_message import Message
from ..core.configuration import VarRef, resolve_var_refs
from ..core.responder import Responder, ResponderContext

class TestResponderPluginConfiguration(BaseModel):
    """Configuration parameters for the prapti.test.test_responder plugin"""
    model_config = ConfigDict(
        validate_assignment=True)

    an_int: int = 0
    a_string: str = "test"

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

    async def _async_response_generator(self, input_: list[Message], cancellation_token: CancellationToken, context: ResponderContext) -> AsyncGenerator[Message, None]:
        plugin_config: TestResponderConfiguration = context.plugin_config
        assert plugin_config is not None
        context.log.debug(f"input: {plugin_config = }", context.state.input_file_path)
        plugin_config = resolve_var_refs(plugin_config, context.root_config, context.log)
        context.log.debug(f"resolved: {plugin_config = }", context.state.input_file_path)

        context.state.test_exfil["test_responder_resolved_plugin_config"] = plugin_config

        responder_config: TestResponderConfiguration = context.responder_config
        assert responder_config is not None
        context.log.debug(f"input: {responder_config = }", context.state.input_file_path)
        responder_config = resolve_var_refs(responder_config, context.root_config, context.log)
        context.log.debug(f"resolved: {responder_config = }", context.state.input_file_path)

        context.state.test_exfil["test_responder_resolved_responder_config"] = responder_config

        yield Message(role="assistant", name=None, content=["Test!"], async_content=None)

    def generate_responses(self, input_: list[Message], cancellation_token: CancellationToken, context: ResponderContext) -> AsyncGenerator[Message, None]:
        return self._async_response_generator(input_, cancellation_token, context)

class TestResponderPlugin(Plugin):
    def __init__(self):
        super().__init__(
            api_version = "1.0.0",
            name = "prapti.test.test_responder",
            version = "0.0.2",
            description = "Responder used to test Prapti",
            capabilities = PluginCapabilities.RESPONDER
        )

    def construct_configuration(self, context: PluginContext) -> BaseModel|tuple[BaseModel, list[tuple[str,VarRef]]]|None:
        return TestResponderPluginConfiguration()

    def construct_responder(self, context: PluginContext) -> Responder|None:
        return TestResponder()

prapti_plugin = TestResponderPlugin()
