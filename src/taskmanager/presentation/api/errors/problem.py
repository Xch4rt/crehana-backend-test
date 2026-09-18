"""The single RFC 9457 body builder. Every error this app emits is built here.

`type` is the stable URN `urn:taskmanager:problem:{code}` (D-05). The two
rejected alternatives were `about:blank`, which carries no information at all,
and a fictional `https://` documentation domain, which promises a page that
does not exist and would 404 for the first evaluator who clicked it. RFC 9457
requires the member to be a URI, not a *dereferenceable* one - it gives `tag:`
URIs as an explicit example - so a URN is compliant, stable and honest.

The other rejected alternative is each handler assembling its own dict. The
CLAUDE.md error-handling rule forbids it, and for a concrete reason: two
handlers written a week apart drift in member order, in spelling and in which
members they bother to include, and the "one shape" claim of ARC-07 quietly
stops being true. Every handler in `handlers.py` calls this function instead.
"""

from typing import Any, Final

from fastapi.responses import JSONResponse

PROBLEM_JSON: Final[str] = "application/problem+json"


def problem(
    *,
    code: str,
    title: str,
    status: int,
    detail: str,
    instance: str,
    errors: Any = None,
) -> JSONResponse:
    """Build the one RFC 9457 body shape: D-06 members in order, `errors` last.

    Arguments are keyword-only because five of the six are strings: a
    positional call site would be one transposition away from serving the
    title as the detail, and no test would notice.
    """
    # Member order is not decoration. Python dicts are insertion-ordered and
    # `json.dumps` writes keys in insertion order, so building the body as a
    # literal in this order is what makes D-06's "always in this order"
    # mechanically true rather than aspirational.
    body: dict[str, Any] = {
        "type": f"urn:taskmanager:problem:{code}",
        "title": title,
        "status": status,
        "detail": detail,
        "instance": instance,
        "code": code,
    }
    # Truthiness, not `is not None`: an empty details dict or an empty error
    # list carries nothing, and RFC 9457 extension members are optional.
    if errors:
        body["errors"] = errors
    return JSONResponse(body, status_code=status, media_type=PROBLEM_JSON)
