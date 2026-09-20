import { cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";

// The jest-dom import does two things: it registers the matchers with vitest's
// expect, and it brings in their type augmentation. That is why `globals` stays
// false in vite.config.ts - nothing here depends on a global `expect` existing,
// and every test imports its own.
//
// And that is exactly why `cleanup` has to be wired by hand. Testing Library
// registers its own auto-cleanup only when it can see a GLOBAL `afterEach`;
// with `globals: false` it silently does not, and every render accumulates in
// the same document until a `getByRole` that should match one element reports
// "found multiple". That failure names the query rather than the cause, so it
// is written down here instead of being rediscovered.
afterEach(() => {
  cleanup();
});
