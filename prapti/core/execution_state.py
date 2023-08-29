from typing import Any
from dataclasses import dataclass, field
import pathlib

from .logger import DiagnosticsLogger
from .configuration import RootConfiguration
from .command_message import Message

@dataclass
class ExecutionState:
    """
        An ExecutionState is the overall state associated with a single run of
        processing a markdown file and producing responses.
    """
    prapti_version: str
    argv: list[str]
    log: DiagnosticsLogger
    input_file_path: pathlib.Path
    user_prapti_config_dir: pathlib.Path|None = None # typically ~/.config/prapti but other locations are possible
    prapticonfig_dirs: list[pathlib.Path] = field(default_factory=list)
        # ^^^ in-tree config dirs, ordered starting from dir containing input file and proceding towards root
    config_file_paths: [pathlib.Path] = field(default_factory=list) # the config files, in the order that they were loaded
    root_config: RootConfiguration = field(default_factory=RootConfiguration) # root of the configuration tree
    message_sequence: list[Message] = field(default_factory=list)
    responses: list[Message] = field(default_factory=list)

    private_core_state: Any|None = None # private to core. use get_private_core_state() for typesafe access
    test_exfil: dict = field(default_factory=dict) # conduit for test inspection
