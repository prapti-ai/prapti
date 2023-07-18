from pathlib import Path
import logging

import prapti.core.logger
from prapti.core.source_location import SourceLocation

def test_logger_check_caplog(caplog):
    """emit all message levels. check caplog behavior"""
    log: prapti.core.logger.DiagnosticsLogger = prapti.core.logger.create_diagnostics_logger()

    log.fatal("id1", "message1")
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

def test_logger_smoke(caplog):
    """test that basic logger usage emits messages as expected and that message counters appear to work"""
    log: prapti.core.logger.DiagnosticsLogger = prapti.core.logger.create_diagnostics_logger()
    formatter: prapti.core.logger.DiagnosticRecordFormatter = prapti.core.logger.DiagnosticRecordFormatter()

    fake_error_message_parameter = "foobar"
    fake_source_loc1 = SourceLocation(Path("path/to/my/file.md"), line=1, column=2)
    fake_source_loc2 = SourceLocation(Path("path/to/my/other/file.md"), line=3, column=4)

    assert all(count == 0 for level,count in log.message_counts.items())

    # log at each logging level. with/without source location, with/without message id
    log.fatal("lots-of-errors", f"lots too many errors. an error message.", fake_source_loc1)
    log.fatal("missing-fluxwub", f"the fluxwub '{fake_error_message_parameter}' is missing")
    log.error("incorrect-fluxwub", f"the fluxwub '{fake_error_message_parameter}' is incorrect")
    log.error("bad-fluxwub", f"the fluxwub '{fake_error_message_parameter}' is bad", fake_source_loc1)
    log.warning("too-many-fluxwubs", f"the fluxwub '{fake_error_message_parameter}' exceeds fluxwub capacity", fake_source_loc2)
    log.hint("improve-dweezilwhatsit", f"improve the fluxwub with dweezilwhatsit")
    # omitting message id should omit the message id tag from the formatted message
    log.info("", f"info without message id")
    log.detail(None, f"detail without message id")
    log.debug(None, f"debug dump without message id")

    assert log.fatal_count() == 2
    assert log.error_count() == 2
    assert log.warning_count() == 1
    # check that we've emitted a message at each level:
    assert all(count != 0 for level,count in log.message_counts.items())

    # embed .file_path expressions below because pathlib.Path will render them differently on Windows and Unix
    expect_formatted_record_tuples = [
        ("prapti", logging.CRITICAL, f"{fake_source_loc1.file_path}:1:2: fatal: [lots-of-errors]: lots too many errors. an error message."),
        ("prapti", logging.CRITICAL, "<source>: fatal: [missing-fluxwub]: the fluxwub 'foobar' is missing"),
        ("prapti", logging.ERROR, "<source>: error: [incorrect-fluxwub]: the fluxwub 'foobar' is incorrect"),
        ("prapti", logging.ERROR, f"{fake_source_loc1.file_path}:1:2: error: [bad-fluxwub]: the fluxwub 'foobar' is bad"),
        ("prapti", logging.WARNING, f"{fake_source_loc2.file_path}:3:4: warning: [too-many-fluxwubs]: the fluxwub 'foobar' exceeds fluxwub capacity"),
        ("prapti", prapti.core.logger.HINT, "<source>: hint: [improve-dweezilwhatsit]: improve the fluxwub with dweezilwhatsit"),
        # notice that there is no empty ``:`-delimited section for the message id:
        ("prapti", logging.INFO, "<source>: info: info without message id"),
        ("prapti", prapti.core.logger.DETAIL, "<source>: detail: detail without message id"),
        ("prapti", logging.DEBUG, "<source>: debug: debug dump without message id"),
    ]
    # caplog captures logging records prior to formatting. In order to test our expectations
    # regarding *formatted* output, we manually format the emitted records as part of the test.
    # this serves to test both that the information was logged and that our formatter behaves as expected.
    formatted_caplog_record_tuples = [(r.name, r.levelno, formatter.format(r)) for r in caplog.records]

    assert len(formatted_caplog_record_tuples) == len(expect_formatted_record_tuples)

    for i in range(0, len(expect_formatted_record_tuples)):
        assert formatted_caplog_record_tuples[i] == expect_formatted_record_tuples[i]

def test_logger_message_counters():
    """test that message counters are incremented when messages are logged"""
    log: prapti.core.logger.DiagnosticsLogger = prapti.core.logger.create_diagnostics_logger()

    assert log.fatal_count() == 0
    assert log.error_count() == 0
    assert log.warning_count() == 0

    log.fatal("id1", "message1")
    assert log.fatal_count() == 1
    assert log.error_count() == 0
    assert log.warning_count() == 0

    log.error("id2", "message2")
    log.error("id3", "message3")
    assert log.fatal_count() == 1
    assert log.error_count() == 2
    assert log.warning_count() == 0

    log.warning("id4", "message4")
    log.warning("id5", "message5")
    log.warning("id6", "message6")
    assert log.fatal_count() == 1
    assert log.error_count() == 2
    assert log.warning_count() == 3

    for level, message_count in log.message_counts.items():
        if level in (logging.CRITICAL, logging.ERROR, logging.WARNING):
            continue
        assert message_count == 0, f"should be 0, no level {level} messages were logged"
