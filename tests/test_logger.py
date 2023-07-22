from pathlib import Path
import logging

import pytest

import prapti.core.logger
from prapti.core.source_location import SourceLocation

@pytest.fixture(name="log", scope="function")
def fixture_log() -> prapti.core.logger.DiagnosticsLogger:
    return prapti.core.logger.create_diagnostics_logger()

def test_logger_check_caplog(caplog, log):
    """emit all message levels. check pytest caplog fixture behavior"""

    log.critical("id1", "message1")
    log.error("id2", "message2")
    log.warning("id3", "message3")
    log.hint("id4", "message4")
    log.info("id5", "message5")
    log.detail("id6", "message6")
    log.debug("id7", "message7")

    assert len(caplog.records) == 7
    final_record = caplog.records[-1]
    assert final_record.levelname == "DEBUG"
    assert final_record.message_id == "id7"
    assert final_record.msg == "message7"

# critical/error/warning/hint/info required message id and message
def test_logger_common_signature_0(caplog, log):
    """test the most common signatures for invoking the logger"""

    log.error("id0", "message0")

    assert len(caplog.records) == 1
    assert caplog.records[0].levelname == "ERROR"
    assert caplog.records[0].message_id == "id0"
    assert caplog.records[0].msg == "message0"
    assert caplog.records[0].__dict__.get("source_file_path") is None
    assert caplog.records[0].__dict__.get("source_line") is None
    assert caplog.records[0].__dict__.get("source_column") is None

def test_logger_common_signature_1(caplog, log):
    """test the most common signatures for invoking the logger"""

    log.warning("id1", "message1", SourceLocation(Path("fake1.md"), line=101, column=201))

    assert len(caplog.records) == 1
    assert caplog.records[0].levelname == "WARNING"
    assert caplog.records[0].message_id == "id1"
    assert caplog.records[0].msg == "message1"
    assert caplog.records[0].__dict__.get("source_file_path") == Path("fake1.md")
    assert caplog.records[0].__dict__.get("source_line") == 101
    assert caplog.records[0].__dict__.get("source_column") == 201

def test_logger_common_signature_2(caplog, log):
    """test the most common signatures for invoking the logger"""

    log.info("id2", "message2", Path("fake2.md"), line=102)

    assert len(caplog.records) == 1
    assert caplog.records[0].levelname == "INFO"
    assert caplog.records[0].message_id == "id2"
    assert caplog.records[0].msg == "message2"
    assert caplog.records[0].__dict__.get("source_file_path") == Path("fake2.md")
    assert caplog.records[0].__dict__.get("source_line") == 102
    assert caplog.records[0].__dict__.get("source_column") is None

# detail and debug support omitting message id
def test_logger_common_signature_3(caplog, log):
    """test the most common signatures for invoking the logger"""

    log.detail("message3")

    assert len(caplog.records) == 1
    assert caplog.records[0].levelname == "DETAIL"
    assert caplog.records[0].message_id is None
    assert caplog.records[0].msg == "message3"
    assert caplog.records[0].__dict__.get("source_file_path") is None
    assert caplog.records[0].__dict__.get("source_line") is None
    assert caplog.records[0].__dict__.get("source_column") is None

def test_logger_common_signature_4(caplog, log):
    """test the most common signatures for invoking the logger"""

    log.detail("message4", SourceLocation(Path("fake4.md"), line=104, column=204))

    assert len(caplog.records) == 1
    assert caplog.records[0].levelname == "DETAIL"
    assert caplog.records[0].message_id is None
    assert caplog.records[0].msg == "message4"
    assert caplog.records[0].__dict__.get("source_file_path") == Path("fake4.md")
    assert caplog.records[0].__dict__.get("source_line") == 104
    assert caplog.records[0].__dict__.get("source_column") == 204

def test_logger_common_signature_5(caplog, log):
    """test the most common signatures for invoking the logger"""

    log.debug("message5", Path("fake5.md"), line=105)

    assert len(caplog.records) == 1
    assert caplog.records[0].levelname == "DEBUG"
    assert caplog.records[0].message_id is None
    assert caplog.records[0].msg == "message5"
    assert caplog.records[0].__dict__.get("source_file_path") == Path("fake5.md")
    assert caplog.records[0].__dict__.get("source_line") == 105
    assert caplog.records[0].__dict__.get("source_column") is None

def test_logger_smoke(caplog, log):
    """test that basic logger usage emits messages as expected and that message counters appear to work"""
    formatter: prapti.core.logger.DiagnosticRecordFormatter = prapti.core.logger.DiagnosticRecordFormatter()

    fake_error_message_parameter = "foobar"
    fake_source_loc1 = SourceLocation(Path("path/to/my/file.md"), line=1, column=2)
    fake_source_loc2 = SourceLocation(Path("path/to/my/other/file.md"), line=3, column=4)

    assert all(count == 0 for level,count in log.message_counts.items())

    # log at each logging level. with/without source location, with/without message id
    log.critical("lots-of-errors", "lots too many errors. an error message.", fake_source_loc1)
    log.critical("missing-fluxwub", f"the fluxwub '{fake_error_message_parameter}' is missing")
    log.error("incorrect-fluxwub", f"the fluxwub '{fake_error_message_parameter}' is incorrect")
    log.error("bad-fluxwub", f"the fluxwub '{fake_error_message_parameter}' is bad", fake_source_loc1)
    log.warning("too-many-fluxwubs", f"the fluxwub '{fake_error_message_parameter}' exceeds fluxwub capacity", fake_source_loc2)
    log.hint("improve-dweezilwhatsit", "improve the fluxwub with dweezilwhatsit")
    # omitting message id should omit the message id tag from the formatted message
    log.info("info-1", "info message")
    log.detail("detail-1", "detail with message id")
    log.detail("detail without message id")
    log.debug("debug dump without message id")

    assert log.critical_count() == 2
    assert log.error_count() == 2
    assert log.warning_count() == 1
    # check that we've emitted a message at each level:
    assert all(count != 0 for level,count in log.message_counts.items())

    # embed .file_path expressions below because pathlib.Path will render them differently on Windows and Unix
    expect_formatted_record_tuples = [
        ("prapti", logging.CRITICAL, f"{fake_source_loc1.file_path}:1:2: critical: [lots-of-errors]: lots too many errors. an error message."),
        ("prapti", logging.CRITICAL, "critical: [missing-fluxwub]: the fluxwub 'foobar' is missing"),
        ("prapti", logging.ERROR, "error: [incorrect-fluxwub]: the fluxwub 'foobar' is incorrect"),
        ("prapti", logging.ERROR, f"{fake_source_loc1.file_path}:1:2: error: [bad-fluxwub]: the fluxwub 'foobar' is bad"),
        ("prapti", logging.WARNING, f"{fake_source_loc2.file_path}:3:4: warning: [too-many-fluxwubs]: the fluxwub 'foobar' exceeds fluxwub capacity"),
        ("prapti", prapti.core.logger.HINT, "hint: [improve-dweezilwhatsit]: improve the fluxwub with dweezilwhatsit"),
        # notice that there is no empty ``:`-delimited section for the message id:
        ("prapti", logging.INFO, "info: [info-1]: info message"),
        ("prapti", prapti.core.logger.DETAIL, "detail: [detail-1]: detail with message id"),
        ("prapti", prapti.core.logger.DETAIL, "detail: detail without message id"),
        ("prapti", logging.DEBUG, "debug: debug dump without message id"),
    ]
    # caplog captures logging records prior to formatting. In order to test our expectations
    # regarding *formatted* output, we manually format the emitted records as part of the test.
    # this serves to test both that the information was logged and that our formatter behaves as expected.
    formatted_caplog_record_tuples = [(r.name, r.levelno, formatter.format(r)) for r in caplog.records]

    assert len(formatted_caplog_record_tuples) == len(expect_formatted_record_tuples)

    for i in range(0, len(expect_formatted_record_tuples)):
        assert formatted_caplog_record_tuples[i] == expect_formatted_record_tuples[i]

def test_logger_message_counters(log):
    """test that message counters are incremented when messages are logged"""

    assert log.critical_count() == 0
    assert log.error_count() == 0
    assert log.warning_count() == 0

    log.critical("id1", "message1")
    assert log.critical_count() == 1
    assert log.error_count() == 0
    assert log.warning_count() == 0

    log.error("id2", "message2")
    log.error("id3", "message3")
    assert log.critical_count() == 1
    assert log.error_count() == 2
    assert log.warning_count() == 0

    log.warning("id4", "message4")
    log.warning("id5", "message5")
    log.warning("id6", "message6")
    assert log.critical_count() == 1
    assert log.error_count() == 2
    assert log.warning_count() == 3

    for level, message_count in log.message_counts.items():
        if level in (logging.CRITICAL, logging.ERROR, logging.WARNING):
            continue
        assert message_count == 0, f"should be 0, no level {level} messages were logged"
