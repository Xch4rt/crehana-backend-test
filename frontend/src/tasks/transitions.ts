import { ALLOWED_TRANSITIONS, type TaskStatus } from "../api/types";

// The moves the status control may offer, in lifecycle order.
//
// The table itself is NOT restated here. `ALLOWED_TRANSITIONS` in `api/types.ts`
// is this package's single transcription of
// `src/taskmanager/domain/value_objects/task_status.py` (ADR-097), and a second
// copy in this file would be a second thing to keep true - the exact defect a
// transcription already risks. What this module adds is deterministic ORDER: the
// Python side is a `frozenset`, which has none, and a control whose options
// reshuffle between renders is not a control.
//
// The honest limit, stated rather than hidden: this is still a COPY of a table
// that lives in Python, and nothing in either build compares the two. An
// over-permissive copy would not corrupt anything - the server owns the state
// machine, refuses the illegal move with a 409 `invalid_status_transition`, and
// TasksScreen renders that refusal's own sentence. That path is tested. What the
// copy buys is that a user is not offered a button whose only outcome is an
// error; what it costs is this paragraph.
//
// `completed -> pending` is the single forbidden move: work resumes before it is
// un-started, so reopening a completed task lands in `in_progress`.

export const STATUSES: readonly TaskStatus[] = [
  "pending",
  "in_progress",
  "completed",
];

export const STATUS_LABELS: Readonly<Record<TaskStatus, string>> = {
  pending: "Pending",
  in_progress: "In progress",
  completed: "Completed",
};

function movesFrom(from: TaskStatus): readonly TaskStatus[] {
  const allowed = ALLOWED_TRANSITIONS[from];
  return STATUSES.filter((to) => allowed.includes(to));
}

export const ALLOWED_MOVES: Readonly<Record<TaskStatus, readonly TaskStatus[]>> =
  {
    pending: movesFrom("pending"),
    in_progress: movesFrom("in_progress"),
    completed: movesFrom("completed"),
  };

export function allowedMovesFrom(status: TaskStatus): readonly TaskStatus[] {
  return ALLOWED_MOVES[status];
}
