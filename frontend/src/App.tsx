import { useEffect, useState } from "react";

import { setUnauthorizedHandler } from "./api/client";
import LoginScreen from "./auth/LoginScreen";
import { clearToken, getToken, setToken } from "./auth/session";

// The shell. Plan 08-02 replaces the signed-in placeholder with the three real
// screens; what lives here permanently is the session: who holds the token, and
// the one effect that makes a 401 raised ANYWHERE end it (UI-05).

export default function App() {
  const [token, setTokenState] = useState<string | null>(getToken());

  useEffect(() => {
    setUnauthorizedHandler(() => {
      clearToken();
      setTokenState(null);
    });
    return () => {
      setUnauthorizedHandler(null);
    };
  }, []);

  function signIn(value: string): void {
    setToken(value);
    setTokenState(value);
  }

  function signOut(): void {
    clearToken();
    setTokenState(null);
  }

  return (
    <div className="container">
      <h1>Task Manager</h1>
      <main>
        {token === null ? (
          <LoginScreen onAuthenticated={signIn} />
        ) : (
          <div className="panel">
            <p>Signed in.</p>
            <button type="button" onClick={signOut}>
              Log out
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
