import { useState } from "react";

import { ApiError, assignTask, unassignTask } from "../api/client";
import type { TaskResponse, UserSummaryResponse } from "../api/types";
import ErrorBanner from "../components/ErrorBanner";

// UI-04's control, one per row.
//
// The directory is a PROP, not a fetch. `GET /api/v1/users` has no pagination
// and returns every account there is (ADR-068), so a component that read it on
// mount would read the whole directory once per task row - twenty rows, twenty
// identical unbounded responses. TasksScreen reads it once and passes it down.
//
// Unassigning answers **200 with the updated task**, not the 204 the two
// deletes answer, so `onChanged` is handed the response body. Assuming an empty
// body here would leave the row showing whatever it held before.
//
// Nothing in this control implies a restriction the API does not have: any
// registered user may be assigned any task the caller can see (ADR-069), and
// the select offers exactly the directory the API published.

const UNASSIGNED = "";

export default function AssigneePicker({
  task,
  users,
  onChanged,
}: {
  task: TaskResponse;
  users: UserSummaryResponse[];
  onChanged: (task: TaskResponse) => void;
}) {
  const [error, setError] = useState<ApiError | null>(null);
  const [inFlight, setInFlight] = useState(false);

  const current = task.assignee_id;
  const known = users.some((one) => one.id === current);

  async function change(value: string): Promise<void> {
    setError(null);
    setInFlight(true);
    try {
      const updated =
        value === UNASSIGNED
          ? await unassignTask(task.task_list_id, task.id)
          : await assignTask(task.task_list_id, task.id, value);
      onChanged(updated);
    } catch (failure: unknown) {
      if (failure instanceof ApiError) {
        setError(failure);
      } else {
        throw failure;
      }
    } finally {
      setInFlight(false);
    }
  }

  return (
    <div className="field inline-field">
      <label htmlFor={`assignee-${task.id}`}>Assignee of {task.title}</label>
      <select
        id={`assignee-${task.id}`}
        value={current ?? UNASSIGNED}
        disabled={inFlight}
        onChange={(event) => {
          void change(event.target.value);
        }}
      >
        <option value={UNASSIGNED}>Unassigned</option>
        {users.map((one) => (
          <option key={one.id} value={one.id}>
            {one.full_name} ({one.email})
          </option>
        ))}
        {/* An assignee the directory does not contain is shown as the id the
            API sent. Falling back to "Unassigned" would state something false
            about the task - the one thing this UI must never do. */}
        {current !== null && !known && (
          <option value={current}>{current} (not in the directory)</option>
        )}
      </select>
      <ErrorBanner error={error} />
    </div>
  );
}
