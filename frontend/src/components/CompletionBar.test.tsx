import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import CompletionBar from "./CompletionBar";

// The third test in this file is the point of the file. It renders a component
// whose three numbers DISAGREE with each other - 1 of 2 done, 0% - and asserts
// that the bar shows 0%. That looks wrong until you know why it is there: the
// API computes the three counters over the WHOLE list while the caller may be
// looking at a filtered subset, so the day somebody "fixes" this component by
// deriving the percentage from `completed / total` it goes red (ADR-009).

describe("CompletionBar", () => {
  it("renders the percentage and the counts it was given", () => {
    render(<CompletionBar total={2} completed={1} percentage={50} />);

    expect(screen.getByText("50%")).toBeInTheDocument();
    expect(screen.getByText("1 / 2")).toBeInTheDocument();
  });

  it("sets the fill's width from the percentage", () => {
    render(<CompletionBar total={2} completed={1} percentage={50} />);

    const fill = screen.getByRole("progressbar").firstElementChild;
    if (fill === null) {
      throw new Error("the progress track rendered no fill element");
    }
    expect(fill).toHaveStyle({ width: "50%" });
  });

  it("shows the percentage it is given even when the counts disagree with it, because it derives nothing (ADR-009)", () => {
    render(<CompletionBar total={2} completed={1} percentage={0} />);

    expect(screen.getByText("0%")).toBeInTheDocument();
    expect(screen.getByText("1 / 2")).toBeInTheDocument();

    const fill = screen.getByRole("progressbar").firstElementChild;
    if (fill === null) {
      throw new Error("the progress track rendered no fill element");
    }
    expect(fill).toHaveStyle({ width: "0%" });
  });

  it("says an empty list is empty in words instead of drawing an unlabelled bar", () => {
    render(<CompletionBar total={0} completed={0} percentage={0} />);

    expect(screen.getByText("No tasks yet")).toBeInTheDocument();
    expect(screen.queryByText("0 / 0")).not.toBeInTheDocument();
  });

  it("exposes the progress to assistive technology", () => {
    render(<CompletionBar total={4} completed={3} percentage={75} />);

    const bar = screen.getByRole("progressbar", { name: "Completion" });
    expect(bar).toHaveAttribute("aria-valuenow", "75");
    expect(bar).toHaveAttribute("aria-valuemin", "0");
    expect(bar).toHaveAttribute("aria-valuemax", "100");
  });
});
