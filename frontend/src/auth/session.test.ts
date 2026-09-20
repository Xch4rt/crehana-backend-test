import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { clearToken, getToken, SESSION_KEY, setToken } from "./session";

// D-06, asserted rather than asserted-about. This module is the only place in
// the UI that is allowed to know where the token lives, so this is the only
// file that has to prove where it does NOT live - which is why the eslint
// token-storage rules are switched off for `src/**/*.test.*` and nowhere else.

beforeEach(() => {
  clearToken();
  sessionStorage.clear();
  localStorage.clear();
});

afterEach(() => {
  clearToken();
  sessionStorage.clear();
  localStorage.clear();
});

describe("the session", () => {
  it("holds the token and mirrors it to sessionStorage", () => {
    setToken("a-signed-token");

    expect(getToken()).toBe("a-signed-token");
    expect(sessionStorage.getItem(SESSION_KEY)).toBe("a-signed-token");
  });

  it("puts nothing in localStorage and sets no cookie", () => {
    setToken("a-signed-token");
    const duringSession = {
      localStorage: localStorage.length,
      cookie: document.cookie,
    };
    clearToken();

    expect(duringSession).toEqual({ localStorage: 0, cookie: "" });
    expect(localStorage.length).toBe(0);
    expect(document.cookie).toBe("");
  });

  it("empties both the value and its mirror on clear", () => {
    setToken("a-signed-token");

    clearToken();

    expect(getToken()).toBeNull();
    expect(sessionStorage.getItem(SESSION_KEY)).toBeNull();
  });

  it("adopts a token already in sessionStorage at module init", async () => {
    // A page refresh, mechanically: seed the mirror, drop the module registry
    // so the module's top-level code runs again, and ask the fresh copy. This
    // is the half of D-06 that makes sessionStorage worth having at all - an
    // in-memory-only token logs the user out on every F5.
    sessionStorage.setItem(SESSION_KEY, "a-token-from-before-the-refresh");
    vi.resetModules();

    const reloaded = await import("./session");

    expect(reloaded.getToken()).toBe("a-token-from-before-the-refresh");
  });
});
