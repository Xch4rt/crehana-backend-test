// The fetch-boundary test helpers, in one place because five test files need
// them and a copy per file is five chances to let one drift.
//
// Nothing here is imported by a component, so it never reaches the bundle: the
// entry point is `main.tsx` and this module is unreachable from it.
//
// Every accessor narrows `unknown` with a real check instead of an `as` cast.
// A cast here would be the worst possible place for one - it would make a test
// that reads the wrong member of a fetch call pass by assertion of the author.

export function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

export function problemResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/problem+json" },
  });
}

// Both DELETEs in this API answer 204 with no body at all - not an empty
// object, and not a JSON `null`.
export function noContent(): Response {
  return new Response(null, { status: 204 });
}

export interface RecordedRequest {
  url: string;
  method: string;
  body: string | null;
}

// Structural on purpose: a `vi.fn()` satisfies it without this module importing
// vitest's `Mock` type and pinning itself to that shape.
export interface CallRecorder {
  mock: { calls: unknown[][] };
}

function methodOf(init: unknown): string {
  if (typeof init === "object" && init !== null && "method" in init) {
    const { method } = init;
    if (typeof method === "string") {
      return method;
    }
  }
  // fetch's own default, which is what the client relies on for a plain read.
  return "GET";
}

function bodyOf(init: unknown): string | null {
  if (typeof init === "object" && init !== null && "body" in init) {
    const { body } = init;
    if (typeof body === "string") {
      return body;
    }
  }
  return null;
}

function recordOf(url: unknown, init: unknown): RecordedRequest {
  if (typeof url !== "string") {
    throw new Error("fetch was not called with a string URL");
  }
  return { url, method: methodOf(init), body: bodyOf(init) };
}

export function requests(mock: CallRecorder): RecordedRequest[] {
  return mock.mock.calls.map((call) => recordOf(call[0], call[1]));
}

export interface Handler {
  method?: string;
  // A substring of the URL, so `?priority=high` is a different route from the
  // unfiltered one without writing a matcher language.
  path: string;
  times?: number;
  respond: () => Response;
}

// A `fetch` implementation that answers by ROUTE instead of by call order.
//
// A screen that reads two things on mount (its tasks and the user directory)
// has no guaranteed order between them, and a queue of `mockResolvedValueOnce`
// silently hands the wrong body to whichever effect ran first. Routing also
// means each handler builds a FRESH Response: a `Response` body can only be
// read once, so a reused one fails the second time in a way that looks like a
// parsing bug in the client.
export function serving(
  handlers: Handler[],
): (url: unknown, init: unknown) => Promise<Response> {
  const remaining = handlers.map((handler) => ({
    handler,
    left: handler.times ?? Number.POSITIVE_INFINITY,
  }));
  return (url: unknown, init: unknown) => {
    const request = recordOf(url, init);
    for (const entry of remaining) {
      if (
        entry.left > 0 &&
        (entry.handler.method ?? "GET") === request.method &&
        request.url.includes(entry.handler.path)
      ) {
        entry.left -= 1;
        return Promise.resolve(entry.handler.respond());
      }
    }
    return Promise.reject(
      new Error(`no stub for ${request.method} ${request.url}`),
    );
  };
}

export function lastRequest(mock: CallRecorder): RecordedRequest {
  const all = requests(mock);
  const last = all[all.length - 1];
  if (last === undefined) {
    throw new Error("fetch was never called");
  }
  return last;
}

// "the request this behaviour was supposed to make", named by verb and by a
// fragment of the path, so a test asserts the call it means rather than
// whichever one happened to be last.
export function requestsMatching(
  mock: CallRecorder,
  method: string,
  fragment: string,
): RecordedRequest[] {
  return requests(mock).filter(
    (recorded) =>
      recorded.method === method && recorded.url.includes(fragment),
  );
}

export function onlyRequest(
  mock: CallRecorder,
  method: string,
  fragment: string,
): RecordedRequest {
  const matched = requestsMatching(mock, method, fragment);
  if (matched.length !== 1) {
    throw new Error(
      `expected exactly one ${method} ${fragment}, saw ${String(
        matched.length,
      )}: ${requests(mock)
        .map((one) => `${one.method} ${one.url}`)
        .join(", ")}`,
    );
  }
  const single = matched[0];
  if (single === undefined) {
    throw new Error("unreachable: length was checked");
  }
  return single;
}

export function jsonBodyOf(recorded: RecordedRequest): unknown {
  if (recorded.body === null) {
    throw new Error(`${recorded.method} ${recorded.url} carried no body`);
  }
  return JSON.parse(recorded.body);
}
