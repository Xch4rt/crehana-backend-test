import type { ApiError } from "../api/client";

// D-07 rendered. The sentence is the API's own `detail` (falling back to its
// `title`, which is what ApiError's message already resolves), and the `code`
// is shown beside it so a reviewer can see which member of the RFC 9457 body is
// driving the text rather than taking this component's word for it.
//
// `role="alert"` so the refusal is announced rather than only drawn.

export default function ErrorBanner({ error }: { error: ApiError | null }) {
  if (error === null) {
    return null;
  }

  return (
    <div role="alert" className="problem">
      {error.message} <span className="muted">({error.code})</span>
    </div>
  );
}
