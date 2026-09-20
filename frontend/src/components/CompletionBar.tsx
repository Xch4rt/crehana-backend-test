// ADR-009, rendered. This component is GIVEN three numbers and derives none of
// them: the API computes `completion_percentage` over the whole list with one
// SQL aggregate, while the caller may be looking at a filtered subset of its
// tasks. A bar that recomputed `completed / total` from whatever rows happen to
// be on screen would contradict the API it sits on - which is precisely the
// defect this project has an ADR about.
//
// So the props are three required numbers with no defaults. A default would let
// a caller omit one and get a plausible-looking bar built out of a zero.

interface CompletionBarProps {
  total: number;
  completed: number;
  percentage: number;
}

// Presentation only, and only ever applied to the number the API sent: 33.333
// reads as 33.3, and 50 stays 50.
function asText(percentage: number): string {
  return `${String(Math.round(percentage * 10) / 10)}%`;
}

export default function CompletionBar({
  total,
  completed,
  percentage,
}: CompletionBarProps) {
  return (
    <div className="completion">
      <div
        className="completion-bar"
        role="progressbar"
        aria-label="Completion"
        aria-valuenow={percentage}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div className="fill" style={{ width: `${String(percentage)}%` }} />
      </div>
      <p className="completion-text">
        <strong>{asText(percentage)}</strong>{" "}
        <span className="muted">
          {total === 0 ? "No tasks yet" : `${String(completed)} / ${String(total)}`}
        </span>
      </p>
    </div>
  );
}
