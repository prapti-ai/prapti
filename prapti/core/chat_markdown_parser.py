"""
    Parse a chat markdown document into a sequence of messages
"""
import re
import pathlib

from .command_message import Command, Message
from .source_location import SourceLocation

# match message delimiter headings, typically "### @system:", "### @user:", "### @assistant:"
# a level-3 ATX heading https://spec.commonmark.org/0.30/#atx-headings
message_delimiter_regex = re.compile(r"^[ ]{0,3}###\s+(\/\/)?\s*@([\w]+)(?:\/([\w]+))?:?\s*\n")

# match single-line "commands" which are lines starting with % (optionally prefixed with >)
# TODO: don't match commands inside <!-- --> comments or inside fenced blocks
command_line_regex = re.compile(r"^(?:[ ]{0,3}\>\s*)?(\/\/)?\s*%\s*(.*)\n")

def parse_messages(lines: list[str], file_path: pathlib.Path|None) -> list[Message]:
    """partition lines of a chat markdown document into a sequence of messages."""
    current_message = Message(role="_head", name=None, content=[], _is_enabled=True, source_loc=SourceLocation(file_path=file_path, line=0))
    result = [current_message]
    for line_no, line in enumerate(lines, start=1):
        if not line.endswith("\n"):
            line = line + "\n" # make sure the final line parses correctly

        if command_match := re.match(command_line_regex, line):
            is_enabled = command_match.group(1) != "//"
            source_loc = SourceLocation(file_path=file_path, line=line_no)
            current_message.content.append(Command(text=command_match.group(2).strip(), _is_enabled=is_enabled, source_loc=source_loc))

        elif message_match := re.match(message_delimiter_regex, line):
            # found message delimeter
            is_enabled = message_match.group(1) != "//"
            role = message_match.group(2)
            name = message_match.group(3) if message_match.group(3) else None

            # start new message
            source_loc = SourceLocation(file_path=file_path, line=line_no)
            current_message = Message(role=role, name=name, content=[], _is_enabled=is_enabled, source_loc=source_loc)
            result.append(current_message)
        else:
            # append line to current mesage content
            if current_message.content and isinstance(current_message.content[-1], str): #check for non-empty before accessing last element
                current_message.content[-1] += line
            else:
                current_message.content.append(line) # start a new string span

    return result
