""""
    Automatically capture each prapti run to a file.
"""
from pathlib import Path
import os
from uuid import uuid1
from datetime import datetime
import json
import platform
import getpass
import inspect
from typing import Any
import time

from pydantic import BaseModel, Field

from ..core.builtins import get_loaded_plugins_info
from ..core.plugin import Plugin, PluginCapabilities, PluginContext
from ..core.hooks import Hooks, HooksContext
from ..core.configuration import VarRef, resolve_var_refs
from ..core.command_message import Message

class CaptureEverythingPluginConfiguration(BaseModel):
    capture_dir: str|None = Field(default=None, description=inspect.cleandoc("""\
        Directory where capture files will be written."""))

def make_capture_file_name(now: datetime) -> str:
    return now.strftime("%Y-%m-%d-%H%M%S-%f")+f"-{uuid1()}.json"

def format_datetime(t: datetime) -> str:
    return t.strftime("%Y-%m-%d %H:%M:%S,%f") # timestamp, including microseconds
    # NOTE: read back with datetime.strptime(t_str, "%Y-%m-%d %H:%M:%S,%f")

def get_user_and_system_info() -> dict:
    system, release, version = platform.system(), platform.release(), platform.version()
    result = {
        "user_name": getpass.getuser(),
        "network_name": platform.node(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "platform": platform.platform(aliased=False),
        "platform_aliased": platform.platform(aliased=True),
        "system_alias": platform.system_alias(system, release, version),
        "system": system,
        "release": release,
        "version": version,
    }
    return result

def get_python_info() -> dict:
    buildno, builddate = platform.python_build()
    result = {
        "implementation": platform.python_implementation(),
        "version": platform.python_version(),
        "revision": platform.python_revision(),
        "branch": platform.python_branch(),
        "buildno": buildno,
        "builddate": builddate,
        "compiler": platform.python_compiler(),
    }
    return result

def get_file_dump(file_path: Path) -> dict:
    creation_date = datetime.fromtimestamp(os.path.getctime(file_path))
    modified_date = datetime.fromtimestamp(os.path.getmtime(file_path))
    result = {
        "path": str(file_path),
        "creation_date": format_datetime(creation_date),
        "modified_date": format_datetime(modified_date),
        "contents": file_path.read_text(),
    }
    return result

def message_sequence_to_json(message_sequence: list[Message]) -> list[dict[str, Any]]:
    return  [
        {
            "role": message.role,
            "name": message.name,
            "content": message.content,
            "is_enabled": message.is_enabled,
            "source_loc": {
                "file_path": str(message.source_loc.file_path) if message.source_loc.file_path else None,
                "line": message.source_loc.line
            }
        }
        for message in message_sequence
    ]

class CaptureEverythingHooks(Hooks):
    def __init__(self):
        self._capture_file_name: str|None = None
        self._capture_data: dict[str, Any] = { "content_type": "prapti.capture_everything/prapti_run/v1"}
        self._generating_response_start_time = 0

    def on_plugin_loaded(self, context: HooksContext):
        self._start_time = datetime.now()
        self._capture_data["start_time"] = format_datetime(self._start_time)
        self._capture_file_name = make_capture_file_name(self._start_time) # do this here to use start timestamp

        input_file_path = context.state.input_file_path.resolve()
        self._capture_data["input_file"] = get_file_dump(input_file_path)

    def on_generating_response(self, context: HooksContext):
        # full processed message sequence, just prior to sending to LLM
        self._capture_data["processed_input_message_sequence"] = message_sequence_to_json(context.state.message_sequence)
        self._generating_response_start_time = time.perf_counter()

    def on_response_completed(self, context: HooksContext):
        self._capture_data["response_time_seconds"] = time.perf_counter() - self._generating_response_start_time

        if context.root_config.prapti.dry_run:
            return

        if not self._capture_file_name:
            context.log.error("bad-capture-file-name", "prapti.capture_everything: skipping capture. no capture file name.")
            return

        self._end_time = datetime.now()
        self._capture_data["end_time"] = format_datetime(self._end_time)

        self._capture_data["prapti_version"] = context.state.prapti_version
        self._capture_data["user_and_system_info"] = get_user_and_system_info()
        self._capture_data["python_info"] = get_python_info()

        self._capture_data["argv"] = context.state.argv # command line args
        self._capture_data["user_prapti_config_dir"] = str(context.state.user_prapti_config_dir)

        self._capture_data["config_files"] = [get_file_dump(config_file_path) for config_file_path in context.state.config_file_paths]

        self._capture_data["loaded_plugins"] = get_loaded_plugins_info(context.state)

        output_file_path = context.state.input_file_path.resolve() # NOTE: output is appended to input file
        self._capture_data["output_file"] = get_file_dump(output_file_path)

        # responses returned by the top-level responder
        self._capture_data["responses"] = message_sequence_to_json(context.state.responses)

        # write the capture file:
        config: CaptureEverythingPluginConfiguration = context.plugin_config
        config = resolve_var_refs(config, context.root_config, context.log)
        if context.plugin_config.capture_dir:
            capture_dir = Path(context.plugin_config.capture_dir).resolve()
            if capture_dir.is_dir():
                capture_file_path = capture_dir / self._capture_file_name
                with capture_file_path.open("w") as file:
                    json.dump(self._capture_data, file)
            else:
                context.log.error("bad-capture-dir", f"prapti.capture_everything: skipping capture. capture directory '{capture_dir}' does not exist or is not a directory")
        else:
            context.log.warning("capture-dir-not-set", "prapti.capture_everything: plugin is loaded but capture directory has not been set. add '% prapti.plugins.capture_everything.capture_dir = ... to your config.")

class CaptureEverythingPlugin(Plugin):
    def __init__(self):
        super().__init__(
            api_version = "0.1.0",
            name = "prapti.capture_everything",
            version = "0.0.1",
            description = "Automatically capture each prapti run to a file",
            capabilities = PluginCapabilities.HOOKS
        )

    def construct_configuration(self, context: PluginContext) -> BaseModel|tuple[BaseModel, list[tuple[str,VarRef]]]|None:
        return CaptureEverythingPluginConfiguration()

    def construct_hooks(self, context: PluginContext) -> Hooks|None:
        return CaptureEverythingHooks()

prapti_plugin = CaptureEverythingPlugin()
