import { getToken } from "../auth/session";
import { isProblem, messageFor, type Problem } from "./problem";
import type {
  TaskCollectionResponse,
  TaskCreateRequest,
  TaskFilters,
  TaskListCreateRequest,
  TaskListResponse,
  TaskListUpdateRequest,
  TaskResponse,
  TaskStatus,
  TaskUpdateRequest,
  TokenResponse,
  UserCreateRequest,
  UserResponse,
  UserSummaryResponse,
} from "./types";

// The single place this UI touches the network. Everything else imports a
// function from here, which is what makes "the UI never invents an error
// message" (D-07) and "the token is attached in one place" (D-06) checkable
// claims rather than conventions.
//
// A RELATIVE base path, and that is the whole of D-03/ADR-107: in the container
// nginx serves the SPA and proxies /api/ to api:8000 on the same origin, and in
// development the Vite dev server proxies the same prefix to localhost:8000.
// Neither the browser nor this file ever learns the API's address, so no
// Access-Control-Allow-* header is needed anywhere and src/taskmanager is
// untouched by the existence of this client.
export const API_BASE = "/api/v1";

const JSON_MEDIA_TYPE = "application/json";
const PROBLEM_MEDIA_TYPE = "application/problem+json";
const FORM_MEDIA_TYPE = "application/x-www-form-urlencoded";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly title: string;
  readonly detail: string;
  readonly errors: unknown;

  constructor(problem: Problem) {
    super(messageFor(problem));
    this.name = "ApiError";
    this.status = problem.status;
    this.code = problem.code;
    this.title = problem.title;
    this.detail = problem.detail;
    this.errors = problem.errors;
  }
}

// The ONE failure this UI words itself, and the reason it is allowed to: the
// API never answered, so there is no RFC 9457 body to render. Status 0 says
// "no HTTP status was received" rather than borrowing one that would look like
// the server's opinion.
function networkFailure(detail: string): ApiError {
  return new ApiError({
    type: "urn:taskmanager:problem:network",
    title: "The API could not be reached",
    status: 0,
    detail,
    instance: "",
    code: "network",
  });
}

let onUnauthorized: (() => void) | null = null;

// Registered once by App, so a 401 raised by ANY call ends the session and
// returns to the login screen - UI-05's second half. A module-level handler
// rather than a parameter on every call: a screen that forgot to pass it would
// leave the user looking at a dead page with a stale token.
export function setUnauthorizedHandler(handler: (() => void) | null): void {
  onUnauthorized = handler;
}

function authorizationHeader(): Record<string, string> {
  const token = getToken();
  return token === null ? {} : { Authorization: `Bearer ${token}` };
}

function mediaTypeOf(response: Response): string {
  const header = response.headers.get("content-type");
  return header === null ? "" : header.split(";")[0]?.trim() ?? "";
}

async function parsed(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return undefined;
  }
}

async function request<T>(
  method: string,
  path: string,
  init: { body?: BodyInit; contentType?: string } = {},
): Promise<T> {
  const headers: Record<string, string> = { ...authorizationHeader() };
  if (init.contentType !== undefined) {
    headers["Content-Type"] = init.contentType;
  }

  let response: Response;
  try {
    const options: RequestInit = { method, headers };
    if (init.body !== undefined) {
      options.body = init.body;
    }
    response = await fetch(`${API_BASE}${path}`, options);
  } catch {
    throw networkFailure(
      "The API did not answer. Is the stack running? `docker compose up`.",
    );
  }

  if (response.status === 401 && onUnauthorized !== null) {
    onUnauthorized();
  }

  if (!response.ok) {
    const body = await parsed(response);
    if (isProblem(body)) {
      throw new ApiError(body);
    }
    throw networkFailure(
      `The API answered ${String(response.status)} with a body this client ` +
        `could not read as ${PROBLEM_MEDIA_TYPE}.`,
    );
  }

  // 204 has no body at all, and calling .json() on it is an exception rather
  // than an empty object. Both DELETEs in this API answer 204.
  if (response.status === 204) {
    return undefined as T;
  }

  if (mediaTypeOf(response) !== JSON_MEDIA_TYPE) {
    throw networkFailure(
      `The API answered ${String(response.status)} as ` +
        `'${mediaTypeOf(response)}' where ${JSON_MEDIA_TYPE} was expected.`,
    );
  }

  const body = await parsed(response);
  if (body === undefined) {
    throw networkFailure("The API answered a body that is not valid JSON.");
  }
  return body as T;
}

function withJson<T>(
  method: string,
  path: string,
  body: unknown,
): Promise<T> {
  return request<T>(method, path, {
    body: JSON.stringify(body),
    contentType: JSON_MEDIA_TYPE,
  });
}

function query(filters: TaskFilters): string {
  const parameters = new URLSearchParams();
  if (filters.status !== undefined) {
    parameters.set("status", filters.status);
  }
  if (filters.priority !== undefined) {
    parameters.set("priority", filters.priority);
  }
  const rendered = parameters.toString();
  return rendered === "" ? "" : `?${rendered}`;
}

// --- auth -------------------------------------------------------------------

export function register(body: UserCreateRequest): Promise<UserResponse> {
  return withJson<UserResponse>("POST", "/auth/register", body);
}

// The one endpoint that is not JSON: FastAPI's OAuth2 password flow takes a
// form encoding, and its `username` field IS the email.
export function login(
  email: string,
  password: string,
): Promise<TokenResponse> {
  const form = new URLSearchParams({ username: email, password });
  return request<TokenResponse>("POST", "/auth/login", {
    body: form.toString(),
    contentType: FORM_MEDIA_TYPE,
  });
}

export function me(): Promise<UserResponse> {
  return request<UserResponse>("GET", "/auth/me");
}

// --- task lists -------------------------------------------------------------

// A bare array, not an envelope. The API has no pagination, so there is nothing
// to wrap it in and nothing for this UI to page through.
export function listTaskLists(): Promise<TaskListResponse[]> {
  return request<TaskListResponse[]>("GET", "/task-lists");
}

export function createTaskList(
  body: TaskListCreateRequest,
): Promise<TaskListResponse> {
  return withJson<TaskListResponse>("POST", "/task-lists", body);
}

export function getTaskList(listId: string): Promise<TaskListResponse> {
  return request<TaskListResponse>("GET", `/task-lists/${listId}`);
}

export function updateTaskList(
  listId: string,
  body: TaskListUpdateRequest,
): Promise<TaskListResponse> {
  return withJson<TaskListResponse>("PATCH", `/task-lists/${listId}`, body);
}

export function deleteTaskList(listId: string): Promise<void> {
  return request<void>("DELETE", `/task-lists/${listId}`);
}

// --- tasks ------------------------------------------------------------------

export function createTask(
  listId: string,
  body: TaskCreateRequest,
): Promise<TaskResponse> {
  return withJson<TaskResponse>("POST", `/task-lists/${listId}/tasks`, body);
}

export function listTasks(
  listId: string,
  filters: TaskFilters = {},
): Promise<TaskCollectionResponse> {
  return request<TaskCollectionResponse>(
    "GET",
    `/task-lists/${listId}/tasks${query(filters)}`,
  );
}

export function getTask(
  listId: string,
  taskId: string,
): Promise<TaskResponse> {
  return request<TaskResponse>("GET", `/task-lists/${listId}/tasks/${taskId}`);
}

export function updateTask(
  listId: string,
  taskId: string,
  body: TaskUpdateRequest,
): Promise<TaskResponse> {
  return withJson<TaskResponse>(
    "PATCH",
    `/task-lists/${listId}/tasks/${taskId}`,
    body,
  );
}

export function deleteTask(listId: string, taskId: string): Promise<void> {
  return request<void>("DELETE", `/task-lists/${listId}/tasks/${taskId}`);
}

// Its own endpoint, never a PATCH of the task body: a status change is a use
// case with a transition table behind it (ADR-097), and a refused move comes
// back as a 409 this client surfaces like any other refusal.
export function changeTaskStatus(
  listId: string,
  taskId: string,
  status: TaskStatus,
): Promise<TaskResponse> {
  return withJson<TaskResponse>(
    "PATCH",
    `/task-lists/${listId}/tasks/${taskId}/status`,
    { status },
  );
}

// --- users and assignment ---------------------------------------------------

export function listUsers(): Promise<UserSummaryResponse[]> {
  return request<UserSummaryResponse[]>("GET", "/users");
}

export function assignTask(
  listId: string,
  taskId: string,
  assigneeId: string,
): Promise<TaskResponse> {
  return withJson<TaskResponse>(
    "PUT",
    `/task-lists/${listId}/tasks/${taskId}/assignee`,
    { assignee_id: assigneeId },
  );
}

// 200 with the updated task, NOT 204: unassigning answers the resource it
// changed, unlike the two deletes above.
export function unassignTask(
  listId: string,
  taskId: string,
): Promise<TaskResponse> {
  return request<TaskResponse>(
    "DELETE",
    `/task-lists/${listId}/tasks/${taskId}/assignee`,
  );
}

export function listAssignedToMe(): Promise<TaskResponse[]> {
  return request<TaskResponse[]>("GET", "/tasks/assigned-to-me");
}
