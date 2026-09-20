// The API contract, hand-written from the live OpenAPI document. Every field
// name here was read from `/openapi.json`, never guessed from a router.
//
// Nullable members are `string | null` and not `string | undefined`, because
// that is what the API actually sends: the response models emit the key with a
// null value rather than omitting it.
//
// Generating this file from the OpenAPI document is deliberately out of scope -
// it would add a codegen step and a second lockfile-shaped artifact to keep
// true, for a contract that is one screen long. The README's "Pending" section
// names it as what I would do next.

export type TaskStatus = "pending" | "in_progress" | "completed";

export type TaskPriority = "low" | "medium" | "high";

// ADR-097. `completed` may only go back to `in_progress`; a request for the
// status a task already has is a 200 no-op, not a refusal.
export const ALLOWED_TRANSITIONS: Readonly<Record<TaskStatus, TaskStatus[]>> = {
  pending: ["in_progress", "completed"],
  in_progress: ["pending", "completed"],
  completed: ["in_progress"],
};

export interface UserResponse {
  id: string;
  email: string;
  full_name: string;
  created_at: string;
}

// Not a UserResponse minus a field: the collection endpoint publishes its own
// shape, and it carries no `created_at`.
export interface UserSummaryResponse {
  id: string;
  full_name: string;
  email: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface TaskListResponse {
  id: string;
  owner_id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
  total_tasks: number;
  completed_tasks: number;
  completion_percentage: number;
}

export interface TaskResponse {
  id: string;
  task_list_id: string;
  title: string;
  description: string | null;
  status: TaskStatus;
  priority: TaskPriority;
  created_at: string;
  updated_at: string;
  due_date: string | null;
  completed_at: string | null;
  assignee_id: string | null;
}

// The three counters describe the WHOLE list, never the filtered `items`
// (ADR-009). Nothing in this UI may recompute them from `items.length`.
export interface TaskCollectionResponse {
  items: TaskResponse[];
  total_tasks: number;
  completed_tasks: number;
  completion_percentage: number;
}

export interface UserCreateRequest {
  email: string;
  full_name: string;
  password: string;
}

export interface TaskListCreateRequest {
  name: string;
  description?: string | null;
}

// Every member optional, and an entirely empty body is a 422 from the API - the
// caller decides what it is changing.
export interface TaskListUpdateRequest {
  name?: string;
  description?: string | null;
}

export interface TaskCreateRequest {
  title: string;
  description?: string | null;
  priority?: TaskPriority;
  due_date?: string | null;
}

export interface TaskUpdateRequest {
  title?: string;
  description?: string | null;
  priority?: TaskPriority;
  due_date?: string | null;
}

export interface TaskFilters {
  status?: TaskStatus;
  priority?: TaskPriority;
}
