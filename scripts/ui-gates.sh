#!/bin/sh
# The frontend's three gates, behind one command, for the pre-commit hook.
#
# This is THE ONE HOOK IN THIS REPOSITORY THAT MAY DECLINE TO RUN, and the trade
# is stated here rather than discovered:
#
#   * a fresh clone has no `frontend/node_modules`. Nothing installs it except
#     `make ui-install`, and a Python-only contributor may never run it;
#   * a hook that failed in that state would make EVERY commit fail on a machine
#     that has never touched the frontend - including a commit that changes only
#     `src/taskmanager`. That is a worse outcome than the one it prevents;
#   * so when `node_modules` is absent this script explains itself and exits 0.
#
# The real gate is therefore the CI `frontend` job, which runs `npm ci` and then
# eslint, tsc and vitest on every push and every pull request with nothing to
# opt out of. This is exactly the shape `.pre-commit-config.yaml`'s header
# already describes for its `.venv/bin/`-qualified entries: the local hook is a
# convenience that works where the environment exists, and the runner is what
# enforces it (ADR-108).
#
# The hook that calls this is scoped `files: ^frontend/`, so a commit that
# touches no frontend file does not even reach this script.
#
# POSIX sh only, and paths resolve against the working directory - pre-commit
# runs every hook from the repository root.
set -eu

if [ ! -d frontend/node_modules ]; then
	echo "frontend gates SKIPPED: frontend/node_modules is absent. Install it with \`make ui-install\`." >&2
	echo "CI runs eslint, tsc and vitest on every push regardless, so this skip cannot hide a red frontend." >&2
	exit 0
fi

npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend test
