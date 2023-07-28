"""
    test plugin with non-empty config
"""
import typing
from pydantic import BaseModel, Field, ConfigDict
from ..core.plugin import Plugin

class TestConfigConfiguration(BaseModel):
    """Configuration parameters for the prapti.test.test_config plugin"""
    model_config = ConfigDict(
        validate_assignment=True)

    a_bool: bool = False
    an_int: int = 0
    a_float: float = 0.0
    a_string: str = "test"
    a_list_of_strings: list[str] = Field(default_factory=list)

class TestConfigPlugin(Plugin):
    def __init__(self):
        super().__init__(
            api_version = "0.1.0",
            name = "prapti.test.test_config",
            version = "0.0.1",
            description = "Plugin used to test Prapti"
        )

    def construct_configuration(self) -> typing.Any|None:
        return TestConfigConfiguration()

prapti_plugin = TestConfigPlugin()
