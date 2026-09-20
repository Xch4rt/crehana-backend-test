// One import, and it does two things: it registers the jest-dom matchers with
// vitest's expect, and it brings in their type augmentation. That is why
// `globals` stays false in vite.config.ts - nothing here depends on a global
// `expect` existing, and every test imports its own.
import "@testing-library/jest-dom/vitest";
