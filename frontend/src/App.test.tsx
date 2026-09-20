import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import App from "./App";

// The smoke test that makes `vitest run` meaningful from the first commit.
// `vitest run` exits 1 when it finds no test file at all, and the alternative -
// `--passWithNoTests` in the npm script - would be a permanent hole: it would
// keep the gate green on the day somebody deletes the suite. One real assertion
// costs less and closes it.
describe("App", () => {
  it("renders the product heading", () => {
    render(<App />);

    expect(
      screen.getByRole("heading", { name: "Task Manager" }),
    ).toBeInTheDocument();
  });
});
