import { useEffect, useState } from "react";

import {
  ApiError,
  createTaskList,
  deleteTaskList,
  listTaskLists,
  updateTaskList,
} from "../api/client";
import type { TaskListResponse } from "../api/types";
import CompletionBar from "../components/CompletionBar";
import ErrorBanner from "../components/ErrorBanner";
import Field from "../components/Field";

// UI-02. Every refusal on this screen is the API's own sentence through
// ErrorBanner (D-07); nothing here words a failure the API answered.
//
// `lists === null` means "not loaded yet" and is why the empty state is a
// separate branch: an empty array is a fact about the account, and saying "no
// lists yet" while the request is still in flight would state it too early.

export default function ListsScreen({
  onOpen,
}: {
  onOpen: (list: TaskListResponse) => void;
}) {
  const [lists, setLists] = useState<TaskListResponse[] | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [inFlight, setInFlight] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");

  useEffect(() => {
    let live = true;
    listTaskLists()
      .then((loaded) => {
        if (live) {
          setLists(loaded);
        }
      })
      .catch((failure: unknown) => {
        if (live && failure instanceof ApiError) {
          setError(failure);
          setLists([]);
        }
      });
    return () => {
      live = false;
    };
  }, []);

  function fail(failure: unknown): void {
    if (failure instanceof ApiError) {
      setError(failure);
      return;
    }
    throw failure;
  }

  async function create(event: React.FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setError(null);
    setInFlight(true);
    try {
      // The API answered the resource it created, so the new row is that
      // response - not a second read of the collection, and not a row this
      // component assembled from the form it just submitted.
      const created = await createTaskList({
        name,
        ...(description === "" ? {} : { description }),
      });
      setLists((current) => [...(current ?? []), created]);
      setName("");
      setDescription("");
    } catch (failure: unknown) {
      fail(failure);
    } finally {
      setInFlight(false);
    }
  }

  async function rename(
    event: React.FormEvent<HTMLFormElement>,
    list: TaskListResponse,
  ): Promise<void> {
    event.preventDefault();
    setError(null);
    setInFlight(true);
    try {
      const renamed = await updateTaskList(list.id, { name: renameValue });
      setLists((current) =>
        (current ?? []).map((one) => (one.id === renamed.id ? renamed : one)),
      );
      setRenamingId(null);
    } catch (failure: unknown) {
      fail(failure);
    } finally {
      setInFlight(false);
    }
  }

  async function remove(list: TaskListResponse): Promise<void> {
    // The smallest honest confirmation, and it names the list rather than
    // asking "are you sure?" about nothing in particular. A dialog component
    // would be a dependency and a focus-trap to get right for one question
    // (D-05).
    if (
      !window.confirm(
        `Delete the list "${list.name}" and every task in it? This cannot be undone.`,
      )
    ) {
      return;
    }
    setError(null);
    setInFlight(true);
    try {
      await deleteTaskList(list.id);
      setLists((current) => (current ?? []).filter((one) => one.id !== list.id));
    } catch (failure: unknown) {
      fail(failure);
    } finally {
      setInFlight(false);
    }
  }

  return (
    <section>
      <h2>My task lists</h2>
      <ErrorBanner error={error} />

      {lists === null ? (
        <p className="muted">Loading your lists…</p>
      ) : lists.length === 0 ? (
        <p className="empty">No lists yet. Create your first one below.</p>
      ) : (
        <ul className="cards">
          {lists.map((list) => (
            <li key={list.id} className="panel card">
              <div className="card-head">
                <button
                  type="button"
                  className="link title"
                  onClick={() => {
                    onOpen(list);
                  }}
                >
                  {list.name}
                </button>
                <div className="row-actions">
                  <button
                    type="button"
                    aria-label={`Rename ${list.name}`}
                    disabled={inFlight}
                    onClick={() => {
                      setRenamingId(list.id);
                      setRenameValue(list.name);
                      setError(null);
                    }}
                  >
                    Rename
                  </button>
                  <button
                    type="button"
                    aria-label={`Delete ${list.name}`}
                    disabled={inFlight}
                    onClick={() => {
                      void remove(list);
                    }}
                  >
                    Delete
                  </button>
                </div>
              </div>

              {list.description !== null && (
                <p className="muted">{list.description}</p>
              )}

              <CompletionBar
                total={list.total_tasks}
                completed={list.completed_tasks}
                percentage={list.completion_percentage}
              />

              {renamingId === list.id && (
                <form
                  className="inline-form"
                  onSubmit={(event) => {
                    void rename(event, list);
                  }}
                >
                  <Field
                    id="rename"
                    label="New name"
                    value={renameValue}
                    required
                    onChange={setRenameValue}
                  />
                  <div className="row-actions">
                    <button
                      type="submit"
                      aria-label="Save new name"
                      disabled={inFlight}
                    >
                      Save
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setRenamingId(null);
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
          void create(event);
        }}
      >
        <h3>New list</h3>
        <Field
          id="list_name"
          label="List name"
          value={name}
          required
          onChange={setName}
        />
        <Field
          id="list_description"
          label="Description"
          value={description}
          onChange={setDescription}
        />
        <button type="submit" disabled={inFlight}>
          Create list
        </button>
      </form>
    </section>
  );
}
