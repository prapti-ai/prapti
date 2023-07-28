"""
    Test responder plugin
"""
import typing

from pydantic import BaseModel, ConfigDict, Field

from ..core.plugin import Plugin
from ..core.command_message import Message
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
    def __init__(self):
        super().__init__()

    def construct_configuration(self, context: ResponderContext) -> typing.Any|None:
        return TestResponderConfiguration()

    def generate_responses(self, input_: list[Message], context: ResponderContext) -> list[Message]:
        config: TestResponderConfiguration = context.responder_config
        context.log.debug(f"prapti.test.test_responder: {config = }", context.state.input_file_path)

        # propagate late-bound global variables:
        for name in ("model", "temperature", "n"):
            if (value := getattr(context.root_config.vars, name, None)) is not None:
                context.log.debug(f"openai.chat: binding config.{name} <- {value} from vars.{name}", context.state.input_file_path)
                setattr(config, name, value)

        context.state.test_exfil["test_responder_resolved_config"] = config

        return [Message(role="assistant", name=None, content=["Test!"])]

class TestResponderPlugin(Plugin):
    def __init__(self):
        super().__init__(
            api_version = "0.1.0",
            name = "prapti.test.test_responder",
            version = "0.0.1",
            description = "Test responder"
        )

    def construct_responder(self) -> Responder|None:
        return TestResponder()

prapti_plugin = TestResponderPlugin()
