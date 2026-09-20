import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import type { TaskListResponse } from "./api/types";
import { SESSION_KEY, clearToken, setToken } from "./auth/session";
import { jsonResponse, problemResponse } from "./testing/http";

// The shell's two responsibilities: who is signed in, and which screen is on
// screen. The third test is UI-05's second half and the reason the 401 handler
// is registered globally rather than passed to each call - a refusal from ANY
// request ends the session, and this test drives it through the lists request
// rather than through the login form.

function aList(): TaskListResponse {
  return {
    id: "list-1",
    owner_id: "owner-1",
    name: "Groceries",
    description: null,
    created_at: "2026-09-19T10:00:00Z",
    updated_at: "2026-09-19T10:00:00Z",
    total_tasks: 0,
    completed_tasks: 0,
    completion_percentage: 0,
  };
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
  vi.restoreAllMocks();
  clearToken();
  sessionStorage.clear();
});

describe("App", () => {
  it("renders the product heading", () => {
    render(<App />);

    expect(
      screen.getByRole("heading", { name: "Task Manager" }),
    ).toBeInTheDocument();
  });

  it("shows the login screen when no token is held", () => {
    render(<App />);

    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Assigned to me" }),
    ).not.toBeInTheDocument();
  });

  it("shows the lists and the navigation once a token is held", async () => {
    setToken("a-signed-token");
    fetchMock.mockResolvedValueOnce(jsonResponse(200, [aList()]));

    render(<App />);

    expect(
      await screen.findByRole("button", { name: "Groceries" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Assigned to me" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "My lists" })).toBeInTheDocument();
  });

  it("returns to the login screen when any call is refused with a 401", async () => {
    setToken("an-expired-token");
    fetchMock.mockResolvedValueOnce(
      problemResponse(401, {
        type: "urn:taskmanager:problem:authentication_failed",
        title: "Unauthorized",
        status: 401,
        detail: "The credentials could not be validated.",
        instance: "/api/v1/task-lists",
        code: "authentication_failed",
      }),
    );

    render(<App />);

    expect(await screen.findByLabelText("Email")).toBeInTheDocument();
    expect(sessionStorage.getItem(SESSION_KEY)).toBeNull();
  });

  it("clears the session when the user logs out", async () => {
    const user = userEvent.setup();
    setToken("a-signed-token");
    fetchMock.mockResolvedValueOnce(jsonResponse(200, []));

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "Log out" }));

    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(sessionStorage.getItem(SESSION_KEY)).toBeNull();
  });
});
