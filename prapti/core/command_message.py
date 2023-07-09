"""
    Command/Message sequence

    Abstraction of a markdown chat document as a sequence of
    chat Messages, each of which may contain interjecting Commands.
"""
from dataclasses import dataclass, field
from typing import Any

@dataclass
class Command:
    text: str # begins with the first non-whitespace character after '%', does not include trailing '\n'
    _is_enabled: bool = True
    result: None|str|Any = None # None|str|'Message'

    def is_enabled(self):
        return self._is_enabled

    def result_is_empty(self):
        # non-None non-empty action result
        return self.result is None or (isinstance(self.result, str) and (len(self.result) == 0 or self.result.isspace()))

@dataclass
class Message:
    role: str
    name: str|None
    content: list[str|Command|None]
        # ^^^ allow embedded inline commands e.g. for file inclusion
        # also allow "None" items so that command outputs can be re-written to None without otherwise modifying the list
    _is_enabled: bool = True

    def is_enabled(self) -> bool:
        return self._is_enabled

    def is_private(self) -> bool:
        return self.role.startswith("_")

    def content_is_empty(self) -> bool:
        for item in self.content:
            if isinstance(item, Command) and not item.result_is_empty():
                return False
            if isinstance(item, str) and len(item) != 0 and not item.isspace():
                return False
        return True

def flatten_message_content(messages: list[Message]) -> list[Message]:
    """
        rewrite each message's content in place to be a single string which is the concatenation of
        individual segments of input text, and/or the output of commands/actions.
        at the same time any collect response messages emitted by actions.

        :returns: response messages emitted by actions

        TODO: adjacent segments should be merged using the longest number of blank lines at either
        source or target.
        TODO: actions should be able to emit not only response messages but also messages
        that are inserted before/after the current message, at the beginning or end of the message sequence,
        after the current system prompt, etc.
    """
    response_messages = []
    for message in messages:
        content_strs = []
        for item in message.content:
            if isinstance(item, str):
                content_strs.append(item)
            elif isinstance(item, Command):
                if isinstance(item.result, str):
                    content_strs.append(item.result)
                elif isinstance(item.result, Message):
                    response_messages.append(item.result)
        message.content = ["".join(content_strs).strip()]
    #print(response_messages)
    return response_messages
