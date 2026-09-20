import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  TaskCollectionResponse,
  TaskListResponse,
  TaskResponse,
  UserSummaryResponse,
} from "../api/types";
import { clearToken, setToken } from "../auth/session";
import {
  type Handler,
  jsonBodyOf,
  jsonResponse,
  lastRequest,
  noContent,
  onlyRequest,
  problemResponse,
  requestsMatching,
  serving,
} from "../testing/http";
import TasksScreen from "./TasksScreen";

// UI-03 and the assignment half of UI-04. The "filtering" block is the one the
// phase exists for: a filtered response narrows the rows and does NOT move the
// completion bar, because the bar renders the response's own whole-list
// counters (ADR-009). It is the README quickstart's step 6 in component form.
//
// `fetch` is routed by URL rather than queued by call order: this screen reads
// two things on mount - its tasks and the user directory - and nothing orders
// those two effects, so a queue would hand one of them the other's body.

const LIST: TaskListResponse = {
  id: "list-1",
  owner_id: "owner-1",
  name: "Groceries",
  description: null,
  created_at: "2026-09-19T10:00:00Z",
  updated_at: "2026-09-19T10:00:00Z",
  total_tasks: 2,
  completed_tasks: 1,
  completion_percentage: 50,
};

const USERS: UserSummaryResponse[] = [
  { id: "user-1", full_name: "Ada Lovelace", email: "ada@example.com" },
  { id: "user-2", full_name: "Grace Hopper", email: "grace@example.com" },
];

function aTask(overrides: Partial<TaskResponse> = {}): TaskResponse {
  return {
    id: "task-1",
    task_list_id: "list-1",
    title: "Buy milk",
    description: "Semi-skimmed",
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

function aCollection(
  overrides: Partial<TaskCollectionResponse> = {},
): TaskCollectionResponse {
  return {
    items: [aTask()],
    total_tasks: 2,
    completed_tasks: 1,
    completion_percentage: 50,
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

function serve(handlers: Handler[]): void {
  fetchMock.mockImplementation(
    serving([
      { path: "/api/v1/users", respond: () => jsonResponse(200, USERS) },
      ...handlers,
    ]),
  );
}

function tasksRequests(): string[] {
  return requestsMatching(fetchMock, "GET", "/tasks").map((one) => one.url);
}

describe("reading a list", () => {
  it("asks for the whole list on mount and renders one row per task", async () => {
    serve([
      {
        path: "/task-lists/list-1/tasks",
        respond: () =>
          jsonResponse(
            200,
            aCollection({
              items: [aTask(), aTask({ id: "task-2", title: "Buy bread" })],
              total_tasks: 2,
              completed_tasks: 0,
              completion_percentage: 0,
            }),
          ),
      },
    ]);

    render(<TasksScreen list={LIST} onBack={vi.fn()} />);

    expect(await screen.findByText("Buy milk")).toBeInTheDocument();
    expect(screen.getByText("Buy bread")).toBeInTheDocument();
    expect(tasksRequests()).toEqual(["/api/v1/task-lists/list-1/tasks"]);
  });

  it("names the list it is showing and can go back", async () => {
    const user = userEvent.setup();
    const onBack = vi.fn();
    serve([
      {
        path: "/task-lists/list-1/tasks",
        respond: () => jsonResponse(200, aCollection()),
      },
    ]);

    render(<TasksScreen list={LIST} onBack={onBack} />);
    await screen.findByText("Buy milk");

    await user.click(screen.getByRole("button", { name: "Back to lists" }));

    expect(onBack).toHaveBeenCalledOnce();
  });

  it("reads the user directory once for the whole screen, not once per row", async () => {
    serve([
      {
        path: "/task-lists/list-1/tasks",
        respond: () =>
          jsonResponse(
            200,
            aCollection({
              items: [
                aTask(),
                aTask({ id: "task-2", title: "Buy bread" }),
                aTask({ id: "task-3", title: "Buy jam" }),
              ],
            }),
          ),
      },
    ]);

    render(<TasksScreen list={LIST} onBack={vi.fn()} />);
    await screen.findByText("Buy jam");

    expect(requestsMatching(fetchMock, "GET", "/api/v1/users")).toHaveLength(1);
  });
});

describe("filtering", () => {
  it("narrows the rows while the bar keeps describing the whole list (ADR-009)", async () => {
    const user = userEvent.setup();
    serve([
      {
        // The filtered answer: ONE item, and the three counters unchanged,
        // because the API computes them over the whole list.
        path: "/task-lists/list-1/tasks?priority=high",
        respond: () =>
          jsonResponse(200, aCollection({ items: [aTask({ priority: "high" })] })),
      },
      {
        path: "/task-lists/list-1/tasks",
        respond: () =>
          jsonResponse(
            200,
            aCollection({
              items: [
                aTask({ priority: "high" }),
                aTask({ id: "task-2", title: "Buy bread", status: "completed" }),
              ],
            }),
          ),
      },
    ]);

    render(<TasksScreen list={LIST} onBack={vi.fn()} />);
    await screen.findByText("Buy bread");

    await user.selectOptions(screen.getByLabelText("Priority"), "high");

    await waitFor(() => {
      expect(screen.queryByText("Buy bread")).not.toBeInTheDocument();
    });
    expect(screen.getByText("Buy milk")).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(1);

    // One row on screen, and the bar still says half the LIST is done.
    expect(screen.getByText("50%")).toBeInTheDocument();
    expect(screen.getByText("1 / 2")).toBeInTheDocument();

    expect(lastRequest(fetchMock).url).toBe(
      "/api/v1/task-lists/list-1/tasks?priority=high",
    );
  });

  it("drops a filtered answer that arrives after the unfiltered one that superseded it", async () => {
    const user = userEvent.setup();

    // The whole point of this test is an order `serving()` cannot produce: it
    // answers every handler synchronously, in call order, so the race below is
    // invisible to it. The filtered read is held open by hand and released only
    // AFTER the unfiltered read that superseded it has already rendered, which
    // is the real network's freedom - two requests, no guaranteed order between
    // their responses.
    let releaseTheFilteredRead = (): void => undefined;
    const filteredReadReleased = new Promise<void>((resolve) => {
      releaseTheFilteredRead = resolve;
    });

    const STALE = "STALE: the superseded filtered row";
    let unfilteredReads = 0;

    fetchMock.mockImplementation((url: unknown) => {
      const target = String(url);
      if (target.includes("/api/v1/users")) {
        return Promise.resolve(jsonResponse(200, USERS));
      }
      if (target.includes("status=in_progress")) {
        return filteredReadReleased.then(() =>
          jsonResponse(
            200,
            aCollection({
              items: [aTask({ id: "task-9", title: STALE })],
              total_tasks: 9,
              completed_tasks: 9,
              completion_percentage: 99,
            }),
          ),
        );
      }
      unfilteredReads += 1;
      return Promise.resolve(
        jsonResponse(
          200,
          aCollection({
            items:
              unfilteredReads === 1
                ? [aTask()]
                : [aTask(), aTask({ id: "task-2", title: "Buy bread" })],
          }),
        ),
      );
    });

    render(<TasksScreen list={LIST} onBack={vi.fn()} />);
    await screen.findByText("Buy milk");

    // Request one: filtered. It is now in flight and will not answer yet.
    await user.selectOptions(screen.getByLabelText("Status"), "in_progress");
    await waitFor(() => {
      expect(tasksRequests()).toContain(
        "/api/v1/task-lists/list-1/tasks?status=in_progress",
      );
    });

    // Request two: unfiltered, sent later and answered first.
    await user.selectOptions(screen.getByLabelText("Status"), "");
    expect(await screen.findByText("Buy bread")).toBeInTheDocument();

    // And only now does the OLDER request come back.
    await act(async () => {
      releaseTheFilteredRead();
      await filteredReadReleased;
    });

    // The second response's rows...
    expect(screen.getByText("Buy bread")).toBeInTheDocument();
    expect(screen.queryByText(STALE)).not.toBeInTheDocument();
    // ...and the second response's whole-list counters. These travel with every
    // response, so a stale body overwrites the bar as well as the rows.
    expect(screen.getByText("50%")).toBeInTheDocument();
    expect(screen.getByText("1 / 2")).toBeInTheDocument();
    expect(screen.queryByText("99%")).not.toBeInTheDocument();
  });

  it("sends the status filter and drops the parameter entirely when it is cleared", async () => {
    const user = userEvent.setup();
    serve([
      {
        path: "/task-lists/list-1/tasks",
        respond: () => jsonResponse(200, aCollection()),
      },
    ]);

    render(<TasksScreen list={LIST} onBack={vi.fn()} />);
    await screen.findByText("Buy milk");

    await user.selectOptions(screen.getByLabelText("Status"), "in_progress");
    await waitFor(() => {
      expect(lastRequest(fetchMock).url).toBe(
        "/api/v1/task-lists/list-1/tasks?status=in_progress",
      );
    });

    await user.selectOptions(screen.getByLabelText("Status"), "");
    await waitFor(() => {
      expect(lastRequest(fetchMock).url).toBe(
        "/api/v1/task-lists/list-1/tasks",
      );
    });
    // Not `?status=` - an empty string is a value, and the API would refuse it
    // as an invalid enum member rather than read it as "no filter".
    expect(lastRequest(fetchMock).url).not.toContain("status=");
  });
});

describe("creating a task", () => {
  it("posts the title, description and priority, defaulting the priority to the API's own default", async () => {
    const user = userEvent.setup();
    serve([
      {
        path: "/task-lists/list-1/tasks",
        times: 1,
        respond: () => jsonResponse(200, aCollection({ items: [] })),
      },
      {
        method: "POST",
        path: "/task-lists/list-1/tasks",
        respond: () => jsonResponse(201, aTask({ title: "Buy eggs" })),
      },
      {
        path: "/task-lists/list-1/tasks",
        respond: () =>
          jsonResponse(200, aCollection({ items: [aTask({ title: "Buy eggs" })] })),
      },
    ]);

    render(<TasksScreen list={LIST} onBack={vi.fn()} />);
    await screen.findByText("No tasks match this view.");

    await user.type(screen.getByLabelText("Title"), "Buy eggs");
    await user.type(screen.getByLabelText("Description"), "A dozen");
    await user.click(screen.getByRole("button", { name: "Add task" }));

    expect(await screen.findByText("Buy eggs")).toBeInTheDocument();

    const posted = onlyRequest(
      fetchMock,
      "POST",
      "/api/v1/task-lists/list-1/tasks",
    );
    expect(jsonBodyOf(posted)).toEqual({
      title: "Buy eggs",
      description: "A dozen",
      priority: "medium",
    });
  });
});

describe("editing a task", () => {
  it("patches the changed fields and never sends status through the general endpoint", async () => {
    const user = userEvent.setup();
    serve([
      {
        path: "/task-lists/list-1/tasks",
        times: 1,
        respond: () => jsonResponse(200, aCollection()),
      },
      {
        method: "PATCH",
        path: "/tasks/task-1",
        respond: () =>
          jsonResponse(200, aTask({ title: "Buy oat milk", priority: "high" })),
      },
      {
        path: "/task-lists/list-1/tasks",
        respond: () =>
          jsonResponse(
            200,
            aCollection({
              items: [aTask({ title: "Buy oat milk", priority: "high" })],
            }),
          ),
      },
    ]);

    render(<TasksScreen list={LIST} onBack={vi.fn()} />);
    await user.click(await screen.findByRole("button", { name: "Edit Buy milk" }));

    const title = screen.getByLabelText("New title");
    await user.clear(title);
    await user.type(title, "Buy oat milk");
    await user.selectOptions(screen.getByLabelText("New priority"), "high");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(await screen.findByText("Buy oat milk")).toBeInTheDocument();

    const patched = onlyRequest(
      fetchMock,
      "PATCH",
      "/api/v1/task-lists/list-1/tasks/task-1",
    );
    const body = jsonBodyOf(patched);
    expect(body).toEqual({ title: "Buy oat milk", priority: "high" });
    expect(Object.keys(Object(body))).not.toContain("status");
  });

  it("sends null, not an empty string, when the description is cleared", async () => {
    const user = userEvent.setup();
    serve([
      {
        path: "/task-lists/list-1/tasks",
        times: 1,
        respond: () => jsonResponse(200, aCollection()),
      },
      {
        method: "PATCH",
        path: "/tasks/task-1",
        respond: () => jsonResponse(200, aTask({ description: null })),
      },
      {
        path: "/task-lists/list-1/tasks",
        respond: () =>
          jsonResponse(
            200,
            aCollection({ items: [aTask({ description: null })] }),
          ),
      },
    ]);

    render(<TasksScreen list={LIST} onBack={vi.fn()} />);
    await user.click(
      await screen.findByRole("button", { name: "Edit Buy milk" }),
    );
    await user.clear(screen.getByLabelText("New description"));
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => {
      expect(screen.queryByText("Semi-skimmed")).not.toBeInTheDocument();
    });

    const patched = onlyRequest(
      fetchMock,
      "PATCH",
      "/api/v1/task-lists/list-1/tasks/task-1",
    );
    // `null` is the API's "clear this field" (the patch model reads the key out
    // of `model_fields_set`, so an explicit null is not the same as omitting
    // it). `""` is a value the UI never has to make the server interpret, and
    // `TaskResponse.description` is `string | null` - so `""` is a third
    // spelling of a two-valued field.
    expect(jsonBodyOf(patched)).toEqual({ description: null });
  });

  it("makes no request when nothing was changed, because an empty patch body is a 422", async () => {
    const user = userEvent.setup();
    serve([
      {
        path: "/task-lists/list-1/tasks",
        respond: () => jsonResponse(200, aCollection()),
      },
    ]);

    render(<TasksScreen list={LIST} onBack={vi.fn()} />);
    await user.click(await screen.findByRole("button", { name: "Edit Buy milk" }));
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(requestsMatching(fetchMock, "PATCH", "/tasks/task-1")).toEqual([]);
  });
});

describe("changing a status", () => {
  it("offers a completed task only the reopening move", async () => {
    serve([
      {
        path: "/task-lists/list-1/tasks",
        respond: () =>
          jsonResponse(
            200,
            aCollection({
              items: [
                aTask({
                  status: "completed",
                  completed_at: "2026-09-19T11:00:00Z",
                }),
              ],
            }),
          ),
      },
    ]);

    render(<TasksScreen list={LIST} onBack={vi.fn()} />);

    const control = await screen.findByLabelText("Status of Buy milk");
    expect(
      within(control).getByRole("option", { name: "In progress" }),
    ).toBeInTheDocument();
    expect(
      within(control).queryByRole("option", { name: "Pending" }),
    ).not.toBeInTheDocument();
  });

  it("uses the dedicated status endpoint and re-reads the counters it changed", async () => {
    const user = userEvent.setup();
    serve([
      {
        path: "/task-lists/list-1/tasks",
        times: 1,
        respond: () => jsonResponse(200, aCollection()),
      },
      {
        method: "PATCH",
        path: "/tasks/task-1/status",
        respond: () => jsonResponse(200, aTask({ status: "completed" })),
      },
      {
        path: "/task-lists/list-1/tasks",
        respond: () =>
          jsonResponse(
            200,
            aCollection({
              items: [aTask({ status: "completed" })],
              total_tasks: 2,
              completed_tasks: 2,
              completion_percentage: 100,
            }),
          ),
      },
    ]);

    render(<TasksScreen list={LIST} onBack={vi.fn()} />);
    await user.selectOptions(
      await screen.findByLabelText("Status of Buy milk"),
      "completed",
    );

    expect(await screen.findByText("100%")).toBeInTheDocument();

    const patched = onlyRequest(
      fetchMock,
      "PATCH",
      "/api/v1/task-lists/list-1/tasks/task-1/status",
    );
    expect(jsonBodyOf(patched)).toEqual({ status: "completed" });
  });

  it("renders the API's own sentence when it refuses the move anyway", async () => {
    const user = userEvent.setup();
    serve([
      {
        path: "/task-lists/list-1/tasks",
        respond: () => jsonResponse(200, aCollection()),
      },
      {
        method: "PATCH",
        path: "/tasks/task-1/status",
        respond: () =>
          problemResponse(409, {
            type: "urn:taskmanager:problem:invalid_status_transition",
            title: "Conflict",
            status: 409,
            detail: "A task cannot move from 'completed' to 'pending'.",
            instance: "/api/v1/task-lists/list-1/tasks/task-1/status",
            code: "invalid_status_transition",
            errors: { from: "completed", to: "pending" },
          }),
      },
    ]);

    render(<TasksScreen list={LIST} onBack={vi.fn()} />);
    await user.selectOptions(
      await screen.findByLabelText("Status of Buy milk"),
      "completed",
    );

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(
      "A task cannot move from 'completed' to 'pending'.",
    );
    expect(alert).toHaveTextContent("invalid_status_transition");
  });
});

describe("assigning a task", () => {
  it("replaces the one row the API answered, without re-reading the collection", async () => {
    const user = userEvent.setup();
    serve([
      {
        path: "/task-lists/list-1/tasks",
        respond: () => jsonResponse(200, aCollection()),
      },
      {
        method: "PUT",
        path: "/tasks/task-1/assignee",
        respond: () => jsonResponse(200, aTask({ assignee_id: "user-1" })),
      },
    ]);

    render(<TasksScreen list={LIST} onBack={vi.fn()} />);
    await user.selectOptions(
      await screen.findByLabelText("Assignee of Buy milk"),
      "user-1",
    );

    await waitFor(() => {
      expect(screen.getByLabelText("Assignee of Buy milk")).toHaveValue(
        "user-1",
      );
    });
    // Assignment cannot change completion, so the counters are left exactly as
    // the last collection read gave them - and that read is not repeated.
    expect(tasksRequests()).toEqual(["/api/v1/task-lists/list-1/tasks"]);
    expect(screen.getByText("50%")).toBeInTheDocument();
  });
});

describe("deleting a task", () => {
  it("asks first, deletes that id and re-reads the list", async () => {
    const user = userEvent.setup();
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    serve([
      {
        path: "/task-lists/list-1/tasks",
        times: 1,
        respond: () =>
          jsonResponse(
            200,
            aCollection({
              items: [aTask(), aTask({ id: "task-2", title: "Buy bread" })],
            }),
          ),
      },
      {
        method: "DELETE",
        path: "/tasks/task-2",
        respond: () => noContent(),
      },
      {
        path: "/task-lists/list-1/tasks",
        respond: () => jsonResponse(200, aCollection({ items: [aTask()] })),
      },
    ]);

    render(<TasksScreen list={LIST} onBack={vi.fn()} />);
    await user.click(
      await screen.findByRole("button", { name: "Delete Buy bread" }),
    );

    expect(String(confirm.mock.calls[0]?.[0])).toContain("Buy bread");
    await waitFor(() => {
      expect(screen.queryByText("Buy bread")).not.toBeInTheDocument();
    });

    const deleted = onlyRequest(
      fetchMock,
      "DELETE",
      "/api/v1/task-lists/list-1/tasks/task-2",
    );
    expect(deleted.url).toBe("/api/v1/task-lists/list-1/tasks/task-2");
  });
});
