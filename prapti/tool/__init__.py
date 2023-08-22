"""
    Prapti command line tool for generating markdown responses
"""
import argparse
import pathlib
from typing import Sequence, TextIO
from dataclasses import dataclass

from ..__init__ import __version__
from ..core.logger import create_diagnostics_logger, log_levels
from ..core._core_execution_state import CoreExecutionState
from ..core.execution_state import ExecutionState
from ..core.chat_markdown_parser import parse_messages
from ..core.command_interpreter import interpret_commands
from ..core.builtins import builtin_actions, lookup_active_responder
from ..core.command_message import flatten_message_content, Message
from ..core.load_configuration import load_config_file, default_load_config_files
from .start_template import get_start_template

# command line args ----------------------------------------------------------

argument_parser = None

def make_argument_parser() -> argparse.ArgumentParser:
    # create and initialize an ArgumentParser
    result = argparse.ArgumentParser(prog="prapti", description="Prapti markdown conversations")
    result.add_argument('--version', action='version', version=f"%(prog)s {__version__}")
    result.add_argument("--dry-run", help="prepare the API request then bail", action="store_true")
    result.add_argument("--strict", help="fail if errors are encountered, do not attempt error recovery", action="store_true")
    result.add_argument("--no-default-config", help="disable default config file search", action="store_true")
    result.add_argument("--config-file", help="specify additional config file(s)", required=False, default=[], action="append")

    log_level_choices = [level.lower() for level in log_levels]
    result.add_argument("--log-level", help="specify the minimum level of log messages to be printed", choices=log_level_choices, required=False, default="info")

    # Positional argument for the filename
    result.add_argument("filename", help="the current markdown conversation file")
    return result

# message sequence helpers ---------------------------------------------------

def find_final_prompt_message(messages: list[Message]) -> Message|None:
    """a prompt message is a message that will form part of the prompt. it is not hidden or disabled"""
    try:
        return next(msg for msg in reversed(messages) if msg.is_enabled and msg.role in ("system", "user", "assistant", "prompt"))
    except StopIteration: # next() found no viable final message
        return None

def find_final_user_message(messages: list[Message]) -> Message|None:
    try:
        return next(msg for msg in reversed(messages) if msg.role == "user")
    except StopIteration: # next() found no viable final message
        return None

# whitespace-aware output file append ----------------------------------------

# A file is segmented into "lines" as follows:
# - each segment of the file text that ends with '\n' constitutes a line
#   - if the final character of the file text is '\n', that '\n' terminates the "final line"
#   - if the final character of the file text is not '\n',
#     the sequence of characters following the final '\n' constitute the final line
# In this way, the final line is either terminated by '\n' or it is constituted
# by *one or more* characters not terminated by '\n'. It is not possible to have an empty
# final line that is not terminated by '\n'
#
# A line is said to be "blank" if:
#   - it is empty, that is, it comprises of zero characters followed by '\n', or
#   - it comprises only of whitespace, irrespective of whether it is followed by '\n'

@dataclass
class TrailingLinesAnalysis:
    has_no_lines: bool
    final_line_has_newline: bool # the final line is terminated with a newline
    trailing_blank_line_count: int

def analyze_trailing_lines(lines: list[str]) -> TrailingLinesAnalysis:
    if not lines:
        has_no_lines = True
        final_line_has_newline = False
        trailing_blank_line_count = 0
    else:
        has_no_lines = False
        final_line_has_newline = lines[-1].endswith("\n")
        trailing_blank_line_count = 0
        for line in reversed(lines):
            if line.strip():
                break
            trailing_blank_line_count += 1
    return TrailingLinesAnalysis(
        has_no_lines=has_no_lines,
        final_line_has_newline=final_line_has_newline,
        trailing_blank_line_count=trailing_blank_line_count)

class OutputFile:
    def __init__(self, file: TextIO, lines_analysis: TrailingLinesAnalysis):
        self.file: TextIO = file
        self.lines_analysis: TrailingLinesAnalysis = lines_analysis

    def write_message(self, m: Message):
        if m.role == "completion": # raw completion. retain all data without formatting/inserting extra newlines
            if m.content:
                assert len(m.content) == 1 and isinstance(m.content[0], str), "prapti.main: expected flattened message content"
                content = "".join(m.content)
            else:
                content = ""

            if content:
                self.file.write(content)
                self.lines_analysis = analyze_trailing_lines(content.splitlines(keepends=True))
            else:
                # no content. don't output anything. trailing lines analysis remains unaltered
                pass
        else:
            # append newlines before appending message heading:
            # the goal is to insert as few newlines as possible while satisfying:
            # 1. the message heading appears at the start of a line
            # 2. the heading is preceeded by a blank line, or the start of file

            if self.lines_analysis.has_no_lines:
                pass # it's ok to insert a heading on the first line of an empty file
            else:
                add_newline_count = 0

                # by definition (see above), a final line with no newline contains content,
                # and since we want our heading to start at the start of a line, we cannot
                # append our heading to the current final line, so append a newline.
                if not self.lines_analysis.final_line_has_newline:
                    add_newline_count += 1

                # we want a blank line between the previous message text and our new message heading.
                # ideally just one blank line, but since we are operating append-only we'll accept
                # multiple existing blank lines, but in that case don't want to add any additional newlines
                add_newline_count += max(0, 1 - self.lines_analysis.trailing_blank_line_count)

                if add_newline_count > 0:
                    self.file.write("\n" * add_newline_count)

            role_and_name = (m.role + "/" + m.name) if m.name else m.role
            self.file.write(f"### {'' if m.is_enabled else '//'}@{role_and_name}:\n")

            if m.content:
                # strip whitespace from start and end of message and apply our own formatting
                assert len(m.content) == 1 and isinstance(m.content[0], str), "prapti.main: expected flattened message content"
                content = "".join(m.content).strip()
            else:
                content = ""

            if content:
                self.file.write(f"\n{content}\n")
                self.lines_analysis = TrailingLinesAnalysis(
                    has_no_lines = False,
                    final_line_has_newline = True,
                    trailing_blank_line_count = 0)
            else:
                self.file.write("\n") # one blank line between the message heading and the content, which in this case is empty
                self.lines_analysis = TrailingLinesAnalysis(
                    has_no_lines = False,
                    final_line_has_newline = True,
                    trailing_blank_line_count = 1)

    def write_messages(self, messages: list[Message]):
        for m in messages:
            self.write_message(m)

    def flush(self):
        self.file.flush()

    def close(self):
        self.file.close()

# ----------------------------------------------------------------------------

def main(argv: Sequence[str] | None = None, test_exfil: dict|None = None) -> int:
    global argument_parser
    if not argument_parser:
        argument_parser = make_argument_parser()

    command_line_args = argument_parser.parse_args(args=argv) # parse command line args, uses sys.argv if None is passed

    log_level = log_levels.get(command_line_args.log_level.upper(), None)
    if not log_level:
        print(f"error: '{command_line_args.log_level}' is not a valid log level")
        return 1

    # construct execution state
    state = ExecutionState(log=create_diagnostics_logger(initial_level=log_level), input_file_path=pathlib.Path(command_line_args.filename))
    core_state = CoreExecutionState()
    state.private_core_state = core_state
    core_state.actions.merge(builtin_actions)
    state.root_config.prapti.dry_run = command_line_args.dry_run
    state.root_config.prapti.strict = command_line_args.strict
    if test_exfil is not None:
        state.test_exfil = test_exfil
    state.test_exfil["state"] = state

    # load config files
    if not command_line_args.no_default_config:
        default_load_config_files(state)

    for config_path in map(pathlib.Path, command_line_args.config_file):
        load_config_file(config_path, state)

    # process input file, generate response
    with open(state.input_file_path, "rt+", encoding="utf-8") as file:
        state.log.info("loading-input", "loading input file", state.input_file_path)
        lines = file.readlines()
        # early-out if the input file is effectively empty
        if not lines or all(not line.strip() for line in lines): # if file is effectively empty
            state.log.info("empty-input", "here's the start template. start writing.", state.input_file_path)
            file.write(get_start_template(state))
            return 0

        input_messages: list[Message] = parse_messages(lines, state.input_file_path)
        interpret_commands(input_messages, state, is_final_sequence=True)
        state.message_sequence += input_messages

        emitted_messages = flatten_message_content(state.message_sequence)

        output_file = OutputFile(file=file, lines_analysis=analyze_trailing_lines(lines))

        final_user_message = find_final_user_message(state.message_sequence)
        user_name = final_user_message.name if final_user_message else None
        user_response_prompt_message = Message(role="user", name=user_name, content=[]) # i.e. ### @user/name:

        # early-out with messages generated by commands
        if emitted_messages:
            flatten_message_content(emitted_messages)
            output_file.write_messages(emitted_messages)
            output_file.write_message(user_response_prompt_message)
            return 0

        # NOTE: check for empty prompt *after* evaluating commands and flattening messages that could extend the message text
        final_prompt_message = find_final_prompt_message(state.message_sequence)
        if not final_prompt_message:
            # early-out if no viable prompt message supplied
            state.log.error("absent-prompt", "no non-hidden non-disabled messages found. write something.", state.input_file_path)
            output_file.write_message(user_response_prompt_message)
            return 0

        # early-out if there is a final prompt, but it does not contain any text
        # (i.e. assume that the user triggered execution before typing their question)
        if final_prompt_message.content_is_empty():
            state.log.error("empty-final-prompt", "final prompt is empty. write something.", final_prompt_message.source_loc)
            return 0

        state.log.info("generating-responses", "generating response(s). please wait...", state.input_file_path)

        # generate responses
        responder_name, responder_context = lookup_active_responder(state)
        if not responder_context:
            state.log.critical("active-responder-not-found", f"couldn't generate a response, sorry. the active responder '{responder_name}' was not found.", state.input_file_path)
            return 1
        if bool(responses := responder_context.responder.generate_responses(state.message_sequence, responder_context)):
            state.responses = responses
            output_file.write_messages(state.responses)

            if state.responses[-1].role not in ("completion", "prompt"):
                # only prompt for next ### @user: input if we're in a user/assistant/user chat mode
                output_file.write_message(user_response_prompt_message)

            output_file.flush()
            output_file.close() # ensure flush and close prior to calling on_response_completed
            core_state.hooks_distributor.on_response_completed()

            state.log.info("generating-responses-done", "done.", state.input_file_path)
        else:
            state.log.error("no-response", "no response generated, sorry.", state.input_file_path)

    if state.log.critical_count() == 0 and state.log.error_count() == 0:
        return 0 # success
    else:
        return 1 # failure
