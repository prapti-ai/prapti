"""
    Responders take a message sequence and generate one or more responses.

    Typically they are adapters to LLM APIs, but they could also be multi-prompt engines
    that run agents, tree-of-thoughts prompting routines and the like.
"""
import abc
from typing import Any, AsyncGenerator
from dataclasses import dataclass

from pydantic import BaseModel
from cancel_token import CancellationToken

from .command_message import Message
from .configuration import RootConfiguration, VarRef
from .logger import DiagnosticsLogger

@dataclass
class ResponderContext:
    state: 'ExecutionState'
    plugin_name: str
    root_config: RootConfiguration
    plugin_config: Any
    responder_config: Any
    # NOTE: ^^^ responder_config will be None before construct_configuration is called
    responder_name: str
    responder: 'Responder'
    log: DiagnosticsLogger

class Responder(metaclass=abc.ABCMeta):
    """Base class for responders"""

    def construct_configuration(self, context: ResponderContext) -> BaseModel|tuple[BaseModel, list[tuple[str,VarRef]]]|None:
        return None

    @abc.abstractmethod
    def generate_responses(self, input_: list[Message], cancellation_token: CancellationToken, context: ResponderContext) -> AsyncGenerator[Message, None]:
        pass
