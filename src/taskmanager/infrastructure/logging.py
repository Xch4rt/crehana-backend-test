"""One JSON line per record, on stdout, so D-15's message actually exists.

uvicorn's `LOGGING_CONFIG` declares handlers for the `uvicorn`, `uvicorn.error`
and `uvicorn.access` loggers and for nothing else. It attaches nothing to the
root logger and leaves root at WARNING, so an INFO record from anywhere in this
package is dropped before it is written: verified by execution, an
`info(...)` call under `taskmanager` printed nothing at all, while an
`error(...)` call printed through `logging.lastResort` unformatted. NOTF-02
asks for a message an evaluator finds with one grep in `docker compose logs
api`; without this module there is nothing to find. That is D-24, and this
module is its whole implementation.

Four decisions, each of which looks arbitrary until its consequence is named.

**`propagate` is left alone, and must stay true.** pytest's `caplog` attaches
its handler to the *root* logger, so a record that stops at `taskmanager` never
reaches it. Two assertions in
`tests/unit/presentation/test_error_contract.py` read records off `caplog`
today and both would break. There is no double printing to buy by
switching it off either: `logging.lastResort` fires only when no handler was
found anywhere along the chain, and root has no handler of its own in the
container, so once the handler below exists each record is written exactly
once.

**The handler carries a private marker and a second call returns early.**
`create_app()` is a factory that runs hundreds of times across the test suite,
and every one of those calls will reach this function once plan 05-11 wires it
in. Without the marker each call would attach another handler and every line
would be printed once per call.

**The handler goes on the package logger, not on `taskmanager.notifications`
alone.** The narrower choice was available and is rejected: one place, one
output shape. The consequence is visible and belongs here rather than in a
changelog - the existing ERROR record from
`presentation/api/errors/handlers.py` is emitted as JSON from now on. That is a
deliberate change to existing behaviour and an improvement, because the fixed
500's log line becomes machine-readable; its *content* is unchanged.

**The stream is `sys.stdout`.** That is what `docker compose logs api` reads,
and it is what keeps this function free of I/O at call time - a file-bound
handler would perform a write-open here and break the promise `main.py` makes
that building the application touches nothing outside the process.

Two things the formatter deliberately does not do. It does not hand `json.dumps`
a fallback coercion, because the only caller that has a value of its own to log
stringifies it at the call site, and a silent coercion would turn a call-site
bug into a line whose shape nobody chose. And it does not render `stack_info`:
nothing in this project passes it, so the branch would be one no test could
reach, which the project's no-suppression coverage rule has no way to excuse.
What it does render is the exception: `handlers.py` promises the traceback
reaches the log and nowhere else, and `exc_info` is a reserved record attribute,
so a formatter that merged only the extras would have thrown every traceback in
the application away.
"""

import json
import logging
import sys
from typing import Any, Final

PACKAGE_LOGGER: Final[str] = "taskmanager"

# The attribute that tells a second call the handler is already ours. A private
# name rather than a subclass, so `isinstance` checks elsewhere cannot start
# depending on a type this module would then owe them.
_MARKER: Final[str] = "_taskmanager_json"

# Computed from a throwaway record rather than typed out. A hard-coded list of
# the record's own attribute names drifts with the standard library - `taskName`
# arrived in 3.12 - and the drift is silent: a name this set failed to mention
# would simply appear in every line of output.
_RESERVED: Final[frozenset[str]] = frozenset(
    logging.LogRecord("", 0, "", 0, "", None, None).__dict__
)


class JsonFormatter(logging.Formatter):
    """Renders a record as one line of JSON: three base fields plus the extras."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Everything the caller passed through `extra=`, and nothing else: the
        # difference between the record's attributes and a fresh record's is
        # exactly that set.
        payload.update(
            {
                key: value
                for key, value in record.__dict__.items()
                if key not in _RESERVED
            }
        )
        if record.exc_info is not None:
            payload["exception"] = self.formatException(record.exc_info)
        # One line by construction, which is the T-5-13 mitigation: every value
        # goes through `json.dumps`, so a newline inside a task title is escaped
        # and the title cannot forge a second record.
        return json.dumps(payload)


def configure_logging(level: int = logging.INFO) -> None:
    """Attach the JSON handler to the `taskmanager` logger, at most once."""
    logger = logging.getLogger(PACKAGE_LOGGER)
    if any(getattr(handler, _MARKER, False) for handler in logger.handlers):
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    setattr(handler, _MARKER, True)
    logger.addHandler(handler)
    logger.setLevel(level)
