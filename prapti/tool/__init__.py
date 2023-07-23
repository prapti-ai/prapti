"""
    Command line tool for generating markdown chat responses
"""
import argparse
import pathlib
from typing import Sequence, TextIO

from ..core.logger import create_diagnostics_logger
from ..core._core_execution_state import CoreExecutionState
from ..core.execution_state import ExecutionState
from ..core.chat_markdown_parser import parse_messages
from ..core.command_interpreter import interpret_commands
from ..core.builtins import builtin_actions, lookup_active_responder
from ..core.command_message import flatten_message_content, Message

from .default_template import get_default_template

fallback_config_file_data = """\
% plugins.load openai.chat
% responder.new default openai.chat
"""

argument_parser = None

def make_argument_parser():
    # create and initialize an ArgumentParser
    result = argparse.ArgumentParser(description="Prapti markdown chat")
    result.add_argument("--dry-run", help="prepare the API request then bail", action="store_true")
    result.add_argument("--strict", help="fail if errors are encountered, do not attempt error recovery", action="store_true")
    result.add_argument("--no-default-config", help="disable default config file search", action="store_true")
    result.add_argument("--config-file", help="specify additional config file(s)", required=False, default=[], action="append")
    # Positional argument for the filename
    result.add_argument("filename", help="the current markdown chat file")
    return result

def parse_messages_and_interpret_commands(lines: list[str], file_path: pathlib.Path, state: ExecutionState):
    message_sequence: list[Message] = parse_messages(lines, file_path)
    interpret_commands(message_sequence, state)
    # NOTE: ^^^ the possible side effects of interpreting commands are:
    # - changes to the configuration tree
    # - mutation of state or plugin internals including loading plugins
    # - generation of command/action results, which are stored in the command.result field
    # this step does not modify the message sequence
    state.message_sequence += message_sequence

def load_config_file(config_path: pathlib.Path, state: ExecutionState) -> bool:
    """load the config file at `config_path` into `state`, if it exists.
        return `True` if the config file exists as a file, whether or not it
        loads without error.
    """
    if config_path.is_file():
        state.log.detail("loading-config", "loading configuration file", config_path)
        try:
            config_file_lines = config_path.read_text(encoding="utf-8").splitlines(keepends=True)
            parse_messages_and_interpret_commands(config_file_lines, config_path, state)
        except Exception as e:
            state.log.error("config-file-exception", f"exception while reading configuration file: {repr(e)}", config_path)
            state.log.logger.debug(e, exc_info=True)
        return True
    return False

def default_load_config_files(state: ExecutionState):
    """default configuration loading algorithm:
        - ~/.config/prapti/config.md
        - .prapticonfig.md in containing directories up to when %config_root = True
        - fallback to fallback_config_file_data if no config files found (just so that we work out of the box)
    """
    found_config_file = False

    # user config file i.e. ~/.prapti/config.md
    found_config_file = load_config_file(pathlib.Path.home() / '.prapti' / 'config.md', state)

    # in-tree `.prapticonfig.md` files:
    # (.editorconfig algorithm) starting from the directory containing the input markdown file,
    # load `.prapticonfig.md`. Iterate up the tree until a config file sets config_root = True
    state.root_config.config_root = False
    for parent in state.input_file_path.resolve().parents:
        found_config_file = load_config_file(parent / ".prapticonfig.md", state)
        if found_config_file and state.root_config.config_root:
            break # stop once we hit a config file with `%config_root = True`

    # if no config file is present, use fallback config
    if not found_config_file:
        state.log.detail("loading-fallback-config", "loading fallback configuration", state.input_file_path)
        parse_messages_and_interpret_commands(fallback_config_file_data.splitlines(keepends=True), pathlib.Path("<fallback-config>"), state)

def find_final_prompt_message(messages: list[Message]) -> Message|None:
    """a prompt message is a message that will form part of the prompt. it is not hidden or disabled"""
    try:
        return next(msg for msg in reversed(messages) if msg.is_enabled() and msg.role in ("system", "user", "assistant"))
    except StopIteration: # next() found no viable final message
        return None

def find_final_user_message(messages: list[Message]) -> Message|None:
    try:
        return next(msg for msg in reversed(messages) if msg.role == "user")
    except StopIteration: # next() found no viable final message
        return None

def write_message(file: TextIO, m: Message):
    role_and_name = (m.role + "/" + m.name) if m.name else m.role
    file.write(f"\n### {'' if m.is_enabled() else '//'}@{role_and_name}:\n")
    content = ''.join(m.content).strip() # FIXME assumed flattened content
    if content:
        file.write(f"\n{content}\n")
    else:
        file.write("\n")

def write_messages(file: TextIO, messages: list[Message]):
    for m in messages:
        write_message(file, m)

def main(argv: Sequence[str] | None = None) -> int:
    global argument_parser
    if not argument_parser:
        argument_parser = make_argument_parser()

    command_line_args = argument_parser.parse_args(args=argv) # parse command line args, uses sys.argv if None is passed

    # construct execution state
    state = ExecutionState(log=create_diagnostics_logger(), input_file_path=pathlib.Path(command_line_args.filename))
    core_state = CoreExecutionState()
    state._core_state = core_state
    core_state.actions.merge(builtin_actions)
    state.root_config.dry_run = command_line_args.dry_run
    state.root_config.strict = command_line_args.strict

    # load config files
    if not command_line_args.no_default_config:
        default_load_config_files(state)

    for config_path in map(pathlib.Path, command_line_args.config_file):
        load_config_file(config_path, state)

    # process input file, generate response
    with open(state.input_file_path, "rt+", encoding="utf-8") as file:
        state.log.detail("loading-input", "loading input file", state.input_file_path)
        lines = file.readlines()
        # early-out if the input file is effectively empty
        if not lines or all(not line.strip() for line in lines): # if file is effectively empty
            state.log.info("empty-input", "here's the default template. start writing.", state.input_file_path)
            file.write(get_default_template(state.log))
            return 0

        parse_messages_and_interpret_commands(lines, state.input_file_path, state)

        emitted_messages = flatten_message_content(state.message_sequence)

        if len(lines) > 0 and not lines[-1].endswith("\n"):
            file.write("\n") # ensure file ends in newline before appending anything

        final_user_message = find_final_user_message(state.message_sequence)
        user_name = final_user_message.name if final_user_message else None
        user_response_prompt_message = Message(role="user", name=user_name, content=[]) # i.e. ### user/name:

        # early-out with messages generated by commands
        if emitted_messages:
            flatten_message_content(emitted_messages)
            write_messages(file, emitted_messages)
            write_message(file, user_response_prompt_message)
            return 0

        # NOTE: check for empty prompt *after* evaluating commands and flattening messages that could extend the message text
        final_prompt_message = find_final_prompt_message(state.message_sequence)
        if not final_prompt_message:
            # early-out if no viable prompt message supplied
            state.log.error("absent-prompt", "no non-hidden non-disabled messages found. write something.", state.input_file_path)
            write_message(file, user_response_prompt_message)
            return 0

        # early-out if there is a final prompt, but it does not contain any text
        # (i.e. assume that the user triggered execution before typing their question)
        if final_prompt_message.content_is_empty():
            state.log.error("empty-final-prompt", "final prompt is empty. write something.", final_prompt_message.source_loc)
            return 0

        # main response generation loop
        responses_written = False
        while True: # do-while not done loop
            done = True

            responder_name, responder_context = lookup_active_responder(state)
            if not responder_context:
                state.log.critical("active-responder-not-found", f"couldn't generate a response, sorry. the active responder '{responder_name}' was not found.", state.input_file_path)
                return 1
            state.selected_responder_context = responder_context

            core_state.hooks_distributor.on_before_generate_responses()
            if bool(responses := responder_context.responder.generate_responses(state.message_sequence, responder_context)):
                state.responses = responses
                core_state.hooks_distributor.on_after_generate_responses()
                write_messages(file, state.responses)
                file.flush()
                responses_written = True

                # followup: feed back responses to input, allow hooks to continue the conversation
                state.responses = []
                # we haven't parsed commands out, but we want to give hooks an opportunity to run:
                interpret_commands(responses, state)
                flatten_message_content(responses)
                state.message_sequence += responses

                # REVIEW: do we allow writing these messages? I don't think so, these are
                # synthetic, as with other messages inserted by commands.
                continue_: bool
                message_sequence: list[Message]|None
                continue_, message_sequence = core_state.hooks_distributor.on_followup()
                if message_sequence:
                    interpret_commands(message_sequence, state)
                    flatten_message_content(message_sequence)
                    state.message_sequence += message_sequence
                if continue_:
                    done = False
            if done:
                break

        if responses_written:
            write_message(file, user_response_prompt_message)
            file.flush()
            file.close() # ensure flush and close prior to calling on_response_completed
            core_state.hooks_distributor.on_response_completed()
        else:
            state.log.error("no-response", "no response generated, sorry.", state.input_file_path)

    return 0 # success
