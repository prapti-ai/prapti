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

# As for the number of languages that markdown code blocks officially use,
# it's not limited by markdown itself but by the platform that renders the markdown.
# For example, GitHub's markdown rendering supports
# [hundreds of languages](https://github.com/github/linguist/blob/master/lib/linguist/languages.yml).
def get_markdown_language(file_extension):
    language_map = {
        ".py": "python",
        ".md": "markdown",
        ".js": "javascript",
        ".html": "html",
        ".htm": "html",
        ".css": "css",
        ".java": "java",
        ".c": "c",
        ".h": "c",
        ".cpp": "cpp",
        ".hpp": "cpp",
        ".cc": "cpp",
        ".hh": "cpp",
        ".cxx": "cpp",
        ".hxx": "cpp",
        ".c++": "cpp",
        ".h++": "cpp",
    }
    return language_map.get(file_extension, "")

@_actions.add_action("include.code")
def include_code(name: str, raw_args: str, state: 'ExecutionState') -> None|str|Message:
    """"insert a fenced code block containing the contents of a file"""
    path = pathlib.Path(raw_args.strip().strip("'\""))
    if not path.is_absolute():
        containing_directory = state.file_name.resolve().parent
        path = containing_directory / path

    # TODO: support a --language argument. we're never going to cover every language
    language = get_markdown_language(path.suffix)

    file_content = path.read_text(encoding="utf-8").strip()

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
