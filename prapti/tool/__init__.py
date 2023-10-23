"""
    Prapti command line tool for generating markdown responses
"""
import argparse
import pathlib
import sys
from typing import Sequence, TextIO, AsyncGenerator
from dataclasses import dataclass, field
import asyncio
from enum import Enum

from cancel_token import CancellationToken

from ..__init__ import __version__
from ..core.logger import create_root_diagnostics_logger, log_levels, DiagnosticsLogger
from ..core._core_execution_state import CoreExecutionState, get_private_core_state
from ..core.execution_state import ExecutionState
from ..core.chat_markdown_parser import parse_messages
from ..core.command_interpreter import interpret_commands
from ..core.builtins import builtin_actions, lookup_active_responder
from ..core.command_message import flatten_message_content, Message
from ..core.load_configuration import load_config_file, default_load_config_files
from .start_template import get_start_template

class ExitStatus(Enum):
    SUCCESS = 0
    FAILURE = 1

# command line args ----------------------------------------------------------

def make_argument_parser() -> argparse.ArgumentParser:
    # create and initialize an ArgumentParser
    result = argparse.ArgumentParser(prog="prapti", description="Prapti markdown conversations")
    result.add_argument('--version', action='version', version=f"%(prog)s {__version__}")
    result.add_argument("--dry-run", help="prepare the LLM API request then halt without calling the API", action="store_true")
    result.add_argument("--halt-on-error", help="halt if errors are encountered, do not attempt error recovery", action="store_true")
    result.add_argument("--no-default-config", help="disable default config file search", action="store_true")
    result.add_argument("--config-file", help="specify additional config file(s)", required=False, default=[], action="append")
    result.add_argument("--show-output", help="stream LLM output to standard output (in addition to updating file)", action="store_true")

    log_level_choices = [level.lower() for level in log_levels]
    result.add_argument("--log-level", help="specify the minimum level of log messages to be printed", choices=log_level_choices, required=False, default="info")

    # Positional argument for the filename
    result.add_argument("filename", help="the current markdown conversation file")
    return result

argument_parser = make_argument_parser()

# message sequence helpers ---------------------------------------------------

def find_final_prompt_message(messages: list[Message]) -> Message|None:
    """Returns the last message that forms part of the prompt and is not
    hidden or disabled, or None if no such message exists."""
    try:
        return next(msg for msg in reversed(messages) if msg.is_enabled and msg.role in ("system", "user", "assistant", "prompt"))
    except StopIteration: # next() found no viable final message
        return None

def find_final_user_message(messages: list[Message]) -> Message|None:
    """Returns the last message with the role 'user' (whether or not disabled),
    or None if no such message exists."""
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
    """Analyzes the trailing lines of a file to determine whether the file ends with a newline
    and the number of trailing blank lines."""
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

class OutputFormatter:
    """Formats messages for text output, taking into account the current trailing whitespace
    at the end of the file."""

    def __init__(self, lines_analysis: TrailingLinesAnalysis):
        assert lines_analysis is not None
        self.lines_analysis: TrailingLinesAnalysis = lines_analysis

    async def format_message(self, m: Message, log: DiagnosticsLogger) -> AsyncGenerator[str, None]:
        if m.role == "completion": # raw completion. retain all data without formatting/inserting extra newlines
            if m.content:
                assert len(m.content) == 1 and isinstance(m.content[0], str), "prapti.main: expected flattened message content"
                content = "".join(m.content)
            else:
                content = ""

            content_yielded = False

            if content:
                yield content
                content_yielded = True

            if m.async_content is not None:
                try:
                    async for text in m.async_content:
                        if not text: # ignore empty spans
                            continue
                        m.content.append(text)
                        yield text
                        content_yielded = True
                except Exception as ex:
                    log.error("async-content-exception", f"response ended unexpectedly. responder emitted exception while streaming asynchronous message content: {repr(ex)}")
                    log.debug_exception(ex)

            if m.content:
                m.content = ["".join(m.content)] # flatten sync content after appending async content

            if content_yielded:
                self.lines_analysis = analyze_trailing_lines(m.content[0].splitlines(keepends=True))
            else:
                # no content yielded. trailing lines analysis remains unaltered
                pass
        else:
            # append newlines before appending message heading:
            # the goal is to insert as few newlines as possible while satisfying:
            # 1. the message heading appears at the start of a line
            # 2. the heading is preceeded by a blank line, or the start of file

            add_newline_count = 0
            if self.lines_analysis.has_no_lines:
                pass
                # it's ok to insert a heading on the first line of an empty file
            else:
                # by definition (see above), a final line with no newline contains content,
                # and since we want our heading to start at the start of a line, we cannot
                # append our heading to the current final line, so append a newline.
                if not self.lines_analysis.final_line_has_newline:
                    add_newline_count += 1

                # we want a blank line between the previous message text and our new message heading.
                # ideally just one blank line, but since we are operating append-only we'll accept
                # multiple existing blank lines, but in that case don't want to add any additional newlines
                add_newline_count += max(0, 1 - self.lines_analysis.trailing_blank_line_count)

            newlines = "\n" * add_newline_count
            role_and_name = (m.role + "/" + m.name) if m.name else m.role
            yield f"{newlines}### {'' if m.is_enabled else '//'}@{role_and_name}:\n"

            # apply our own formatting to message content. in effect, the content is stripped
            # of leading and trailing whitespace and then a single leading and trailing newline
            # is added; as if `yield f"\n{content.strip()}\n"` were executed, but taking
            # async content into account. if the message has no content, a single newline is output.

            # in addition, async content is appended to message synchronous content.
            # (without any of the above whitespace handling).

            content_yielded = False
            trailing_ws = "" # hold back trailing whitespace until we know there is more content

            # output synchronous content
            if m.content:
                assert len(m.content) == 1 and isinstance(m.content[0], str), "prapti.main: expected flattened message content"
                content = "".join(m.content)
                lcontent = content.lstrip()
                if lcontent:
                    lrcontent = lcontent.rstrip()
                    yield "\n" + lrcontent
                    content_yielded = True
                    trailing_ws = lcontent[len(lrcontent):]

            # process and output asynchronous content
            if m.async_content is not None:
                try:
                    async for text in m.async_content:
                        if not text: # ignore empty spans
                            continue
                        m.content.append(text)

                        if content_yielded:
                            # retain leading whitespace within content
                            rtext = text.rstrip()
                            yield trailing_ws + rtext
                            trailing_ws = text[len(rtext):]
                        else:
                            # strip leading whitespace at start of content
                            ltext = text.lstrip()
                            if ltext:
                                lrtext = ltext.rstrip()
                                yield "\n" + lrtext # no content yielded yet, leading newline
                                content_yielded = True
                                trailing_ws = ltext[len(lrtext):]
                except Exception as ex:
                    log.error("async-content-exception", f"response ended unexpectedly. responder emitted exception while streaming asynchronous message content: {repr(ex)}")
                    log.debug_exception(ex)

                if m.content:
                    m.content = ["".join(m.content)] # flatten sync content after appending async content

            if content_yielded:
                yield "\n" # single newline at end of content
                self.lines_analysis = TrailingLinesAnalysis(
                    has_no_lines = False,
                    final_line_has_newline = True,
                    trailing_blank_line_count = 0)
            else:
                yield "\n" # one blank line between the message heading and the content, which in this case is empty
                self.lines_analysis = TrailingLinesAnalysis(
                    has_no_lines = False,
                    final_line_has_newline = True,
                    trailing_blank_line_count = 1)

# ----------------------------------------------------------------------------

@dataclass
class RunState:
    completed: bool
    result_code: int|None = None
    state: ExecutionState|None = None
    file: TextIO|None = None
    lines_analysis: TrailingLinesAnalysis|None = None
    early_output: list[str|Message] = field(default_factory=list)
    user_response_prompt_message: Message|None = None
    show_output: bool = False

def run_phase_1(argv: Sequence[str] | None = None, test_exfil: dict|None = None, input_lines: list[str]|None = None) -> RunState:
    """synchronous execution phase: parse input, run commands prepare prompt."""
    if not argv:
        argv = sys.argv # use sys.argv if None is passed
    state_argv = list(argv) # capture a copy
    args = argv[1:] # parse_args doesn't want the command name
    command_line_args = argument_parser.parse_args(args=args)

    log_level = log_levels.get(command_line_args.log_level.upper(), None)
    if not log_level:
        print(f"error: '{command_line_args.log_level}' is not a valid log level", file=sys.stderr, flush=True)
        return RunState(completed=True, result_code=ExitStatus.FAILURE.value)

    # construct execution state
    state = ExecutionState(prapti_version=__version__, argv=state_argv, log=create_root_diagnostics_logger(initial_level=log_level), input_file_path=pathlib.Path(command_line_args.filename))
    core_state = CoreExecutionState()
    state.private_core_state = core_state
    core_state.actions.merge(builtin_actions)
    state.root_config.prapti.dry_run = command_line_args.dry_run
    state.root_config.prapti.halt_on_error = command_line_args.halt_on_error
    if test_exfil is not None:
        state.test_exfil = test_exfil
    state.test_exfil["state"] = state

    # load config files
    state.log.info("loading-config", "loading configuration files...", state.input_file_path)

    if not command_line_args.no_default_config:
        default_load_config_files(state)

    for config_path in map(pathlib.Path, command_line_args.config_file):
        load_config_file(config_path, state)

    # process input file
    state.log.info("processing-input", "processing input...", state.input_file_path)

    file = None
    if input_lines is None:
        state.log.info("loading-input", "loading input file", state.input_file_path)

        try:
            file = open(state.input_file_path, "rt+", encoding="utf-8")
        except OSError as e:
            state.log.info("error-opening-input", f"could not open input file '{state.input_file_path}': {e}")
            return RunState(completed=True, state=state, result_code=ExitStatus.FAILURE.value)

        input_lines = file.readlines()

    lines_analysis=analyze_trailing_lines(input_lines)

    # early-out if the input file is effectively empty
    if not input_lines or all(not line.strip() for line in input_lines): # if file is effectively empty
        state.log.info("empty-input", "here's the start template. start writing.", state.input_file_path)
        return RunState(completed=True, state=state, result_code=ExitStatus.SUCCESS.value, file=file, lines_analysis=lines_analysis, early_output=[get_start_template(state)], show_output=command_line_args.show_output)

    input_messages: list[Message] = parse_messages(input_lines, state.input_file_path)
    interpret_commands(input_messages, state, is_final_sequence=True)
    state.message_sequence += input_messages

    emitted_messages = flatten_message_content(state.message_sequence)

    final_user_message = find_final_user_message(state.message_sequence)
    user_name = final_user_message.name if final_user_message else None
    user_response_prompt_message = Message(role="user", name=user_name, content=[]) # i.e. ### @user/name:

    # early-out with messages generated by commands
    if emitted_messages:
        flatten_message_content(emitted_messages)
        state.log.info("processing-input-done-early-output", "processing input done. output generated by command(s).", state.input_file_path)
        return RunState(completed=True, state=state, result_code=ExitStatus.SUCCESS.value, file=file, lines_analysis=lines_analysis, early_output=emitted_messages + [user_response_prompt_message])

    # NOTE: check for empty prompt *after* evaluating commands and flattening messages that could extend the message text
    final_prompt_message = find_final_prompt_message(state.message_sequence)
    if not final_prompt_message:
        # early-out if no viable prompt message supplied
        state.log.info("absent-prompt", "no non-hidden non-disabled messages found. write something.", state.input_file_path)
        return RunState(completed=True, state=state, result_code=ExitStatus.SUCCESS.value, file=file, lines_analysis=lines_analysis, early_output=[user_response_prompt_message], show_output=command_line_args.show_output)

    # early-out if there is a final prompt, but it does not contain any text
    # (i.e. assume that the user triggered execution before typing their question)
    if final_prompt_message.content_is_empty():
        state.log.info("empty-final-prompt", "final prompt is empty. write something.", final_prompt_message.source_loc)
        return RunState(completed=True, state=state, result_code=ExitStatus.SUCCESS.value)

    if state.root_config.prapti.halt_on_error and (state.log.critical_count() > 0 or state.log.error_count() > 0):
        state.log.error("error-halting", "halting due to errors.", state.input_file_path)
        return RunState(completed=True, state=state, result_code=ExitStatus.FAILURE.value)

    state.log.info("processing-input-done", "processing input done.", state.input_file_path)
    return RunState(completed=False, state=state, file=file, lines_analysis=lines_analysis, user_response_prompt_message=user_response_prompt_message, show_output=command_line_args.show_output)

async def format_early_output(items: list[Message|str], output_formatter: OutputFormatter, log: DiagnosticsLogger) -> str:
    result = []
    for item in items:
        match(item):
            case str():
                result.append(item)
            case Message():
                async for text in output_formatter.format_message(item, log):
                    result.append(text)
    return "".join(result)

@dataclass
class EndOfOutputSentinel:
    pass

@dataclass
class CompletionSentinel:
    result_code: int

async def run_phase_2(run_state: RunState, cancellation_token: CancellationToken) -> AsyncGenerator[str|EndOfOutputSentinel|CompletionSentinel, None]:
    """asynchrononous execution phase: generate output, emit result code"""

    if run_state.state is None:
        # if no execution state was created there is no logger, so perform a best-effort cleanup
        assert run_state.completed
        assert run_state.result_code is not None
        assert not run_state.early_output
        yield EndOfOutputSentinel()
        yield CompletionSentinel(result_code=run_state.result_code)
        return

    assert run_state.state is not None
    state = run_state.state
    core_state = get_private_core_state(state)
    end_of_output_sentinel_yielded = False
    result_code = ExitStatus.FAILURE.value
    try:
        if run_state.early_output or not run_state.completed:
            # if there is early output, or there might be phase-2 output,
            # phase-1 should have computed a lines_analysis
            assert run_state.lines_analysis is not None

        output_formatter = None

        if run_state.early_output:
            assert run_state.state is not None
            assert run_state.lines_analysis is not None
            output_formatter = OutputFormatter(lines_analysis=run_state.lines_analysis)
            output_text = await format_early_output(run_state.early_output, output_formatter, run_state.state.log)
            yield output_text

        if run_state.completed:
            assert run_state.result_code is not None
            result_code=run_state.result_code
            return

        # end early-completion / early-output emission

        if not output_formatter:
            assert run_state.lines_analysis is not None
            output_formatter = OutputFormatter(lines_analysis=run_state.lines_analysis)

        state.log.info("generating-responses", "generating response(s). please wait...", state.input_file_path)

        core_state.hooks_distributor.on_generating_response()

        responder_name, responder_context = lookup_active_responder(state)
        if not responder_context:
            state.log.critical("active-responder-not-found", f"couldn't generate a response, sorry. the active responder '{responder_name}' was not found.", state.input_file_path)
            result_code = ExitStatus.FAILURE.value
            return

        if cancellation_token.cancelled:
            state.log.error("generate-responses-cancelled", "generating responses cancelled.", state.input_file_path)
            result_code = ExitStatus.FAILURE.value
            return

        async_responses = responder_context.responder.generate_responses(state.message_sequence, cancellation_token, responder_context)

        responses = []
        async for message in async_responses:
            responses.append(message)
            async_text = output_formatter.format_message(message, state.log)
            async for text in async_text:
                yield text
        state.responses = responses

        if responses and responses[-1].role not in ("completion", "prompt") and run_state.user_response_prompt_message:
            # only prompt for next ### @user: input if we're in a user/assistant/user chat mode
            async_text = output_formatter.format_message(run_state.user_response_prompt_message, state.log)
            async for text in async_text:
                yield text

        end_of_output_sentinel_yielded = True
        yield EndOfOutputSentinel() # trigger/ensure flush and close prior to calling on_response_completed

        if cancellation_token.cancelled:
            state.log.error("generate-responses-cancelled", "generating responses cancelled.", state.input_file_path)

        if state.responses:
            core_state.hooks_distributor.on_response_completed()

            state.log.info("generating-responses-done", "generating responses done.", state.input_file_path)
        else:
            if not cancellation_token.cancelled:
                state.log.error("no-response", "no response generated, sorry.", state.input_file_path)

        if state.log.critical_count() == 0 and state.log.error_count() == 0:
            result_code = ExitStatus.SUCCESS.value
        else:
            result_code = ExitStatus.FAILURE.value
    except Exception as ex:
        state.log.error("unhandled-exception", f"generation halted unexpectedly. an unhandled exception occurred: {repr(ex)}", state.input_file_path)
        state.log.error_exception(ex)
    finally:
        if not end_of_output_sentinel_yielded:
            yield EndOfOutputSentinel()
        yield CompletionSentinel(result_code=result_code)

async def async_main_run_phase_2(run_state: RunState) -> int:
    """run asynchronous response generation, write output to file and console, return result code"""
    has_output = False
    async_output = run_phase_2(run_state, CancellationToken())
    async for item in async_output:
        match item:
            case str():
                assert run_state.file is not None
                assert run_state.lines_analysis is not None

                text = item
                run_state.file.write(text)

                if run_state.show_output:
                    if not has_output:
                        print(">>>>>>>>\n", end="", flush=False)
                    print(text, end="", flush=True)
                    has_output = True

            case EndOfOutputSentinel():
                if run_state.file:
                    run_state.file.flush()
                    run_state.file.close() # ensure flush and close prior to calling on_response_completed

                if run_state.show_output:
                    note = "" if has_output else "(no output)"
                    print(f"{note}\n<<<<<<<<\n", end="", flush=True)

            case CompletionSentinel():
                return item.result_code
    assert False, "run_phase_2 did not yield CompletionSentinel"

def main(argv: Sequence[str] | None = None, test_exfil: dict|None = None) -> int:
    run_state = run_phase_1(argv, test_exfil)
    return asyncio.run(async_main_run_phase_2(run_state))
