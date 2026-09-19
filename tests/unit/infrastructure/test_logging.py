"""The JSON handler that makes D-15's line exist at all (D-24).

Every test here mutates process-wide state - the `taskmanager` logger's handler
list, its level and its propagation flag are one object shared by the whole
suite - so the autouse fixture below both clears that state before a test and
puts back exactly what pytest left. Without the restore half, the two `caplog`
assertions in `tests/unit/presentation/test_error_contract.py` would start depending on
whether this module happened to run first; without the clear half, the
idempotence assertion would be counting handlers somebody else attached.

Two of the assertions are about the formatter rather than about logging, and
they are the ones worth keeping honest. The injection test (T-5-13) builds a
record whose *message* contains a newline and a complete JSON object and
asserts the result is still one line with the injected text as a value - a
title an assignee typed cannot become a second log record. The exception test
asserts the opposite of a regression this module could easily have shipped:
`presentation/api/errors/handlers.py` logs the fixed 500 with `exc_info=exc`
and its docstring promises the traceback reaches the log, so a formatter that
serialised only the three base fields would have silently thrown every
traceback in the application away.
"""

import json
import logging
import socket
from collections.abc import Iterator
from typing import Any

import pytest

from taskmanager.infrastructure.logging import (
    PACKAGE_LOGGER,
    JsonFormatter,
    configure_logging,
)

NOTIFICATIONS_LOGGER = "taskmanager.notifications"


@pytest.fixture(autouse=True)
def _isolate_the_package_logger() -> Iterator[None]:
    """Start from a known handler list and hand back the one pytest owns."""
    logger = logging.getLogger(PACKAGE_LOGGER)
    handlers = list(logger.handlers)
    level = logger.level
    propagate = logger.propagate
    logger.handlers = []
    yield
    logger.handlers = handlers
    logger.setLevel(level)
    logger.propagate = propagate


def a_record(
    message: str,
    *,
    exc_info: Any = None,
    extra: dict[str, Any] | None = None,
) -> logging.LogRecord:
    """A record made the way the logging module makes one, without emitting it."""
    return logging.getLogger(NOTIFICATIONS_LOGGER).makeRecord(
        NOTIFICATIONS_LOGGER,
        logging.INFO,
        "some_module.py",
        1,
        message,
        (),
        exc_info,
        extra=extra,
    )


def test_configuring_twice_leaves_exactly_one_handler() -> None:
    """`create_app()` runs hundreds of times here; the line must not multiply."""
    configure_logging()
    configure_logging()

    assert len(logging.getLogger(PACKAGE_LOGGER).handlers) == 1


def test_the_second_call_keeps_the_handler_the_first_one_attached() -> None:
    """Idempotence by marker, not by count.

    A count alone would be satisfied by an implementation that removed the
    handler and attached a fresh one, which drops whatever the first call
    configured on it.
    """
    configure_logging()
    first = logging.getLogger(PACKAGE_LOGGER).handlers[0]

    configure_logging()

    assert logging.getLogger(PACKAGE_LOGGER).handlers[0] is first


def test_the_package_logger_is_set_to_info() -> None:
    """WARNING - uvicorn's effective default - would drop D-15's line entirely."""
    configure_logging()

    assert logging.getLogger(PACKAGE_LOGGER).level == logging.INFO


def test_an_info_record_is_printed_to_stdout_as_one_json_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The whole point: without this module the record is dropped silently."""
    configure_logging()

    logging.getLogger(NOTIFICATIONS_LOGGER).info("Task assignment invitation")

    printed = capsys.readouterr().out
    assert len(printed.splitlines()) == 1
    assert json.loads(printed) == {
        "level": "INFO",
        "logger": NOTIFICATIONS_LOGGER,
        "message": "Task assignment invitation",
    }


def test_fields_passed_through_extra_become_top_level_keys(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """D-15's field set is greppable only if each field is its own key."""
    configure_logging()

    logging.getLogger(NOTIFICATIONS_LOGGER).info(
        "Task assignment invitation",
        extra={"event": "task_assigned_email", "to": "assignee@example.com"},
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["event"] == "task_assigned_email"
    assert payload["to"] == "assignee@example.com"


def test_reserved_record_attributes_never_reach_the_payload() -> None:
    """The record's own machinery is not output, and the set is computed, not listed."""
    payload = json.loads(JsonFormatter().format(a_record("hello")))

    for reserved in ("msg", "args", "pathname", "lineno", "created", "name"):
        assert reserved not in payload


def test_a_newline_in_the_message_cannot_forge_a_second_record() -> None:
    """T-5-13: a task title reaches this stream as data, never as a record.

    `json.dumps` escapes the newline, so the forged object below is a value
    inside `message` rather than a line of its own - which is what makes the
    log stream parseable by a reader that splits on newlines.
    """
    injected = 'Ship it\n{"level": "ERROR", "logger": "taskmanager", "message": "x"}'

    line = JsonFormatter().format(a_record(injected))

    assert len(line.splitlines()) == 1
    payload = json.loads(line)
    assert payload["message"] == injected
    assert payload["level"] == "INFO"
    assert payload["logger"] == NOTIFICATIONS_LOGGER


def test_an_exception_is_rendered_into_the_line_rather_than_dropped() -> None:
    """The 500 handler's `exc_info=exc` must survive the change of formatter.

    `handlers.py` says the traceback goes to the log and nowhere else. Merging
    only the non-reserved attributes would have dropped it, because `exc_info`
    is a reserved attribute - a regression nothing else in the suite would have
    caught, since the existing assertions read `record.exc_info` rather than
    the formatted output.
    """
    try:
        raise RuntimeError("boom")
    except RuntimeError as error:
        record = a_record(
            "Unhandled exception",
            exc_info=(type(error), error, error.__traceback__),
        )

    line = JsonFormatter().format(record)

    assert len(line.splitlines()) == 1
    payload = json.loads(line)
    assert "Traceback" in payload["exception"]
    assert "RuntimeError: boom" in payload["exception"]


def test_a_record_without_an_exception_carries_no_exception_key() -> None:
    """The ordinary record stays three keys wide."""
    payload = json.loads(JsonFormatter().format(a_record("hello")))

    assert "exception" not in payload


def test_propagation_stays_on_so_caplog_still_sees_the_record(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`propagate = False` would break two existing assertions in the API suite.

    pytest attaches `caplog`'s handler to the **root** logger, so a record that
    stops at `taskmanager` never reaches it. The flag is asserted and the
    consequence is exercised, because the flag alone would pass against a
    handler that swallowed the record some other way.
    """
    configure_logging()

    with caplog.at_level(logging.INFO, logger=NOTIFICATIONS_LOGGER):
        logging.getLogger(NOTIFICATIONS_LOGGER).info("visible to caplog")

    assert logging.getLogger(PACKAGE_LOGGER).propagate is True
    assert [record.getMessage() for record in caplog.records] == ["visible to caplog"]


def test_configuring_logging_opens_no_connection_and_reads_no_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`create_app()` will call this, and building the application touches nothing.

    The same falsifiable form `test_security_resources.py` uses: both refusals
    raise, so a handler pointed at a file or at a log-shipping endpoint would
    fail here rather than quietly adding a prerequisite to every unit test that
    builds the application.
    """

    def no_connection(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("configure_logging() opened a connection")

    def no_file(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("configure_logging() read a file")

    monkeypatch.setattr(socket, "socket", no_connection)
    monkeypatch.setattr("builtins.open", no_file)

    configure_logging()

    assert len(logging.getLogger(PACKAGE_LOGGER).handlers) == 1
