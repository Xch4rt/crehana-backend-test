import { useEffect, useState } from "react";

import { ApiError, listAssignedToMe } from "../api/client";
import type { TaskResponse } from "../api/types";
import ErrorBanner from "../components/ErrorBanner";
import { STATUS_LABELS } from "../tasks/transitions";

// UI-04's other half: every task assigned to the caller, across every list.
//
// There is deliberately NO completion bar here. This endpoint answers a bare
// `TaskResponse[]` with no counters at all, so any percentage on this screen
// could only be one the UI invented - the same mistake ADR-009 forbids on the
// tasks screen, pointing the other way. The row shows the list id it belongs
// to; opening that list from here would need a lookup the API does not offer
// in this response, and inventing a name for it would be the same kind of lie.

const PRIORITY_LABELS: Readonly<Record<TaskResponse["priority"], string>> = {
  low: "Low",
  medium: "Medium",
  high: "High",
};

export default function AssignedScreen({ onBack }: { onBack: () => void }) {
  const [tasks, setTasks] = useState<TaskResponse[] | null>(null);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    let live = true;
    listAssignedToMe()
      .then((loaded) => {
        if (live) {
          setTasks(loaded);
        }
      })
      .catch((failure: unknown) => {
        if (live && failure instanceof ApiError) {
          setError(failure);
          setTasks([]);
        }
      });
    return () => {
      live = false;
    };
  }, []);

  return (
    <section>
      <div className="card-head">
        <h2>Assigned to me</h2>
        <button type="button" onClick={onBack}>
          Back to lists
        </button>
      </div>

      <ErrorBanner error={error} />

      {tasks === null ? (
        <p className="muted">Loading your assigned tasks…</p>
      ) : tasks.length === 0 ? (
        <p className="empty">Nothing is assigned to you.</p>
      ) : (
        <ul className="cards">
          {tasks.map((task) => (
            <li key={task.id} className="panel card">
              <span className="title">{task.title}</span>
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
                <span className="muted">In list {task.task_list_id}</span>
              </p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
