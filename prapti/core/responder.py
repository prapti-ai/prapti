"""
    Responders take a message sequence and generate one or more responses.

    Typically they are adapters to LLM APIs, but they could also be multi-prompt engines
    that run agents, tree-of-thoughts prompting routines and the like.
"""
import abc
from typing import Any, Optional
from dataclasses import dataclass

from .command_message import Message
from .configuration import RootConfiguration

@dataclass
class ResponderContext:
    plugin_name: str
    root_config: RootConfiguration
    plugin_config: Any
    responder_config: Any
    # NOTE: ^^^ responder_config will be an EmptyResponderConfiguration before construct_configuration is called
    responder_name: str
    responder: 'Responder'

class Responder(metaclass=abc.ABCMeta):
    """Base class for responders"""

    @abc.abstractmethod
    def construct_configuration(self, context: ResponderContext) -> Optional[Any]:
        pass

    @abc.abstractmethod
    def generate_responses(self, input: list[Message], context: ResponderContext) -> list[Message]:
        pass
