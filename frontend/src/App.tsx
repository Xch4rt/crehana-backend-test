import { useEffect, useState } from "react";

import { setUnauthorizedHandler } from "./api/client";
import type { TaskListResponse } from "./api/types";
import LoginScreen from "./auth/LoginScreen";
import { clearToken, getToken, setToken } from "./auth/session";
import AssignedScreen from "./assigned/AssignedScreen";
import ListsScreen from "./lists/ListsScreen";
import TasksScreen from "./tasks/TasksScreen";

// The shell: who holds the token, and which screen is on screen.
//
// Navigation is a hand-rolled view switch and not a router (D-05, ADR-106).
// Three screens, no nesting, no URL to share: `react-router` would be a
// dependency, a lockfile entry and an ADR for a `switch`. The cost is real and
// named in the README's Pending section - there are no deep links and browser
// Back does not move between these screens.

type View =
  | { name: "lists" }
  | { name: "tasks"; list: TaskListResponse }
  | { name: "assigned" };

export default function App() {
  const [token, setTokenState] = useState<string | null>(getToken());
  const [view, setView] = useState<View>({ name: "lists" });

  useEffect(() => {
    setUnauthorizedHandler(() => {
      clearToken();
      setTokenState(null);
      setView({ name: "lists" });
    });
    return () => {
      setUnauthorizedHandler(null);
    };
  }, []);

  function signIn(value: string): void {
    setToken(value);
    setTokenState(value);
    setView({ name: "lists" });
  }

  function signOut(): void {
    clearToken();
    setTokenState(null);
    setView({ name: "lists" });
  }

  return (
    <div className="container">
      <header className="app-header">
        <h1>Task Manager</h1>
        {token !== null && (
          <nav className="nav">
            <button
              type="button"
              aria-current={view.name === "lists" ? "page" : undefined}
              onClick={() => {
                setView({ name: "lists" });
              }}
            >
              My lists
            </button>
            <button
              type="button"
              aria-current={view.name === "assigned" ? "page" : undefined}
              onClick={() => {
                setView({ name: "assigned" });
              }}
            >
              Assigned to me
            </button>
            <button type="button" onClick={signOut}>
              Log out
            </button>
          </nav>
        )}
      </header>

      <main>
        {token === null ? (
          <LoginScreen onAuthenticated={signIn} />
        ) : view.name === "lists" ? (
          <ListsScreen
            onOpen={(list) => {
              setView({ name: "tasks", list });
            }}
          />
        ) : view.name === "tasks" ? (
          <TasksScreen
            list={view.list}
            onBack={() => {
              setView({ name: "lists" });
            }}
          />
        ) : (
          <AssignedScreen
            onBack={() => {
              setView({ name: "lists" });
            }}
          />
        )}
      </main>
    </div>
  );
}
