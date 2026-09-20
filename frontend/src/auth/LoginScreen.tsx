import { useState } from "react";

import { ApiError, login, register } from "../api/client";
import ErrorBanner from "../components/ErrorBanner";
import Field from "../components/Field";

// UI-01's first half: register, then log in. One component with a toggle rather
// than two routes, because this UI has no router (ADR-106) and the two forms
// differ by one field.
//
// After a successful registration the account is logged in immediately with the
// credentials just submitted - the API has no "registered but not yet signed
// in" state worth showing, and making the user retype a password they typed ten
// seconds ago buys nothing.

type Mode = "login" | "register";

export default function LoginScreen({
  onAuthenticated,
}: {
  onAuthenticated: (token: string) => void;
}) {
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<ApiError | null>(null);
  const [inFlight, setInFlight] = useState(false);

  const registering = mode === "register";

  function switchTo(next: Mode): void {
    setMode(next);
    setError(null);
  }

  async function submit(event: React.FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setError(null);
    setInFlight(true);
    try {
      if (registering) {
        await register({ email, full_name: fullName, password });
      }
      const token = await login(email, password);
      onAuthenticated(token.access_token);
    } catch (failure: unknown) {
      if (failure instanceof ApiError) {
        setError(failure);
      } else {
        throw failure;
      }
    } finally {
      setInFlight(false);
    }
  }

  return (
    <div className="panel">
      <h2>{registering ? "Create an account" : "Log in"}</h2>
      <ErrorBanner error={error} />
      <form
        onSubmit={(event) => {
          void submit(event);
        }}
      >
        <Field
          id="email"
          label="Email"
          type="email"
          value={email}
          required
          autoComplete="email"
          onChange={setEmail}
        />
        {registering && (
          <Field
            id="full_name"
            label="Full name"
            value={fullName}
            required
            autoComplete="name"
            onChange={setFullName}
          />
        )}
        <Field
          id="password"
          label="Password"
          type="password"
          value={password}
          required
          autoComplete={registering ? "new-password" : "current-password"}
          onChange={setPassword}
        />
        <button type="submit" disabled={inFlight}>
          {registering ? "Register" : "Log in"}
        </button>
      </form>
      <p className="muted">
        {registering ? "Already have an account? " : "No account yet? "}
        <button
          type="button"
          className="link"
          onClick={() => {
            switchTo(registering ? "login" : "register");
          }}
        >
          {registering ? "Log in" : "Create an account"}
        </button>
      </p>
    </div>
  );
}
