import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { clearToken, setToken } from "../auth/session";
import {
  ApiError,
  API_BASE,
  createTaskList,
  deleteTaskList,
  listTaskLists,
  login,
  register,
  setUnauthorizedHandler,
} from "./client";

// The contract every screen in plan 08-02 is written against. It is asserted
// against a stubbed `fetch` rather than a running API on purpose: what is being
// pinned here is the shape of the request the UI makes and the shape of the
// failure it produces, neither of which needs a database to be true.

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function problemResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/problem+json" },
  });
}

function recordedCall(mock: ReturnType<typeof vi.fn>): [string, RequestInit] {
  const call: unknown[] = mock.mock.calls[0] ?? [];
  const [url, init] = call;
  if (typeof url !== "string") {
    throw new Error("fetch was not called with a string URL");
  }
  if (init === undefined || init === null || typeof init !== "object") {
    throw new Error("fetch was not called with an init object");
  }
  return [url, init];
}

// No `as ApiError` anywhere below: a cast written to make an assertion compile
// is a cast that would keep compiling the day the client stopped throwing one.
// This narrows instead, and says so when the call did not reject at all.
async function refusalFrom(call: Promise<unknown>): Promise<ApiError> {
  try {
    await call;
  } catch (error: unknown) {
    if (error instanceof ApiError) {
      return error;
    }
    throw error;
  }
  throw new Error("the call resolved; it was expected to reject");
}

function headerOf(init: RequestInit, name: string): string | null {
  return new Headers(init.headers).get(name);
}

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  clearToken();
  setUnauthorizedHandler(null);
});

afterEach(() => {
  vi.unstubAllGlobals();
  clearToken();
  setUnauthorizedHandler(null);
});

describe("the request the client makes", () => {
  it("addresses a relative path under /api/v1, never a host", async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, []));

    await listTaskLists();

    const [url] = recordedCall(fetchMock);
    expect(API_BASE).toBe("/api/v1");
    expect(url).toBe("/api/v1/task-lists");
    expect(url.startsWith("/")).toBe(true);
    expect(url).not.toMatch(/^https?:/);
  });

  it("sends a JSON body as application/json", async () => {
    fetchMock.mockResolvedValue(jsonResponse(201, { id: "1" }));

    await createTaskList({ name: "Launch checklist" });

    const [url, init] = recordedCall(fetchMock);
    expect(url).toBe("/api/v1/task-lists");
    expect(init.method).toBe("POST");
    expect(headerOf(init, "content-type")).toBe("application/json");
    expect(init.body).toBe(JSON.stringify({ name: "Launch checklist" }));
  });

  it("sends the login as a form encoding whose username field is the email", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(200, {
        access_token: "t",
        token_type: "bearer",
        expires_in: 1800,
      }),
    );

    await login("ada@example.com", "correct-horse-battery-staple");

    const [url, init] = recordedCall(fetchMock);
    expect(url).toBe("/api/v1/auth/login");
    expect(headerOf(init, "content-type")).toBe(
      "application/x-www-form-urlencoded",
    );
    const sent = new URLSearchParams(String(init.body));
    expect(sent.get("username")).toBe("ada@example.com");
    expect(sent.get("password")).toBe("correct-horse-battery-staple");
  });

  it("carries the bearer token on every call once a session exists", async () => {
    setToken("a-signed-token");
    fetchMock.mockResolvedValue(jsonResponse(200, []));

    await listTaskLists();

    const [, init] = recordedCall(fetchMock);
    expect(headerOf(init, "authorization")).toBe("Bearer a-signed-token");
  });

  it("sends no Authorization header when there is no session", async () => {
    fetchMock.mockResolvedValue(jsonResponse(201, { id: "1" }));

    await register({
      email: "ada@example.com",
      full_name: "Ada Lovelace",
      password: "correct-horse-battery-staple",
    });

    const [, init] = recordedCall(fetchMock);
    expect(headerOf(init, "authorization")).toBeNull();
  });
});

describe("the answer the client returns", () => {
  it("resolves a 200 to the parsed body", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(200, [{ id: "1", name: "Launch checklist" }]),
    );

    const lists = await listTaskLists();

    expect(lists).toEqual([{ id: "1", name: "Launch checklist" }]);
  });

  it("resolves a 204 to undefined without attempting to parse a body", async () => {
    const response = new Response(null, { status: 204 });
    const parse = vi.spyOn(response, "json");
    fetchMock.mockResolvedValue(response);

    const answer = await deleteTaskList("24f0c966");

    expect(answer).toBeUndefined();
    expect(parse).not.toHaveBeenCalled();
  });
});

describe("the failure the client produces", () => {
  it("rejects a problem+json refusal with every member of the body", async () => {
    fetchMock.mockResolvedValue(
      problemResponse(409, {
        type: "urn:taskmanager:problem:duplicate_task_list_name",
        title: "Conflict",
        status: 409,
        detail: "You already have a task list named 'Launch checklist'.",
        instance: "/api/v1/task-lists",
        code: "duplicate_task_list_name",
        errors: { name: "already used" },
      }),
    );

    const problem = await refusalFrom(
      createTaskList({ name: "Launch checklist" }),
    );

    expect(problem.status).toBe(409);
    expect(problem.code).toBe("duplicate_task_list_name");
    expect(problem.title).toBe("Conflict");
    expect(problem.detail).toBe(
      "You already have a task list named 'Launch checklist'.",
    );
    expect(problem.errors).toEqual({ name: "already used" });
  });

  it("calls the unauthorized handler exactly once on a 401", async () => {
    const onUnauthorized = vi.fn();
    setUnauthorizedHandler(onUnauthorized);
    fetchMock.mockResolvedValue(
      problemResponse(401, {
        type: "urn:taskmanager:problem:authentication_failed",
        title: "Unauthorized",
        status: 401,
        detail: "Not authenticated.",
        instance: "/api/v1/task-lists",
        code: "authentication_failed",
      }),
    );

    const failure = await refusalFrom(listTaskLists());

    expect(failure.status).toBe(401);
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
  });

  it("turns an unparseable answer into the one failure the UI words itself", async () => {
    fetchMock.mockResolvedValue(
      new Response("<html><body>502 Bad Gateway</body></html>", {
        status: 502,
        headers: { "content-type": "text/html" },
      }),
    );

    const failure = await refusalFrom(listTaskLists());

    expect(failure.code).toBe("network");
    expect(failure.detail).not.toBe("");
  });

  it("turns a rejected fetch into the same network failure", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));

    const failure = await refusalFrom(listTaskLists());

    expect(failure.code).toBe("network");
    expect(failure.status).toBe(0);
  });
});
