"""
    Actions for including content into the chat.
"""
import pathlib
from typing import Optional

from ..core.plugin import Plugin
from ..core.action import ActionNamespace
from ..core.command_message import Message

_actions: ActionNamespace = ActionNamespace()

# ----------------------------------------------------------------------------
# /// DANGER -- UNDER CONSTRUCTION ///////////////////////////////////////////

@_actions.add_action("include.code")
def include_code(name: str, raw_args: str, state: 'ExecutionState') -> None|str|Message:

    path = pathlib.Path(raw_args.strip().strip("'\""))
    if not path.is_absolute():
        containing_directory = state.file_name.resolve().parent
        path = containing_directory / path

    file_content = path.read_text(encoding="utf-8").strip()
    language = "python" # FIXME derive from file type
    result = f"```{language}:{path.name}\n" + file_content + "\n```\n"
    return result

# ^^^ END UNDER CONSTRUCTION /////////////////////////////////////////////////
# ----------------------------------------------------------------------------

class IncludePlugin(Plugin):
    def __init__(self):
        super().__init__(
            api_version = "0.1.0",
            name = "prapti.include",
            version = "0.0.1",
            description = "Commands for including file contents"
        )

    def construct_actions(self) -> Optional['ActionNamespace']:
        return _actions

prapti_plugin = IncludePlugin()
