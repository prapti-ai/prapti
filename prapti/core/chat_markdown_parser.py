"""
    Parse a chat markdown document into a sequence of messages
"""
import re

from .command_message import Command, Message

# match message delimiter headings, typically "### @system:", "### @user:", "### @assistant:"
# a level-3 ATX heading https://spec.commonmark.org/0.30/#atx-headings
message_delimiter_regex = re.compile(r"^[ ]{0,3}###\s+(\/\/)?\s*@([\w]+)(?:\/([\w]+))?:?\s*\n")

# match single-line "commands" which are lines starting with % (optionally prefixed with >)
# TODO: don't match commands inside <!-- --> comments or inside fenced blocks
command_line_regex = re.compile(r"^(?:\>\s*)?(\/\/)?\s*%\s*(.*)\n")

def parse_messages(lines: list[str]) -> list[Message]:
    """partition lines of a chat markdown document into a sequence of messages."""
    current_message = Message(role="_head", name=None, content=[], _is_enabled=True)
    result = [current_message]
    for line in lines:
        if not line.endswith("\n"):
            line = line + "\n" # make sure the final line parses correctly

        if command_match := re.match(command_line_regex, line):
            is_enabled = command_match.group(1) != "//"
            current_message.content.append(Command(text=command_match.group(2).strip(), _is_enabled=is_enabled))

        elif message_match := re.match(message_delimiter_regex, line):
            # found message delimeter
            is_enabled = message_match.group(1) != "//"
            role = message_match.group(2)
            name = message_match.group(3) if message_match.group(3) else None

            if not role.startswith("_"):
                # validate non-private roles
                if role not in ["system", "user", "assistant"]:
                    print(f"warning: found unknown role '{role}'")

            # start new message
            current_message = Message(role=role, name=name, content=[], _is_enabled=is_enabled)
            result.append(current_message)
        else:
            # append line to current mesage content
            if current_message.content and isinstance(current_message.content[-1], str): #check for non-empty before accessing last element
                current_message.content[-1] += line
            else:
                current_message.content.append(line) # start a new string span

    return result
