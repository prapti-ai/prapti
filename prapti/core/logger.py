"""
    Logging support, specialized for compiler-style diagnostic messages.

    Logging Levels:
    - critical: Unrecoverable conditions that require the entire run to be halted.
    - error: Violations of the documented contract for successful behavior.
      Should not be reported for transient failures, such as inside retry loops.
    - warning: Non-error conditions that the user could benefit from being notified about.
    - hint: Suggestions for improvement, similar to linter messages.
    - info: Key happy-path information, notifications, and status information.
    - detail: (Potentially verbose) user-oriented detailed reporting on processing steps,
      progress, and actions performed. This is a non-standard level added to separate details
      from key information presented at the 'info' level.
    - debug: Developer-oriented logs for debugging, including dumps of internal state.

    The first six levels are user-oriented and should be clear, brief, and succinct.
    The debug level is developer-oriented and may include details not part of the user-facing
    conceptual model of the software.

    For general guidelines, refer to the Python logging documentation:
    https://docs.python.org/3/howto/logging.html
"""
from typing import Any
import logging
import pathlib
import sys
from .source_location import SourceLocation

# Add HINT and DETAIL logging levels, without monkey patching anything.
# See the following SO question for extensive discussion of more comprehensive/invasive approaches:
# https://stackoverflow.com/questions/2183233/how-to-add-a-custom-loglevel-to-pythons-logging-facility
def add_logging_level(level: int, name: str, lower_bound: int, upper_bound: int) -> int:
    existing_level = logging.getLevelName(name)
    # ^^^ getLevelName returns level numbers given string level names(!),
    # except if a level name does not exist, in which case it returns a string(!!)
    if isinstance(existing_level, str):
        existing_level = None

    if existing_level is None:
        assert level > lower_bound
        assert level < upper_bound
        logging.addLevelName(level, name)
        return level
    if existing_level > upper_bound or existing_level < lower_bound:
        print(f"prapti: warning: log level {name} was not configured in expected range", file=sys.stderr)
    return existing_level

HINT: int = add_logging_level(25, "HINT", logging.INFO, logging.WARNING) # midway between INFO and WARNING
DETAIL: int = add_logging_level(15, "DETAIL", logging.DEBUG, logging.INFO) # midway between DEBUG and INFO


class DiagnosticsLogger:
    """Ergonomic facade for logging compiler-style diagnostic messages.
    - Requires message ids for INFO and above.
    - Supports a range of source location arguments.
    - Counts message events to support staged halting on error conditions.
    """
    def __init__(self, logger: logging.Logger):
        self.logger = logger

        self.message_counts: dict[int, int] = {}
        for level in [logging.CRITICAL, logging.ERROR, logging.WARNING, DETAIL, logging.INFO, HINT, logging.DEBUG]:
            self.message_counts[level] = 0

    def critical_count(self) -> int:
        return self.message_counts[logging.CRITICAL]

    def error_count(self) -> int:
        return self.message_counts[logging.ERROR]

    def warning_count(self) -> int:
        return self.message_counts[logging.WARNING]

    def _decode_extras(self, extras_dict: dict[str, Any], extras: tuple[Any, ...], kwextras: dict[str, Any]):
        """take extras and kwextras and interpret them into the following fields in extras_dict:
            - source_file_path
            - source_line # 1-based
            - source_column # 1-based
        """
        file_path, line, column = None, None, None

        for obj in extras:
            if isinstance(obj, SourceLocation):
                # for now expect only one source location per log message,
                # use the last one found
                file_path, line, column = obj.file_path, obj.line, obj.column
            elif isinstance(obj, pathlib.Path):
                file_path = obj
            else:
                assert False, f"unrecognised type-dispatched extra log argument {repr(obj)}"

        for name, value in kwextras.items():
            if name == "line":
                line = value
            elif name == "column":
                column = value
            else:
                assert False, f"unrecognised keyword extra log argument {name} = {repr(value)}"

        if file_path is not None:
            extras_dict['source_file_path'] = file_path
        if line is not None:
            extras_dict['source_line'] = line
        if column is not None:
            extras_dict['source_column'] = column

    def _make_extra(self, message_id, extras: tuple[Any, ...], kwextras: dict[str, Any]) -> dict[str, Any]:
        extras_dict: dict[str, Any] = {'message_id': message_id}
        self._decode_extras(extras_dict, extras, kwextras)
        return extras_dict

    # log calls follow one of the basic patterns:
    #   log.error(message, ...)
    #   log.error(message_id, message, ...)
    # where ... are optional type-dispatched and keyword-dispatched extra arguments.
    # For example, Path and SourceLocation instances can be passed as type-dispatched
    # extras that associate a source location to the log message. Similarly, the line
    # and column keyword arguments can be used to specify line and column.

    def _log(self, level, msg_id_or_msg: str, msg_and_or_extras: tuple[Any, ...], kwextras: dict[str, Any]):
        # make the call behave as if the signature is
        #   error([message_id=None], message, *extras, **kwextras)
        if not msg_and_or_extras:
            message_id = None
            message = msg_id_or_msg
            extras = tuple()
        elif isinstance(msg_and_or_extras[0], str):
            message_id = msg_id_or_msg
            message = msg_and_or_extras[0]
            extras = msg_and_or_extras[1:]
        else:
            # msg_and_or_extras[0] is not a string
            message_id = None
            message = msg_id_or_msg
            extras = msg_and_or_extras

        if level >= logging.INFO:
            assert message_id is not None, "message_id is required for logging at 'info' level and above"

        self.logger.log(level, message, extra=self._make_extra(message_id, extras, kwextras))
        self.message_counts[level] += 1

    def critical(self, msg_id_or_msg: str, *msg_and_or_extras, **kwextras):
        self._log(logging.CRITICAL, msg_id_or_msg, msg_and_or_extras, kwextras)

    def error(self, msg_id_or_msg: str, *msg_and_or_extras, **kwextras):
        self._log(logging.ERROR, msg_id_or_msg, msg_and_or_extras, kwextras)

    def warning(self, msg_id_or_msg: str, *msg_and_or_extras, **kwextras):
        self._log(logging.WARNING, msg_id_or_msg, msg_and_or_extras, kwextras)

    def hint(self, msg_id_or_msg: str, *msg_and_or_extras, **kwextras):
        self._log(HINT, msg_id_or_msg, msg_and_or_extras, kwextras)

    def info(self, msg_id_or_msg: str, *msg_and_or_extras, **kwextras):
        self._log(logging.INFO, msg_id_or_msg, msg_and_or_extras, kwextras)

    def detail(self, msg_id_or_msg: str, *msg_and_or_extras, **kwextras):
        self._log(DETAIL, msg_id_or_msg, msg_and_or_extras, kwextras)

    def debug(self, msg_id_or_msg: str, *msg_and_or_extras, **kwextras):
        self._log(logging.DEBUG, msg_id_or_msg, msg_and_or_extras, kwextras)


class DiagnosticRecordFormatter(logging.Formatter):
    """Format log messages in a compiler-like format for console display."""
    def formatMessage(self, record) -> str:
        # filename:line:col
        source_file: str = record.__dict__.get('source_file_path', '')
        source_line = record.__dict__.get('source_line', None)
        source_column = record.__dict__.get('source_column', None)
        if (source_line is not None or source_column is not None) and not source_file:
            source_file = '<source>'
        source_location_str = ":".join(str(s) for s in (source_file, source_line, source_column) if s)

        levelname = record.levelname.lower()

        log_message_id = True
        if log_message_id:
            message_id = record.__dict__.get('message_id', None)
            message_id = f"[{message_id}]" if message_id else None
        else:
            message_id= None

        message = record.__dict__['message']

        # filename:ln:col: level: [message_id]: ... message goes here ...
        if message:
            return ": ".join(s for s in (source_location_str, levelname, message_id, message) if s)
        else:
            return ": ".join(s for s in (source_location_str, levelname, message_id) if s) + ":"


def create_diagnostics_logger(initial_level=logging.DEBUG) -> DiagnosticsLogger:
    logger = logging.getLogger(name='prapti')
    logger.setLevel(initial_level)
    if not logger.handlers:
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.DEBUG)
        formatter = DiagnosticRecordFormatter()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    return DiagnosticsLogger(logger=logger)
