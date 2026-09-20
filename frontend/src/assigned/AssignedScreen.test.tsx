import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { TaskResponse } from "../api/types";
import { clearToken, setToken } from "../auth/session";
import {
  jsonResponse,
  onlyRequest,
  problemResponse,
  serving,
} from "../testing/http";
import AssignedScreen from "./AssignedScreen";

// UI-04's other half: everything assigned to the caller, across every list.
//
// The third test asserts an ABSENCE, which is unusual enough to explain. This
// endpoint answers a bare `TaskResponse[]` - no counters at all - so a
// completion bar here could only be a number this UI made up. That is the same
// mistake ADR-009 forbids on the tasks screen, pointing the other way.

function aTask(overrides: Partial<TaskResponse> = {}): TaskResponse {
  return {
    id: "task-1",
    task_list_id: "list-7",
    title: "Review the proposal",
    description: null,
    status: "in_progress",
    priority: "high",
    created_at: "2026-09-19T10:00:00Z",
    updated_at: "2026-09-19T10:00:00Z",
    due_date: null,
    completed_at: null,
    assignee_id: "user-1",
    ...overrides,
  };
}

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  setToken("a-signed-token");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  clearToken();
  sessionStorage.clear();
});

describe("assigned to me", () => {
  it("reads the caller's assigned tasks once and shows each one's status and priority", async () => {
    fetchMock.mockImplementation(
      serving([
        {
          path: "/tasks/assigned-to-me",
          respond: () =>
            jsonResponse(200, [
              aTask(),
              aTask({
                id: "task-2",
                title: "Ship the release",
                status: "pending",
                priority: "low",
              }),
            ]),
        },
      ]),
    );

    render(<AssignedScreen onBack={vi.fn()} />);

    expect(await screen.findByText("Review the proposal")).toBeInTheDocument();
    expect(screen.getByText("Ship the release")).toBeInTheDocument();
    expect(screen.getByText("In progress")).toBeInTheDocument();
    expect(screen.getByText("High")).toBeInTheDocument();
    expect(screen.getByText("Pending")).toBeInTheDocument();
    expect(screen.getByText("Low")).toBeInTheDocument();

    const read = onlyRequest(fetchMock, "GET", "/api/v1/tasks/assigned-to-me");
    expect(read.url).toBe("/api/v1/tasks/assigned-to-me");
  });

  it("says so explicitly when nothing is assigned to the caller", async () => {
    fetchMock.mockImplementation(
      serving([
        { path: "/tasks/assigned-to-me", respond: () => jsonResponse(200, []) },
      ]),
    );

    render(<AssignedScreen onBack={vi.fn()} />);

    expect(
      await screen.findByText("Nothing is assigned to you."),
    ).toBeInTheDocument();
  });

  it("renders no completion bar, because this response carries no counters to render one from", async () => {
    fetchMock.mockImplementation(
      serving([
        {
          path: "/tasks/assigned-to-me",
          respond: () => jsonResponse(200, [aTask()]),
        },
      ]),
    );

    render(<AssignedScreen onBack={vi.fn()} />);
    await screen.findByText("Review the proposal");

    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  });

  it("renders a refusal from the API's own body", async () => {
    fetchMock.mockImplementation(
      serving([
        {
          path: "/tasks/assigned-to-me",
          respond: () =>
            problemResponse(503, {
              type: "urn:taskmanager:problem:internal_error",
              title: "Service Unavailable",
              status: 503,
              detail: "The service is temporarily unavailable.",
              instance: "/api/v1/tasks/assigned-to-me",
              code: "internal_error",
            }),
        },
      ]),
    );

    render(<AssignedScreen onBack={vi.fn()} />);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("The service is temporarily unavailable.");
    expect(alert).toHaveTextContent("internal_error");
  });

  it("can go back to the lists", async () => {
    const user = userEvent.setup();
    const onBack = vi.fn();
    fetchMock.mockImplementation(
      serving([
        { path: "/tasks/assigned-to-me", respond: () => jsonResponse(200, []) },
      ]),
    );

    render(<AssignedScreen onBack={onBack} />);
    await screen.findByText("Nothing is assigned to you.");

    await user.click(screen.getByRole("button", { name: "Back to lists" }));

    expect(onBack).toHaveBeenCalledOnce();
  });
});
