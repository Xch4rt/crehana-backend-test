import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { TaskResponse, UserSummaryResponse } from "../api/types";
import { clearToken, setToken } from "../auth/session";
import {
  jsonBodyOf,
  jsonResponse,
  onlyRequest,
  problemResponse,
  serving,
} from "../testing/http";
import AssigneePicker from "./AssigneePicker";

// UI-04's control. The third test is the one with teeth: unassigning answers
// **200 with the updated task**, not the 204 both DELETEs on the task and the
// list answer, so the component has to USE the response body. Asserting that
// `onChanged` received the body - and not the task it already held - is what
// makes "assumed 204" a red test rather than a latent bug that shows up as a
// row which never quite refreshes.

const USERS: UserSummaryResponse[] = [
  { id: "user-1", full_name: "Ada Lovelace", email: "ada@example.com" },
  { id: "user-2", full_name: "Grace Hopper", email: "grace@example.com" },
];

function aTask(overrides: Partial<TaskResponse> = {}): TaskResponse {
  return {
    id: "task-1",
    task_list_id: "list-1",
    title: "Buy milk",
    description: null,
    status: "pending",
    priority: "medium",
    created_at: "2026-09-19T10:00:00Z",
    updated_at: "2026-09-19T10:00:00Z",
    due_date: null,
    completed_at: null,
    assignee_id: null,
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

describe("the assignee control", () => {
  it("offers every user in the directory by name and email, plus nobody", () => {
    render(
      <AssigneePicker task={aTask()} users={USERS} onChanged={vi.fn()} />,
    );

    const control = screen.getByLabelText("Assignee of Buy milk");
    expect(
      within(control).getByRole("option", { name: "Unassigned" }),
    ).toBeInTheDocument();
    expect(
      within(control).getByRole("option", {
        name: "Ada Lovelace (ada@example.com)",
      }),
    ).toBeInTheDocument();
    expect(
      within(control).getByRole("option", {
        name: "Grace Hopper (grace@example.com)",
      }),
    ).toBeInTheDocument();
  });

  it("shows the current assignee as the selection", () => {
    render(
      <AssigneePicker
        task={aTask({ assignee_id: "user-2" })}
        users={USERS}
        onChanged={vi.fn()}
      />,
    );

    expect(screen.getByLabelText("Assignee of Buy milk")).toHaveValue("user-2");
  });

  it("shows an assignee who is not in the directory as their raw id, never as unassigned", () => {
    render(
      <AssigneePicker
        task={aTask({ assignee_id: "a-stranger-id" })}
        users={USERS}
        onChanged={vi.fn()}
      />,
    );

    const control = screen.getByLabelText("Assignee of Buy milk");
    expect(control).toHaveValue("a-stranger-id");
    expect(
      within(control).getByRole("option", { selected: true }),
    ).toHaveTextContent("a-stranger-id");
  });

  it("puts the assignee id and hands its caller the task the API answered", async () => {
    const user = userEvent.setup();
    const onChanged = vi.fn();
    fetchMock.mockImplementation(
      serving([
        {
          method: "PUT",
          path: "/tasks/task-1/assignee",
          respond: () =>
            jsonResponse(200, aTask({ assignee_id: "user-2", updated_at: "2026-09-19T12:00:00Z" })),
        },
      ]),
    );

    render(
      <AssigneePicker task={aTask()} users={USERS} onChanged={onChanged} />,
    );
    await user.selectOptions(
      screen.getByLabelText("Assignee of Buy milk"),
      "user-2",
    );

    const put = onlyRequest(
      fetchMock,
      "PUT",
      "/api/v1/task-lists/list-1/tasks/task-1/assignee",
    );
    expect(jsonBodyOf(put)).toEqual({ assignee_id: "user-2" });
    expect(onChanged).toHaveBeenCalledWith(
      expect.objectContaining({
        assignee_id: "user-2",
        updated_at: "2026-09-19T12:00:00Z",
      }),
    );
  });

  it("unassigns through DELETE and uses the 200 body it answers rather than assuming a 204", async () => {
    const user = userEvent.setup();
    const onChanged = vi.fn();
    // The API answers the UPDATED TASK here. A component that assumed an empty
    // 204 would have nothing to hand on, and this assertion is how that shows.
    fetchMock.mockImplementation(
      serving([
        {
          method: "DELETE",
          path: "/tasks/task-1/assignee",
          respond: () =>
            jsonResponse(
              200,
              aTask({ assignee_id: null, updated_at: "2026-09-19T13:00:00Z" }),
            ),
        },
      ]),
    );

    render(
      <AssigneePicker
        task={aTask({ assignee_id: "user-2" })}
        users={USERS}
        onChanged={onChanged}
      />,
    );
    await user.selectOptions(screen.getByLabelText("Assignee of Buy milk"), "");

    const deleted = onlyRequest(
      fetchMock,
      "DELETE",
      "/api/v1/task-lists/list-1/tasks/task-1/assignee",
    );
    expect(deleted.body).toBeNull();
    expect(onChanged).toHaveBeenCalledWith(
      expect.objectContaining({
        assignee_id: null,
        updated_at: "2026-09-19T13:00:00Z",
      }),
    );
  });

  it("renders the API's own sentence when the assignee is not a user", async () => {
    const user = userEvent.setup();
    fetchMock.mockImplementation(
      serving([
        {
          method: "PUT",
          path: "/tasks/task-1/assignee",
          respond: () =>
            problemResponse(404, {
              type: "urn:taskmanager:problem:user_not_found",
              title: "Not Found",
              status: 404,
              detail: "No user exists with the requested identifier.",
              instance: "/api/v1/task-lists/list-1/tasks/task-1/assignee",
              code: "user_not_found",
            }),
        },
      ]),
    );

    render(
      <AssigneePicker task={aTask()} users={USERS} onChanged={vi.fn()} />,
    );
    await user.selectOptions(
      screen.getByLabelText("Assignee of Buy milk"),
      "user-1",
    );

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(
      "No user exists with the requested identifier.",
    );
    expect(alert).toHaveTextContent("user_not_found");
  });
});
