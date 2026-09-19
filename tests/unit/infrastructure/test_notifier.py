"""`LoggingEmailNotifier`: the one message this product sends, and does not send.

The port binding lives in `test_adapter_ports.py`, not here, for the reason
that module's own docstring gives: a port binding has one home, and asserting
it twice would make a single change to `EmailNotifier` look like two problems.
This module is about behaviour.

Every assertion below reads the record's structured *attributes*, or the JSON
the project's own formatter produces from it - never a substring of the
rendered message. D-15 promises `event`, `to`, `subject`, `body` and `task_id`
as fields an evaluator can grep for, and a test that matched on the message
text would keep passing after those fields were flattened back into it.

`caplog` defaults to WARNING, so every test that expects the INFO line opens
`caplog.at_level(logging.INFO, logger=...)` first. A test that forgets asserts
on an empty list and passes for the wrong reason.
"""

import inspect
import json
import logging
import socket
from typing import Any
from uuid import UUID, uuid4

import pytest

from taskmanager.infrastructure.logging import JsonFormatter
from taskmanager.infrastructure.notifications import logging as notifier_module
from taskmanager.infrastructure.notifications.logging import (
    ASSIGNED_TASKS_PATH,
    LOGGER_NAME,
    LoggingEmailNotifier,
)

pytestmark = pytest.mark.unit

RECIPIENT = "assignee@example.com"
TITLE = "Ship the release notes"


def records_of(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    """Only this adapter's records: the suite's root handler collects everyone's."""
    return [record for record in caplog.records if record.name == LOGGER_NAME]


async def send(
    caplog: pytest.LogCaptureFixture,
    *,
    task_title: str = TITLE,
    task_id: UUID | None = None,
) -> logging.LogRecord:
    """Send once at INFO and hand back the single record it produced."""
    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        await LoggingEmailNotifier().send_task_assigned(
            recipient_email=RECIPIENT,
            task_title=task_title,
            task_id=task_id or uuid4(),
        )
    emitted = records_of(caplog)
    assert len(emitted) == 1
    return emitted[0]


async def test_sending_emits_exactly_one_info_record_on_the_notifications_logger(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """One assignment, one line - D-15 promises a message, not a conversation."""
    record = await send(caplog)

    assert record.name == LOGGER_NAME
    assert record.levelno == logging.INFO
    assert LOGGER_NAME.startswith("taskmanager.")


async def test_the_record_carries_the_field_set_d15_names(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`event` is the grep handle; the other three are the message itself."""
    task_id = uuid4()

    record = await send(caplog, task_id=task_id)
    payload = json.loads(JsonFormatter().format(record))

    assert payload["event"] == "task_assigned_email"
    assert payload["to"] == RECIPIENT
    assert payload["task_id"] == str(task_id)
    assert TITLE in payload["subject"]
    assert payload["message"] == "Task assignment invitation"


async def test_the_task_id_is_a_string_rather_than_a_uuid(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A `UUID` is not JSON-serialisable, and `json.dumps` raises inside the formatter.

    Stringifying at the call site is what keeps a notification from becoming a
    logging failure. Asserting the *type* rather than only the rendered value
    is the point: the rendered value would look identical either way, right up
    until the formatter raised.
    """
    task_id = uuid4()

    record = await send(caplog, task_id=task_id)

    assert record.__dict__["task_id"] == str(task_id)
    assert isinstance(record.__dict__["task_id"], str)


async def test_the_body_names_the_task_title_and_where_to_find_it(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The port carries no `task_list_id`, so the body names the flat route (D-02)."""
    record = await send(caplog)
    body = json.loads(JsonFormatter().format(record))["body"]

    assert TITLE in body
    assert ASSIGNED_TASKS_PATH in body


async def test_a_newline_in_the_title_still_produces_one_parseable_line(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """T-5-13 end to end: a title an assignee typed cannot forge a second record."""
    injected = 'Ship it\n{"level": "ERROR", "logger": "taskmanager", "message": "x"}'

    record = await send(caplog, task_title=injected)
    line = JsonFormatter().format(record)

    assert len(line.splitlines()) == 1
    payload = json.loads(line)
    assert injected in payload["body"]
    assert payload["event"] == "task_assigned_email"


async def test_sending_opens_no_connection(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Being simulated is a property of this adapter, falsifiable right here."""

    def no_connection(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("the notifier opened a connection")

    monkeypatch.setattr(socket, "socket", no_connection)

    record = await send(caplog)

    assert record.__dict__["event"] == "task_assigned_email"


def test_the_module_imports_no_mail_library() -> None:
    """The adapter swap is what makes NOTF-02's simulation visible (T-5-14).

    A source scan rather than a runtime check, because the property is about
    what the file contains: a mail library imported but not yet called would
    pass every behavioural assertion above and would still mean this adapter
    had started growing the thing it exists not to be.
    """
    source = inspect.getsource(notifier_module)

    for forbidden in ("smtplib", "aiosmtplib", "email.message", "SMTP("):
        assert forbidden not in source
