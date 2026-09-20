import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

// The token-storage rules below are a gate, not style. D-06 says the access
// token lives in memory, mirrored to sessionStorage at most - never
// localStorage and never a cookie the backend did not set. A rule is the only
// form of that sentence a future edit cannot quietly ignore, and it was driven
// red once before it was trusted.
const TOKEN_STORAGE_MESSAGE =
  "D-06: the access token lives in memory, mirrored to sessionStorage at most. Never localStorage.";

export default tseslint.config(
  { ignores: ["dist", "node_modules", "coverage"] },
  js.configs.recommended,
  tseslint.configs.recommended,
  // `configs.flat[...]`, not `configs[...]`: this plugin still ships both
  // shapes, and the un-namespaced one is the legacy eslintrc object whose
  // `plugins` is an array of strings. eslint 10 refuses it outright.
  reactHooks.configs.flat["recommended-latest"],
  {
    files: ["src/**/*.{ts,tsx}"],
    languageOptions: {
      globals: globals.browser,
    },
    rules: {
      "no-restricted-globals": [
        "error",
        {
          name: "localStorage",
          message: TOKEN_STORAGE_MESSAGE,
        },
      ],
      "no-restricted-properties": [
        "error",
        {
          object: "window",
          property: "localStorage",
          message: TOKEN_STORAGE_MESSAGE,
        },
        {
          object: "document",
          property: "cookie",
          message:
            "D-06: the UI never sets a cookie the backend did not set.",
        },
      ],
    },
  },
  {
    // The tests have to NAME localStorage and document.cookie in order to
    // assert they stayed empty. A rule that forbade the assertion would remove
    // its own proof, so the exemption is scoped to the test files and to those
    // two rules only.
    files: ["src/**/*.test.{ts,tsx}"],
    rules: {
      "no-restricted-globals": "off",
      "no-restricted-properties": "off",
    },
  },
);
