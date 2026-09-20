// RFC 9457, the shape every refusal this API makes arrives in, and the whole of
// D-07: the UI shows what the API said. `detail` is the sentence written for a
// human; `title` is the fallback for the rare body that carries no detail; and
// `code` is the only member anything should ever branch on.

export interface Problem {
  type: string;
  title: string;
  status: number;
  detail: string;
  instance: string;
  code: string;
  // Present only when non-empty - the backend omits the member rather than
  // sending an empty object (presentation/api/errors/problem.py).
  errors?: unknown;
}

export function isProblem(value: unknown): value is Problem {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const candidate: Record<string, unknown> = { ...value };
  return (
    typeof candidate["type"] === "string" &&
    typeof candidate["title"] === "string" &&
    typeof candidate["status"] === "number" &&
    typeof candidate["detail"] === "string" &&
    typeof candidate["code"] === "string"
  );
}

export function messageFor(problem: Problem): string {
  return problem.detail || problem.title;
}
