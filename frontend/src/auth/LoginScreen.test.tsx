import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { clearToken } from "./session";
import LoginScreen from "./LoginScreen";

// UI-01 and UI-05 for the auth screen. Two properties are being pinned here and
// they are the ones a reviewer should care about:
//   * every control is found by its ACCESSIBLE NAME - by label text, never by a
//     test id. A field a test can only reach through a test id is a field a
//     screen reader cannot reach either;
//   * the text shown for a refusal is the API's own `detail`, asserted verbatim.
//     A test that matched a string the component invented would pass while the
//     component ignored the RFC 9457 body entirely (D-07).

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

function recordedCall(
  mock: ReturnType<typeof vi.fn>,
): [string, RequestInit] {
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

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  clearToken();
  sessionStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
  clearToken();
  sessionStorage.clear();
});

describe("logging in", () => {
  it("posts the form encoding and hands the token to its caller", async () => {
    const user = userEvent.setup();
    const onAuthenticated = vi.fn();
    fetchMock.mockResolvedValue(
      jsonResponse(200, {
        access_token: "a-signed-token",
        token_type: "bearer",
        expires_in: 1800,
      }),
    );
    render(<LoginScreen onAuthenticated={onAuthenticated} />);

    await user.type(screen.getByLabelText("Email"), "ada@example.com");
    await user.type(
      screen.getByLabelText("Password"),
      "correct-horse-battery-staple",
    );
    await user.click(screen.getByRole("button", { name: "Log in" }));

    const [url, init] = recordedCall(fetchMock);
    expect(url).toBe("/api/v1/auth/login");
    expect(new Headers(init.headers).get("content-type")).toBe(
      "application/x-www-form-urlencoded",
    );
    expect(new URLSearchParams(String(init.body)).get("username")).toBe(
      "ada@example.com",
    );
    expect(onAuthenticated).toHaveBeenCalledWith("a-signed-token");
  });

  it("renders the refusal's own detail in an alert", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValue(
      problemResponse(401, {
        type: "urn:taskmanager:problem:authentication_failed",
        title: "Unauthorized",
        status: 401,
        detail: "Incorrect email or password.",
        instance: "/api/v1/auth/login",
        code: "authentication_failed",
      }),
    );
    render(<LoginScreen onAuthenticated={vi.fn()} />);

    await user.type(screen.getByLabelText("Email"), "ada@example.com");
    await user.type(screen.getByLabelText("Password"), "wrong");
    await user.click(screen.getByRole("button", { name: "Log in" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Incorrect email or password.");
    expect(alert).toHaveTextContent("authentication_failed");
  });
});

describe("creating an account", () => {
  it("posts the three registration fields as JSON", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValue(
      jsonResponse(201, {
        id: "a3e833d0",
        email: "ada@example.com",
        full_name: "Ada Lovelace",
        created_at: "2026-09-19T00:00:00Z",
      }),
    );
    render(<LoginScreen onAuthenticated={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Create an account" }));
    await user.type(screen.getByLabelText("Email"), "ada@example.com");
    await user.type(screen.getByLabelText("Full name"), "Ada Lovelace");
    await user.type(
      screen.getByLabelText("Password"),
      "correct-horse-battery-staple",
    );
    await user.click(screen.getByRole("button", { name: "Register" }));

    const [url, init] = recordedCall(fetchMock);
    expect(url).toBe("/api/v1/auth/register");
    expect(new Headers(init.headers).get("content-type")).toBe(
      "application/json",
    );
    expect(JSON.parse(String(init.body))).toEqual({
      email: "ada@example.com",
      full_name: "Ada Lovelace",
      password: "correct-horse-battery-staple",
    });
  });

  it("renders the 409 the API answers for an email already registered", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValue(
      problemResponse(409, {
        type: "urn:taskmanager:problem:email_already_registered",
        title: "Conflict",
        status: 409,
        detail: "An account with this email already exists.",
        instance: "/api/v1/auth/register",
        code: "email_already_registered",
      }),
    );
    render(<LoginScreen onAuthenticated={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Create an account" }));
    await user.type(screen.getByLabelText("Email"), "ada@example.com");
    await user.type(screen.getByLabelText("Full name"), "Ada Lovelace");
    await user.type(screen.getByLabelText("Password"), "whatever-it-was");
    await user.click(screen.getByRole("button", { name: "Register" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("An account with this email already exists.");
    expect(alert).toHaveTextContent("email_already_registered");
  });
});
