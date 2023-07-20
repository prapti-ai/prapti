"""
    Interpret commands
        command processing :
            update message sequence in-place
            update configuration in-place
"""
import re

from ._core_execution_state import get_private_core_state
from .execution_state import ExecutionState
from .configuration import assign_configuration_field
from .command_message import Command, Message
from .action import Action

def _join_alternatives(alternatives: list[str]):
    return ", ".join(alternatives[:-1]) + " or " + alternatives[-1]

def run_action(has_exclamation: bool, action_name: str, raw_args: str, state: ExecutionState) -> None|str|Message:
    core_state = get_private_core_state(state)
    #state.log.debug(f"running action '{'!' if has_exclamation else ''}{action_name}' with raw args '{raw_args}'")

    matches: list[Action] = core_state.actions.lookup_action(action_name)
    match len(matches):
        case 0:
            state.log.error("action-not-found", f"could not find action {action_name}")
        case 1:
            action = matches[0]
            if action.exclamation_only and not has_exclamation:
                state.log.error("excl-only-action-without-excl", f"action '{action_name}' is !-only but written without a '!'")
                return None
            return action.function(action_name, raw_args, state)
        case _:
            alternatives = _join_alternatives([action.qualified_name for action in matches])
            state.log.error("ambiguous-action-name", f"action name '{action_name}' is ambiguous, did you mean: {alternatives}")
    return None

# process '%' commands -------------------------------------------------------
# i.e. set configuration fields and run actions

command_regex = re.compile(r"^(!)?\s*([\w\-_./\\]+)(?:\s*(=)|\s+|$)(.*)")
# Regex that matches valid command text (starting with the first non-whitespace
# character after the '%')
# Explanation:
# - `^(!)?` matches an optional exclamation mark at the beginning of the command.
# - `\s*` matches zero or more whitespace characters (spaces and tabs).
# - `([\w\-_./\\]+)` matches the command name. It allows alphanumeric characters, hyphens,
#   underscores, periods, forward slashes, and backslashes.
# - `(?:\s*(=)|\s+|$)` matches either optional whitespace followed by an equal sign (`\s*(=)`)
#   or more whitespace characters (`\s+`) or the end of input(`$`). The `=` is captured as a separate group.
# - `(.*)` matches any remaining characters after the command, if any.

def _interpret_command(command_text: str, is_final_message: bool, state: ExecutionState) -> None|str|Message:
    """
    Interpret one command

    Recognised commands are of two types: 1. assignment, 2. action
    The syntax of a command (after the '%') is either"
      [!] action-name [... args ...]
    or
      [!] field-name = value string
    where action-name and field-name have the same permitted characters: alphanumeric, -_.\/
    """
    result = None
    if match := re.match(command_regex, command_text):
        has_exclamation = bool(match.group(1))
        name = match.group(2)
        equals_sign = match.group(3)
        RHS = match.group(4).strip() if match.group(4) else ""
        #state.log.debug(f"{has_exclamation = }, {name = }, {equals_sign = }, {RHS = }")

        if not has_exclamation or (has_exclamation and is_final_message): # has_exclamation commands only run in final message
            if equals_sign:
                # assignment:
                if len(RHS) == 0: # missing right hand side of assignment
                    state.log.warning("skiping-empty-assignment", f"skipping assignment command with no right-hand-side '{command_text}'")
                else:
                    assign_configuration_field(state.root_config, name, RHS, state.log)
            else:
                # action:
                result = run_action(has_exclamation, name, RHS, state)
    else:
        state.log.warning("unknown-command", f"warning: could not interpret command '{command_text}'")
    return result

def interpret_commands(message_sequence: list[Message], state: ExecutionState) -> None:
    """"for each enabled message in the sequence, interpret enabled commands. store command results in command.result field"""
    final_message = message_sequence[-1] # FIXME: this won't work as intened if we invoke interpret_commands multiple times e.g. for config files
    for message in message_sequence:
        if message.is_enabled():
            is_final_message = message is final_message
            for item in message.content:
                if isinstance(item, Command) and item.is_enabled():
                    item.result = _interpret_command(command_text=item.text, is_final_message=is_final_message, state=state)
