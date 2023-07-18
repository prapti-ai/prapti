"""
    Logging support, specialised to compiler-style diagnostic messages.

    Guidelines for use of prapti logging methods:

    The advice for choosing logging levels given in the Python documentation applies:
    https://docs.python.org/3/howto/logging.html

    With more nuance for prapti: you should think of the logged diagnostics as equivalent
    to compiler diagnostics or linter diagnostics. When targetted at source code locations,
    `fatal`, `error`, `warning` and `hint` messages may also appear as linter output
    (e.g. from the prapti language server).

    fatal (critical):
        Panic conditions. Use only when the entire run must be unconditionally halted.
        Exceptions that propagate to top level are always treated as fatal.
        Anything that is an error, but for which there is no reasonable local recovery or
        capability to continue should be implemented as a fatal log message followed by
        throwing an exception.

    error:
        Conditions that, from the user's perspective, violate the documented contract
        for successful behavior. Whether a condition can be locally or globally ignored or worked-around
        has no bearing on its status as an "error". Errors include unrecoverable "faults" detected in
        accessing external apis and services, and issues with erroneous user input.
        Errors (and warnings) should not be reported for transient conditions inside retry loops,
        unless the whole loop fails.

    warning:
        Conditions that are not considered errors, but that the user could benefit from being
        notified about. For example, behavior that violates a reasonable user's expectations.
        Warnings may arise when Postel's Law is applied to user input. The resulting behavior might be
        well-documented but degenerate from a "strict processing" perspective.

    hint:
        Suggestions for improvement (as in a linter). Added as a non-standard level to support
        lint-type messages, especially when run as a language server.

    info:
        Key happy-path information. Brief, targeted actionable instructions or information
        that is immediately useful to the user. Notifications. Status information.

    detail:
        Potentially verbose description of normal operation. User-oriented detailed reporting
        on processing step, progress and actions performed. "Detail" is for the benefit of the user.
        Useful for understanding what prapti is doing, what configuration it is performing,
        what commands it is running. The "detail" level should focus on narrating processes,
        events and actions. Detail-level logging should not include "checkpoint dumps" of
        internal state or other debug-type output that only a developer with access to the
        source code could make sense of. Added as a non-standard level in order to separate
        details from key information presented at the "info" level.

    The above six levels are part of the standard "UI" of prapti. They are all user-oriented.
    Care should be taken to make messages clear, brief, and succinct. Each emitted message should
    be useful. There should be no repetition or redundancy. With only the above levels visible,
    the user should know when they have done something wrong, and should be able to confidently
    assume that everything is behaving as expected.

    debug:
        Developer oriented. Events used for debugging. Dumps of internal state. Information related to
        internal details that are not part of the documented user-facing conceptual model of the software.
        It is preferable for debug output to be clear and "usable" like all other logged output. But it is
        ok if debug output is confusing to non-developers.
"""
import logging
from .source_location import SourceLocation

# Minimal addition of DETAIL and HINT logging levels
# without monkey patching anything. See this SO question for extensive discussion
# of more comprehensive/invasive approaches:
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
        print(f"prapti: warning: log level {name} was not configured in expected range")
    return existing_level

DETAIL: int = add_logging_level(15, "DETAIL", logging.DEBUG, logging.INFO) # midway between DEBUG and INFO
HINT: int = add_logging_level(25, "HINT", logging.INFO, logging.WARNING) # midway between INFO and WARNING

class DiagnosticsLogger:
    """Ergonomic facade for logging diagnostic messages.
    Require message ids and support optional SourceLocation arguments.
    Count message events to support staged halting on error conditions.
    """
    def __init__(self, logger: logging.Logger):
        self.logger = logger

        self.message_counts = {}
        for level in [logging.CRITICAL, logging.ERROR, logging.WARNING, DETAIL, logging.INFO, HINT, logging.DEBUG]:
            self.message_counts[level] = 0

    def fatal_count(self):
        return self.message_counts[logging.CRITICAL]

    def error_count(self):
        return self.message_counts[logging.ERROR]

    def warning_count(self):
        return self.message_counts[logging.WARNING]

    def _decode_extras(self, extras_dict, extras):
        """take extras and interpret them into the following fields in extras_dict:
            - source_file_path
            - line # 1-based
            - column # 1-based
        """
        file_path, line, column = None, None, None

        for obj in extras:
            if isinstance(obj, SourceLocation):
                # for now expect only one source location per log message,
                # use the last one found
                file_path, line, column = obj.file_path, obj.line, obj.column

        if file_path is not None:
            extras_dict['source_file_path'] = file_path
        if line is not None:
            extras_dict['source_line'] = line
        if column is not None:
            extras_dict['source_column'] = column

    def _make_extra(self, message_id, extras):
        extras_dict = {'message_id': message_id}
        self._decode_extras(extras_dict, extras)
        return extras_dict

    def _log(self, level, message_id, message, extras):
        self.logger.log(level, message, extra=self._make_extra(message_id, extras))
        self.message_counts[level] += 1

    def fatal(self, message_id, message, *extras):
        self._log(logging.CRITICAL, message_id, message, extras)

    def error(self, message_id, message, *extras):
        self._log(logging.ERROR, message_id, message, extras)

    def warning(self, message_id, message, *extras):
        self._log(logging.WARNING, message_id, message, extras)

    def hint(self, message_id, message, *extras):
        self._log(HINT, message_id, message, extras)

    def info(self, message_id, message, *extras):
        self._log(logging.INFO, message_id, message, extras)

    def detail(self, message_id, message, *extras):
        self._log(DETAIL, message_id, message, extras)

    def debug(self, message_id, message, *extras):
        self._log(logging.DEBUG, message_id, message, extras)

class DiagnosticRecordFormatter(logging.Formatter):
    """Format log messages in a compiler-like format for console display."""
    def format(self, record) -> str:
        # filename:line:col
        source_file: str = str(record.__dict__.get('source_file_path', '<source>'))
        source_line = record.__dict__.get('source_line', None)
        source_column = record.__dict__.get('source_column', None)
        source_location_str = ":".join(str(s) for s in (source_file, source_line, source_column) if s)

        levelname = record.levelname.lower()
        if levelname == "critical":
            levelname = "fatal"

        message_id = record.__dict__.get('message_id', None)
        message_id = f"[{message_id}]" if message_id else None

        message = record.__dict__['msg'] % record.__dict__['args']

        # filename:ln:col: level: [message_id]: ... message goes here ...
        return ": ".join(s for s in (source_location_str, levelname, message_id, message) if s)

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
