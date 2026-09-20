// Where the access token lives, and the only module in this package that is
// allowed to know (D-06).
//
// In memory first - a module-level `let`, which dies with the tab and is
// unreachable from any other origin. `sessionStorage` is the mirror, and it
// buys exactly one thing: a page refresh keeps the user signed in. It is
// scoped to the tab and cleared when the tab closes.
//
// `localStorage` and `document.cookie` are not merely avoided here: they are
// eslint errors across `src/**` (eslint.config.js), exempted only in the test
// files that must name them to assert they stayed empty. That is what makes
// D-06 a gate rather than a habit.

export const SESSION_KEY = "taskmanager.access_token";

// Read back at module init, which is what makes a refresh survivable.
let token: string | null = sessionStorage.getItem(SESSION_KEY);

export function getToken(): string | null {
  return token;
}

export function setToken(value: string): void {
  token = value;
  sessionStorage.setItem(SESSION_KEY, value);
}

export function clearToken(): void {
  token = null;
  sessionStorage.removeItem(SESSION_KEY);
}
