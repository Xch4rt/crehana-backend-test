import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { TaskListResponse } from "../api/types";
import { clearToken, setToken } from "../auth/session";
import {
  jsonBodyOf,
  jsonResponse,
  noContent,
  onlyRequest,
  problemResponse,
  requestsMatching,
} from "../testing/http";
import ListsScreen from "./ListsScreen";

// UI-02, at the level a reviewer cares about: what the screen asks the API for,
// and what it does with the answer. `fetch` is stubbed - the client underneath
// is real, so the URL, the verb and the JSON body asserted here are the ones
// that would go on the wire.

function aList(overrides: Partial<TaskListResponse> = {}): TaskListResponse {
  return {
    id: "list-1",
    owner_id: "owner-1",
    name: "Groceries",
    description: "Weekly shop",
    created_at: "2026-09-19T10:00:00Z",
    updated_at: "2026-09-19T10:00:00Z",
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

describe("the list index", () => {
  it("reads the caller's lists once on mount and renders each one", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(200, [
        aList(),
        aList({
          id: "list-2",
          name: "Reading",
          total_tasks: 4,
          completed_tasks: 1,
          completion_percentage: 25,
        }),
      ]),
    );

    render(<ListsScreen onOpen={vi.fn()} />);

    expect(
      await screen.findByRole("button", { name: "Groceries" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reading" })).toBeInTheDocument();
    expect(screen.getByText("50%")).toBeInTheDocument();
    expect(screen.getByText("25%")).toBeInTheDocument();

    const read = onlyRequest(fetchMock, "GET", "/api/v1/task-lists");
    expect(read.url).toBe("/api/v1/task-lists");
  });

  it("says so explicitly when there are no lists yet", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, []));

    render(<ListsScreen onOpen={vi.fn()} />);

    expect(
      await screen.findByText("No lists yet. Create your first one below."),
    ).toBeInTheDocument();
  });

  it("hands the whole list to its caller when the name is clicked", async () => {
    const user = userEvent.setup();
    const onOpen = vi.fn();
    fetchMock.mockResolvedValueOnce(jsonResponse(200, [aList()]));

    render(<ListsScreen onOpen={onOpen} />);

    await user.click(await screen.findByRole("button", { name: "Groceries" }));

    expect(onOpen).toHaveBeenCalledWith(
      expect.objectContaining({ id: "list-1", name: "Groceries" }),
    );
  });
});

describe("creating a list", () => {
  it("posts the name and description and shows the list the API answered", async () => {
    const user = userEvent.setup();
    fetchMock
      .mockResolvedValueOnce(jsonResponse(200, []))
      .mockResolvedValueOnce(
        jsonResponse(
          201,
          aList({
            id: "list-9",
            name: "Sprint 12",
            description: "The work",
            total_tasks: 0,
            completed_tasks: 0,
            completion_percentage: 0,
          }),
        ),
      );

    render(<ListsScreen onOpen={vi.fn()} />);
    await screen.findByText("No lists yet. Create your first one below.");

    await user.type(screen.getByLabelText("List name"), "Sprint 12");
    await user.type(screen.getByLabelText("Description"), "The work");
    await user.click(screen.getByRole("button", { name: "Create list" }));

    expect(
      await screen.findByRole("button", { name: "Sprint 12" }),
    ).toBeInTheDocument();

    const posted = onlyRequest(fetchMock, "POST", "/api/v1/task-lists");
    expect(jsonBodyOf(posted)).toEqual({
      name: "Sprint 12",
      description: "The work",
    });
    // The new row came from the response, not from a second read of the
    // collection: the API already answered the resource it created.
    expect(requestsMatching(fetchMock, "GET", "/api/v1/task-lists")).toHaveLength(
      1,
    );
  });

  it("renders the API's own duplicate-name sentence", async () => {
    const user = userEvent.setup();
    fetchMock
      .mockResolvedValueOnce(jsonResponse(200, [aList()]))
      .mockResolvedValueOnce(
        problemResponse(409, {
          type: "urn:taskmanager:problem:duplicate_task_list_name",
          title: "Conflict",
          status: 409,
          detail: "You already have a task list named 'Groceries'.",
          instance: "/api/v1/task-lists",
          code: "duplicate_task_list_name",
        }),
      );

    render(<ListsScreen onOpen={vi.fn()} />);
    await screen.findByRole("button", { name: "Groceries" });

    await user.type(screen.getByLabelText("List name"), "Groceries");
    await user.click(screen.getByRole("button", { name: "Create list" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(
      "You already have a task list named 'Groceries'.",
    );
    expect(alert).toHaveTextContent("duplicate_task_list_name");
  });
});

describe("renaming a list", () => {
  it("patches the name alone and shows the renamed list", async () => {
    const user = userEvent.setup();
    fetchMock
      .mockResolvedValueOnce(jsonResponse(200, [aList()]))
      .mockResolvedValueOnce(
        jsonResponse(200, aList({ name: "Groceries (weekly)" })),
      );

    render(<ListsScreen onOpen={vi.fn()} />);
    await user.click(
      await screen.findByRole("button", { name: "Rename Groceries" }),
    );

    const input = screen.getByLabelText("New name");
    await user.clear(input);
    await user.type(input, "Groceries (weekly)");
    await user.click(screen.getByRole("button", { name: "Save new name" }));

    expect(
      await screen.findByRole("button", { name: "Groceries (weekly)" }),
    ).toBeInTheDocument();

    const patched = onlyRequest(fetchMock, "PATCH", "/api/v1/task-lists/list-1");
    expect(jsonBodyOf(patched)).toEqual({ name: "Groceries (weekly)" });
  });
});

describe("deleting a list", () => {
  it("asks first, then deletes that id and drops the row", async () => {
    const user = userEvent.setup();
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    fetchMock
      .mockResolvedValueOnce(
        jsonResponse(200, [aList(), aList({ id: "list-2", name: "Reading" })]),
      )
      .mockResolvedValueOnce(noContent());

    render(<ListsScreen onOpen={vi.fn()} />);
    await user.click(
      await screen.findByRole("button", { name: "Delete Reading" }),
    );

    expect(confirm).toHaveBeenCalledOnce();
    expect(String(confirm.mock.calls[0]?.[0])).toContain("Reading");

    await waitFor(() => {
      expect(
        screen.queryByRole("button", { name: "Reading" }),
      ).not.toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: "Groceries" })).toBeInTheDocument();

    const deleted = onlyRequest(
      fetchMock,
      "DELETE",
      "/api/v1/task-lists/list-2",
    );
    expect(deleted.url).toBe("/api/v1/task-lists/list-2");
  });

  it("makes no request at all when the question is declined", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(false);
    fetchMock.mockResolvedValueOnce(jsonResponse(200, [aList()]));

    render(<ListsScreen onOpen={vi.fn()} />);
    await user.click(
      await screen.findByRole("button", { name: "Delete Groceries" }),
    );

    expect(requestsMatching(fetchMock, "DELETE", "/api/v1/task-lists")).toEqual(
      [],
    );
    const row = screen.getByRole("listitem");
    expect(within(row).getByRole("button", { name: "Groceries" })).toBeInTheDocument();
  });
});
