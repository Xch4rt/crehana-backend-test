import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  changeTaskStatus,
  createTask,
  deleteTask,
  listTasks,
  listUsers,
  updateTask,
} from "../api/client";
import type {
  TaskCollectionResponse,
  TaskListResponse,
  TaskPriority,
  TaskResponse,
  TaskStatus,
  TaskUpdateRequest,
  UserSummaryResponse,
} from "../api/types";
import CompletionBar from "../components/CompletionBar";
import ErrorBanner from "../components/ErrorBanner";
import Field from "../components/Field";
import AssigneePicker from "./AssigneePicker";
import { STATUSES, STATUS_LABELS, allowedMovesFrom } from "./transitions";

// UI-03: one list, its tasks, the filters, and the status control.
//
// Two rules hold this screen together and both are easy to break by "tidying":
//
//   1. The completion bar is fed the RESPONSE's three counters, never anything
//      derived from `items` (ADR-009). The API computes them over the whole list
//      with one SQL aggregate no matter what filter was sent, so a filtered view
//      still reports the list's real progress. Deriving the bar from the rows on
//      screen would make the UI contradict the API - see the filter test.
//   2. A status change goes through its own endpoint and nowhere else. The
//      general PATCH accepts title, description, priority and due_date, and a
//      `status` member there is a 422: the state machine has a transition table
//      behind it (ADR-097) and is not a field you assign.

const PRIORITIES: readonly TaskPriority[] = ["low", "medium", "high"];

const PRIORITY_LABELS: Readonly<Record<TaskPriority, string>> = {
  low: "Low",
  medium: "Medium",
  high: "High",
};

// Narrowing a <select>'s string back to the union, by looking it up rather than
// asserting it. "" is the "Any" option and means the parameter is omitted
// entirely - not sent empty, which the API would refuse as an invalid enum.
function asStatus(value: string): TaskStatus | "" {
  return STATUSES.find((status) => status === value) ?? "";
}

function asPriority(value: string): TaskPriority | "" {
  return PRIORITIES.find((priority) => priority === value) ?? "";
}

export default function TasksScreen({
  list,
  onBack,
}: {
  list: TaskListResponse;
  onBack: () => void;
}) {
  const [collection, setCollection] = useState<TaskCollectionResponse | null>(
    null,
  );
  const [status, setStatus] = useState<TaskStatus | "">("");
  const [priority, setPriority] = useState<TaskPriority | "">("");
  const [error, setError] = useState<ApiError | null>(null);
  const [inFlight, setInFlight] = useState(false);
  const [users, setUsers] = useState<UserSummaryResponse[]>([]);

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [newPriority, setNewPriority] = useState<TaskPriority>("medium");

  const [editing, setEditing] = useState<TaskResponse | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editPriority, setEditPriority] = useState<TaskPriority>("medium");

  // A promise chain rather than `async`/`await` on purpose: every setState here
  // has to sit inside a callback, because `react-hooks/set-state-in-effect`
  // reads an awaited setState in a function the effect calls as a synchronous
  // one and refuses it. The chain is also what the rule documents as correct -
  // React is being told about the answer when it arrives, not during the effect.
  const load = useCallback(
    (): Promise<void> =>
      listTasks(list.id, {
        ...(status === "" ? {} : { status }),
        ...(priority === "" ? {} : { priority }),
      })
        .then((loaded) => {
          setCollection(loaded);
        })
        .catch((failure: unknown) => {
          if (failure instanceof ApiError) {
            setError(failure);
          }
        }),
    [list.id, status, priority],
  );

  useEffect(() => {
    void load();
  }, [load]);

  // ONCE for the screen, not once per row: the directory has no pagination and
  // answers every account there is, so a fetch inside AssigneePicker would
  // multiply it by the number of tasks.
  useEffect(() => {
    let live = true;
    listUsers()
      .then((loaded) => {
        if (live) {
          setUsers(loaded);
        }
      })
      .catch((failure: unknown) => {
        if (live && failure instanceof ApiError) {
          setError(failure);
        }
      });
    return () => {
      live = false;
    };
  }, []);

  // An assignment changes ONE task and cannot change completion, so the row is
  // replaced from the response body and the three counters are left exactly as
  // the last collection read gave them. Re-reading the collection here would be
  // a request that can only return the same numbers.
  function replace(updated: TaskResponse): void {
    setCollection((current) =>
      current === null
        ? current
        : {
            ...current,
            items: current.items.map((one) =>
              one.id === updated.id ? updated : one,
            ),
          },
    );
  }

  function fail(failure: unknown): void {
    if (failure instanceof ApiError) {
      setError(failure);
      return;
    }
    throw failure;
  }

  async function add(event: React.FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setError(null);
    setInFlight(true);
    try {
      await createTask(list.id, {
        title,
        ...(description === "" ? {} : { description }),
        priority: newPriority,
      });
      setTitle("");
      setDescription("");
      setNewPriority("medium");
      // A new task moves `total_tasks`, so the counters are re-read rather
      // than adjusted here. The API owns them.
      await load();
    } catch (failure: unknown) {
      fail(failure);
    } finally {
      setInFlight(false);
    }
  }

  function startEditing(task: TaskResponse): void {
    setEditing(task);
    setEditTitle(task.title);
    setEditDescription(task.description ?? "");
    setEditPriority(task.priority);
    setError(null);
  }

  async function save(
    event: React.FormEvent<HTMLFormElement>,
    task: TaskResponse,
  ): Promise<void> {
    event.preventDefault();
    // Only what actually changed, and NEVER `status` - that is the dedicated
    // endpoint's business. An entirely empty body is a 422, so an edit that
    // changed nothing makes no request at all rather than asking the API to
    // refuse it.
    const changes: TaskUpdateRequest = {};
    if (editTitle !== task.title) {
      changes.title = editTitle;
    }
    if (editDescription !== (task.description ?? "")) {
      changes.description = editDescription;
    }
    if (editPriority !== task.priority) {
      changes.priority = editPriority;
    }
    if (Object.keys(changes).length === 0) {
      setEditing(null);
      return;
    }

    setError(null);
    setInFlight(true);
    try {
      await updateTask(list.id, task.id, changes);
      setEditing(null);
      // A priority change can move a task in or out of the current filter, so
      // the collection is re-read rather than patched in place.
      await load();
    } catch (failure: unknown) {
      fail(failure);
    } finally {
      setInFlight(false);
    }
  }

  async function move(task: TaskResponse, next: TaskStatus): Promise<void> {
    setError(null);
    setInFlight(true);
    try {
      await changeTaskStatus(list.id, task.id, next);
      // This is the one mutation that MOVES the counters, so it re-reads them.
      await load();
    } catch (failure: unknown) {
      fail(failure);
    } finally {
      setInFlight(false);
    }
  }

  async function remove(task: TaskResponse): Promise<void> {
    if (!window.confirm(`Delete the task "${task.title}"?`)) {
      return;
    }
    setError(null);
    setInFlight(true);
    try {
      await deleteTask(list.id, task.id);
      await load();
    } catch (failure: unknown) {
      fail(failure);
    } finally {
      setInFlight(false);
    }
  }

  return (
    <section>
      <div className="card-head">
        <h2>{list.name}</h2>
        <button type="button" onClick={onBack}>
          Back to lists
        </button>
      </div>

      <ErrorBanner error={error} />

      {collection !== null && (
        // The response's own counters, whatever filter produced this response.
        <CompletionBar
          total={collection.total_tasks}
          completed={collection.completed_tasks}
          percentage={collection.completion_percentage}
        />
      )}

      <div className="filters">
        <div className="field">
          <label htmlFor="filter_status">Status</label>
          <select
            id="filter_status"
            value={status}
            onChange={(event) => {
              setStatus(asStatus(event.target.value));
            }}
          >
            <option value="">Any</option>
            {STATUSES.map((one) => (
              <option key={one} value={one}>
                {STATUS_LABELS[one]}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="filter_priority">Priority</label>
          <select
            id="filter_priority"
            value={priority}
            onChange={(event) => {
              setPriority(asPriority(event.target.value));
            }}
          >
            <option value="">Any</option>
            {PRIORITIES.map((one) => (
              <option key={one} value={one}>
                {PRIORITY_LABELS[one]}
              </option>
            ))}
          </select>
        </div>
      </div>

      {collection === null ? (
        <p className="muted">Loading tasks…</p>
      ) : collection.items.length === 0 ? (
        <p className="empty">No tasks match this view.</p>
      ) : (
        <ul className="cards">
          {collection.items.map((task) => (
            <li key={task.id} className="panel card">
              <div className="card-head">
                <span className="title">{task.title}</span>
                <div className="row-actions">
                  <button
                    type="button"
                    aria-label={`Edit ${task.title}`}
                    disabled={inFlight}
                    onClick={() => {
                      startEditing(task);
                    }}
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    aria-label={`Delete ${task.title}`}
                    disabled={inFlight}
                    onClick={() => {
                      void remove(task);
                    }}
                  >
                    Delete
                  </button>
                </div>
              </div>

              {task.description !== null && (
                <p className="muted">{task.description}</p>
              )}

              <p className="meta">
                <span className={`badge priority-${task.priority}`}>
                  {PRIORITY_LABELS[task.priority]}
                </span>
                <span className={`badge status-${task.status}`}>
                  {STATUS_LABELS[task.status]}
                </span>
                {task.due_date !== null && (
                  <span className="muted">Due {task.due_date}</span>
                )}
              </p>

              <div className="field inline-field">
                <label htmlFor={`status-${task.id}`}>
                  Status of {task.title}
                </label>
                <select
                  id={`status-${task.id}`}
                  value={task.status}
                  disabled={inFlight}
                  onChange={(event) => {
                    const next = asStatus(event.target.value);
                    if (next !== "") {
                      void move(task, next);
                    }
                  }}
                >
                  {/* The current status, shown and unselectable: it is where
                      the task is, not somewhere it can go. */}
                  <option value={task.status} disabled>
                    {STATUS_LABELS[task.status]}
                  </option>
                  {allowedMovesFrom(task.status).map((next) => (
                    <option key={next} value={next}>
                      {STATUS_LABELS[next]}
                    </option>
                  ))}
                </select>
              </div>

              <AssigneePicker
                task={task}
                users={users}
                onChanged={replace}
              />

              {editing?.id === task.id && (
                <form
                  className="inline-form"
                  onSubmit={(event) => {
                    void save(event, task);
                  }}
                >
                  <Field
                    id="edit_title"
                    label="New title"
                    value={editTitle}
                    required
                    onChange={setEditTitle}
                  />
                  <Field
                    id="edit_description"
                    label="New description"
                    value={editDescription}
                    onChange={setEditDescription}
                  />
                  <div className="field">
                    <label htmlFor="edit_priority">New priority</label>
                    <select
                      id="edit_priority"
                      value={editPriority}
                      onChange={(event) => {
                        const chosen = asPriority(event.target.value);
                        if (chosen !== "") {
                          setEditPriority(chosen);
                        }
                      }}
                    >
                      {PRIORITIES.map((one) => (
                        <option key={one} value={one}>
                          {PRIORITY_LABELS[one]}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="row-actions">
                    <button type="submit" disabled={inFlight}>
                      Save changes
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setEditing(null);
                      }}
                    >
                      Cancel
                    </button>
                  </div>
                </form>
              )}
            </li>
          ))}
        </ul>
      )}

      <form
        className="panel"
        onSubmit={(event) => {
          void add(event);
        }}
      >
        <h3>New task</h3>
        <Field
          id="task_title"
          label="Title"
          value={title}
          required
          onChange={setTitle}
        />
        <Field
          id="task_description"
          label="Description"
          value={description}
          onChange={setDescription}
        />
        <div className="field">
          <label htmlFor="task_priority">Priority of the new task</label>
          <select
            id="task_priority"
            value={newPriority}
            onChange={(event) => {
              const chosen = asPriority(event.target.value);
              if (chosen !== "") {
                setNewPriority(chosen);
              }
            }}
          >
            {PRIORITIES.map((one) => (
              <option key={one} value={one}>
                {PRIORITY_LABELS[one]}
              </option>
            ))}
          </select>
        </div>
        <button type="submit" disabled={inFlight}>
          Add task
        </button>
      </form>
    </section>
  );
}
