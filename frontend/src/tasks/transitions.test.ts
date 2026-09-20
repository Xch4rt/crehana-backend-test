import { describe, expect, it } from "vitest";

import type { TaskStatus } from "../api/types";
import { STATUSES, allowedMovesFrom } from "./transitions";

// ADR-097's table, from the UI's side. These are exact-equality assertions and
// not `toContain`, because the defect worth catching is an EXTRA move offered,
// not a missing one: a missing move is a control the user cannot reach, while
// an extra one is a button that produces a 409.

describe("the moves a status allows", () => {
  it("offers work and completion from pending", () => {
    expect(allowedMovesFrom("pending")).toEqual(["in_progress", "completed"]);
  });

  it("offers a step back and completion from in_progress", () => {
    expect(allowedMovesFrom("in_progress")).toEqual(["pending", "completed"]);
  });

  it("offers only in_progress from completed, because completed -> pending is the single forbidden move", () => {
    expect(allowedMovesFrom("completed")).toEqual(["in_progress"]);
    expect(allowedMovesFrom("completed")).not.toContain("pending");
  });

  it("never offers a status its own move, since asking for it is a no-op rather than a move", () => {
    for (const status of STATUSES) {
      expect(allowedMovesFrom(status)).not.toContain(status);
    }
  });

  it("covers every status the API has", () => {
    const covered: TaskStatus[] = [...STATUSES];
    expect(covered).toEqual(["pending", "in_progress", "completed"]);
    for (const status of covered) {
      expect(allowedMovesFrom(status).length).toBeGreaterThan(0);
    }
  });
});
