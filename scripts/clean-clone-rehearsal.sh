#!/bin/sh
# Clone this repository into an empty directory and do exactly what README.md says.
#
# This is roadmap SC-4's other half behind one command: `make rehearse`. The
# README claims a stranger can go from nothing to a working API and a green test
# run with two commands. Nothing in the test suite can check that - the
# documentation gate (tests/architecture/test_documentation_claims.py) reads the
# file and the published OpenAPI document, so it can tell that `make docker-test`
# is a real target and that the endpoint table is true, and it cannot tell
# whether any of it *works*. This script is what asks.
#
# The mechanism, and it is the whole design: the commands are not re-typed here.
# They are EXTRACTED from the clone's own README.md, from the fenced `bash`
# blocks between `<!-- rehearsal:begin -->` and `<!-- rehearsal:end -->`,
# concatenated in order into one shell script and executed. A script that
# restated the README would prove the script. This one can only pass if the
# README is right, and it goes red the day somebody edits a command in it.
#
# The blocks are concatenated rather than run one at a time because they share
# shell state - $API, $TOKEN, $AUTH, $LIST, $TASK - exactly as a reader typing
# them into one terminal would. Comment lines and blank lines are dropped, which
# is also what --extract-only prints: what it shows and what it runs are produced
# by the same function, so the dry run cannot describe a different rehearsal than
# the real one.
#
# The one command that is transformed rather than executed verbatim is `make up`,
# because the README itself says it runs in the FOREGROUND and tells the reader
# to leave it there and open a second terminal. There is no second terminal here,
# so the line becomes a background invocation with its output tee'd to a log,
# followed by a bounded poll for `api` reporting healthy and the same pair for
# `ui` - which is the mechanical form of the sentence the README already
# contains. Every other line runs as written, and a non-zero exit fails the
# rehearsal.
#
# What it deliberately does to the developer's machine, stated up front because
# it is a side effect and not a surprise:
#   * it stops the developer's stack with a plain `docker compose down` (no -v,
#     so `test_pgdata` survives), because docker-compose.yml hard-codes :8000 and
#     :5432 and this repository ships no override file on purpose (D-16);
#   * it LEAVES IT DOWN and prints the one command that brings it back. Bringing
#     it back automatically would make the outcome depend on whether it happened
#     to be up when the run started; predictable beats friendly;
#   * every `docker compose down -v` in this file runs inside the CLONE, after
#     COMPOSE_PROJECT_NAME=crehana-rehearsal has been exported, so the volume it
#     destroys can only ever be the rehearsal's own. The dev project is `test`
#     (compose derives it from the directory basename) with volume
#     `test_pgdata`; the isolation is stated explicitly rather than inherited.
#
# Safety, in the shape scripts/break-check.sh established:
#   * it refuses to start unless `git status --porcelain` is empty. A clone
#     carries the COMMITTED tree, so an uncommitted fix is invisible to the run
#     and a green result would be a lie about the tree that gets delivered;
#   * it refuses to start unless README.md is tracked - a rehearsal of a tree
#     with no committed README proves nothing;
#   * a trap installed BEFORE the first container is stopped restores on any
#     exit, including HUP, INT, QUIT and TERM - each named, because a shell that
#     dies from an untrapped signal does not run its EXIT trap under dash
#     (ADR-094). It tears down the rehearsal project and removes the temporary
#     directory, and it touches nothing outside them;
#   * no `git stash`, no `git reset --hard`, no blanket `git checkout -- .`, and
#     nothing under this repository is written at all: the clone and every log
#     live in a `mktemp -d` directory.
#
# `timeout(1)` is NOT used, and not by preference: it does not exist on this
# macOS host. Every bounded wait is a POSIX polling loop with a counter and
# `sleep`, the idiom docker/entrypoint.sh already uses.
#
# Deliberately in NO gate path (D-09, the `make break-check` precedent): not in
# `make test`, not in .pre-commit-config.yaml, not in .github/workflows/ci.yml.
# It rebuilds an image from nothing and runs the whole suite in it, which is
# minutes, and the value of a ten-second commit loop is that nobody skips it.
# This is a spot check run on demand - before delivery, and whenever the README's
# commands change. CLAUDE.md's two-places rule is satisfied by saying so.
#
# The extracted commands run under `set -x`, so a failure names the command that
# produced it. The trace therefore contains the bearer token the README's own
# quickstart creates. That token is signed with a secret generated inside the
# throwaway clone, for a database this same run destroys, and the log lives in
# the temporary directory the trap removes - but the JWT_SECRET itself is never
# traced and never printed, and the assertions that read it turn tracing off
# first.
#
# POSIX sh only. Paths resolve against the working directory, so `make` runs it
# at the repository root and tests/unit/test_clean_clone_rehearsal.py runs it in
# a temporary one.
set -eu

BEGIN_MARKER='<!-- rehearsal:begin -->'
END_MARKER='<!-- rehearsal:end -->'
PROJECT=crehana-rehearsal
MINIMUM_COMMANDS=3

# The API is polled for at most POLL_ATTEMPTS * POLL_SECONDS. Three polls is the
# observed figure once the image exists; sixty is four minutes, which is slack
# for a cold machine rather than a guess about a fast one.
POLL_ATTEMPTS=60
POLL_SECONDS=3

# The one path README.md names in backticks that must NOT exist in a fresh
# clone: `.env` is git-ignored on purpose, and the README says "untracked" in
# the same sentence. Exempting it would be a hole, so the exemption is paid for -
# the run asserts .env is absent before `make env` and present, with a real
# secret, afterwards.
UNTRACKED_BY_DESIGN='.env'

# --- extraction, shared by --extract-only and the real run --------------------

extract_commands() {
	# Every command line inside the region's fenced `bash` blocks, in order.
	awk -v begin="$BEGIN_MARKER" -v end="$END_MARKER" '
		index($0, begin) { region = 1; next }
		index($0, end)   { region = 0; next }
		region && !block && /^```bash[ \t]*$/ { block = 1; next }
		region && block && /^```[ \t]*$/ { block = 0; next }
		region && block && $0 !~ /^[ \t]*$/ && $0 !~ /^[ \t]*#/ { print }
	' "$1"
}

validate_markers() {
	# Exactly one of each, in order - never "at least one". A second `begin`
	# silently moves the region, and the rehearsal would then execute a set of
	# commands nobody reviewed (06-REVIEW WR-05; the same hole is not dug twice).
	awk -v begin="$BEGIN_MARKER" -v end="$END_MARKER" -v name="$1" '
		index($0, begin) { begins++; if (!at_begin) at_begin = NR }
		index($0, end)   { ends++;   if (!at_end)   at_end   = NR }
		END {
			if (begins != 1 || ends != 1) {
				printf "%s has %d begin and %d end rehearsal marker(s); exactly one of each is required\n", name, begins, ends > "/dev/stderr"
				exit 1
			}
			if (at_begin > at_end) {
				printf "%s has the end marker before the begin marker\n", name > "/dev/stderr"
				exit 1
			}
		}
	' "$1"

	count=$(extract_commands "$1" | wc -l | tr -d ' ')
	if [ "$count" -lt "$MINIMUM_COMMANDS" ]; then
		printf '%s has %s command line(s) between its rehearsal markers; at least %s are required, or the rehearsal would prove nothing by running almost nothing\n' \
			"$1" "$count" "$MINIMUM_COMMANDS" >&2
		exit 1
	fi
}

# --- --extract-only: the dry run, no docker and no git ------------------------

if [ "${1:-}" = "--extract-only" ]; then
	if [ ! -f README.md ]; then
		echo "README.md not found - run this from the repository root." >&2
		exit 1
	fi
	validate_markers README.md
	extract_commands README.md
	exit 0
fi

if [ "$#" -ne 0 ]; then
	echo "usage: sh scripts/clean-clone-rehearsal.sh [--extract-only]" >&2
	exit 1
fi

# --- step 0: refuse to rehearse anything but the committed tree ---------------

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
	echo "not inside a git repository - this script rehearses a clone of it." >&2
	exit 1
fi

REPO=$(pwd)
if [ "$(git rev-parse --show-toplevel)" != "$REPO" ]; then
	echo "run this from the repository root: $(git rev-parse --show-toplevel)" >&2
	exit 1
fi

if [ -n "$(git status --porcelain)" ]; then
	echo "the working tree has uncommitted changes:" >&2
	git status --porcelain >&2
	echo "" >&2
	echo "This script clones the COMMITTED tree, so an uncommitted fix is" >&2
	echo "invisible to it and a green run would be a claim about a tree nobody" >&2
	echo "is going to deliver. Commit, then re-run \`make rehearse\`." >&2
	exit 1
fi

if ! git ls-files --error-unmatch README.md >/dev/null 2>&1; then
	echo "README.md is not tracked - there would be nothing to rehearse." >&2
	exit 1
fi

validate_markers README.md

# --- the trap, installed before anything is stopped or created ----------------

WORK=
CLONE=

cleanup() {
	if [ -n "$CLONE" ] && [ -d "$CLONE" ]; then
		( cd "$CLONE" && COMPOSE_PROJECT_NAME="$PROJECT" docker compose down -v ) \
			>/dev/null 2>&1 || true
	fi
	if [ -n "$WORK" ] && [ -d "$WORK" ]; then
		rm -rf "$WORK"
	fi
}

on_signal() {
	cleanup
	echo "" >&2
	echo "interrupted - the rehearsal project is down and its directory is gone." >&2
	echo "The developer stack is DOWN. Bring it back with: make up" >&2
	exit 143
}

trap cleanup EXIT
# All four by name. POSIX does not run the EXIT trap when the shell dies from an
# untrapped signal; bash does anyway and dash does not, and dash is /bin/sh on
# Debian. A run interrupted at minute three would otherwise leave a rehearsal
# project up, holding :8000 and :5432 against the developer's own stack
# (ADR-094).
trap on_signal HUP INT QUIT TERM

# --- the step table -----------------------------------------------------------

STEPS=
STEP_LABEL=
STEP_BEGAN=0
TOTAL_BEGAN=$(date +%s)

step() {
	STEP_LABEL=$1
	STEP_BEGAN=$(date +%s)
	printf '\n=== %s\n' "$STEP_LABEL"
}

step_done() {
	elapsed=$(($(date +%s) - STEP_BEGAN))
	STEPS="$STEPS$(printf '%5ss  %s' "$elapsed" "$STEP_LABEL")
"
	printf '    (%ss)\n' "$elapsed"
}

# --- step 1: stop the developer's stack, keeping its volume -------------------

step "1. stop the developer stack (plain \`down\`: test_pgdata survives)"
printf '    what was running:\n'
docker compose ps | sed 's/^/      /'
docker compose down
step_done

# --- step 2: clone the committed tree into an empty directory -----------------

step "2. clone the committed tree into an empty directory"
WORK=$(mktemp -d)
CLONE="$WORK/$PROJECT"
git clone --quiet "$REPO" "$CLONE"
printf '    %s -> %s\n' "$(git rev-parse --short HEAD)" "$CLONE"
step_done

# --- step 3: everything from here happens inside the clone --------------------

cd "$CLONE"
# Exported before any `down -v` exists in this process, so the destructive
# command below cannot address the developer's project even by accident.
COMPOSE_PROJECT_NAME="$PROJECT"
export COMPOSE_PROJECT_NAME

# --- step 4: a fresh project volume ------------------------------------------

step "4. docker compose down -v in the clone (project: $COMPOSE_PROJECT_NAME)"
# Idempotent, and load-bearing rather than hygiene: the postgres image runs
# docker/initdb/ only against an EMPTY data directory, so `taskmanager_test` -
# which `make docker-test` needs - exists only on a fresh volume. The quickstart
# also registers ada@example.com and grace@example.com, which a reused database
# would already hold.
docker compose down -v
step_done

# --- step 5: the claims that need the whole tree ------------------------------
#
# Before the build, not after it. The plan put this after the --no-cache build;
# it runs in seconds and the build is minutes, and the loop this script exists to
# serve is find-a-gap, fix-the-document, re-run. Waiting four minutes to be told
# a path is misspelled is the difference between a tool somebody uses and a tool
# somebody runs once.
#
# These checks live here rather than in the pytest gate because the test image
# deliberately carries neither .planning/ nor .github/ nor docker/ (ADR-102), so
# a path-existence check over the whole tree could only ever be a skip in the
# container. The clone has everything.

step "5. every path the README cites, and every [PDF] key it owes"
missing_paths=
for token in $(
	grep -o '`[^`]*`' README.md |
		sed 's/^`//; s/`$//' |
		grep -E '^[A-Za-z0-9_.][A-Za-z0-9_./-]*$' |
		grep -E '/|\.(py|md|yml|yaml|ini|toml|sh|cfg|txt|json|example)$|^\.[A-Za-z]' |
		sort -u
); do
	if [ "$token" = "$UNTRACKED_BY_DESIGN" ]; then
		continue
	fi
	if [ ! -e "$token" ]; then
		missing_paths="$missing_paths $token"
	fi
done

if [ -e "$UNTRACKED_BY_DESIGN" ]; then
	printf '    %s exists in a fresh clone; it is supposed to be untracked\n' \
		"$UNTRACKED_BY_DESIGN" >&2
	exit 1
fi

missing_keys=
for key in $(
	grep -o '\[PDF [^]]*\]' .planning/REQUIREMENTS.md |
		sed 's/\[PDF //; s/\]//' |
		tr ',' '\n' |
		sed 's/^ *//; s/ *$//' |
		grep '^[0-9]' |
		sort -u
); do
	# As a table cell, not anywhere in the file: `6` appears in the README a
	# dozen times as a number, and a substring match would report the evidence
	# map complete while the row was missing.
	if ! grep -q "^| $key |" README.md; then
		missing_keys="$missing_keys $key"
	fi
done

if [ -n "$missing_paths" ] || [ -n "$missing_keys" ]; then
	if [ -n "$missing_paths" ]; then
		printf '    README.md cites these paths, which do not exist in the clone:\n%s\n' \
			"$(printf '%s\n' $missing_paths | sed 's/^/      /')" >&2
	fi
	if [ -n "$missing_keys" ]; then
		printf '    .planning/REQUIREMENTS.md cites these [PDF] keys, which have no row in the README evidence map:\n%s\n' \
			"$(printf '%s\n' $missing_keys | sed 's/^/      /')" >&2
	fi
	exit 1
fi
printf '    every cited path exists, every [PDF] key has a row\n'
step_done

# --- step 6: build from nothing ----------------------------------------------

step "6. docker compose build --no-cache"
docker compose build --no-cache
step_done

# --- step 7: run the README ---------------------------------------------------

step "7. run the README's own commands"
RUNNABLE="$WORK/readme-commands.sh"
REHEARSAL_UP_LOG="$WORK/make-up.log"
export REHEARSAL_UP_LOG

{
	cat <<'PREAMBLE'
#!/bin/sh
# GENERATED from README.md by scripts/clean-clone-rehearsal.sh. Not committed.
set -e

rehearsal_wait_for_a_healthy_api() {
	attempt=1
	while [ "$attempt" -le "$REHEARSAL_POLL_ATTEMPTS" ]; do
		if [ "$(docker compose ps --format '{{.Health}}' api 2>/dev/null)" = healthy ]; then
			return 0
		fi
		attempt=$((attempt + 1))
		sleep "$REHEARSAL_POLL_SECONDS"
	done
	echo "api never reported healthy; the tail of \`make up\`:" >&2
	tail -40 "$REHEARSAL_UP_LOG" >&2
	return 1
}

rehearsal_assert_the_api_is_ours() {
	# Tracing off for the whole body: it reads JWT_SECRET out of .env, and a
	# secret that reaches a log is a published secret.
	set +x
	ours=$(docker compose ps -q api)
	if [ -z "$ours" ]; then
		echo "no api container in project $COMPOSE_PROJECT_NAME" >&2
		return 1
	fi
	publishing=$(docker ps --filter publish=8000 --no-trunc --format '{{.ID}}')
	if [ "$publishing" != "$ours" ]; then
		echo "the container answering on :8000 is not this rehearsal's api." >&2
		echo "  this rehearsal's api: $ours" >&2
		echo "  publishing :8000:     ${publishing:-<nothing>}" >&2
		return 1
	fi
	answer=$(curl -s http://localhost:8000/health)
	case "$answer" in
	*'"status":"ok"'*'"version":"'*) ;;
	*)
		echo "/health did not answer the document the README shows: $answer" >&2
		return 1
		;;
	esac
	if [ ! -f .env ]; then
		echo ".env does not exist - \`make env\` is not the first command in the region" >&2
		return 1
	fi
	case "$(awk 'sub(/^JWT_SECRET=/, "") { print; exit }' .env)" in
	'')
		echo ".env carries no JWT_SECRET" >&2
		return 1
		;;
	replace-me*)
		echo ".env still carries the placeholder JWT_SECRET, which ADR-084 refuses at boot" >&2
		return 1
		;;
	esac
	echo "the healthy api on :8000 is this rehearsal's container ($ours), and .env has a generated secret"
	set -x
}

rehearsal_wait_for_a_healthy_ui() {
	attempt=1
	while [ "$attempt" -le "$REHEARSAL_POLL_ATTEMPTS" ]; do
		if [ "$(docker compose ps --format '{{.Health}}' ui 2>/dev/null)" = healthy ]; then
			return 0
		fi
		attempt=$((attempt + 1))
		sleep "$REHEARSAL_POLL_SECONDS"
	done
	echo "ui never reported healthy; the tail of \`make up\`:" >&2
	tail -40 "$REHEARSAL_UP_LOG" >&2
	return 1
}

rehearsal_assert_the_ui_is_ours() {
	# The same argument as the api assertion above, for the port that is far
	# MORE likely to be contended: 8080 is the default of every local web
	# server, proxy and admin console a developer has ever started. A foreign
	# server answering there would let every UI claim in the README pass
	# without this rehearsal's own container ever being reached.
	#
	# No `set +x` dance here. Unlike the api assertion this function reads no
	# secret, so there is nothing tracing could publish.
	ours=$(docker compose ps -q ui)
	if [ -z "$ours" ]; then
		echo "no ui container in project $COMPOSE_PROJECT_NAME" >&2
		return 1
	fi
	publishing=$(docker ps --filter publish=8080 --no-trunc --format '{{.ID}}')
	if [ "$publishing" != "$ours" ]; then
		echo "the container answering on :8080 is not this rehearsal's ui." >&2
		echo "  this rehearsal's ui: $ours" >&2
		echo "  publishing :8080:    ${publishing:-<nothing>}" >&2
		return 1
	fi
	answer=$(curl -sf http://localhost:8080/)
	case "$answer" in
	*'id="root"'*) ;;
	*)
		echo "http://localhost:8080/ did not serve the SPA document" >&2
		return 1
		;;
	esac
	echo "the healthy ui on :8080 is this rehearsal's container ($ours), and it serves the SPA"
}

set -x
PREAMBLE
	extract_commands README.md | awk '
		/^[ \t]*make up[ \t]*$/ {
			print "make up > \"$REHEARSAL_UP_LOG\" 2>&1 &"
			print "rehearsal_wait_for_a_healthy_api"
			print "rehearsal_assert_the_api_is_ours"
			print "rehearsal_wait_for_a_healthy_ui"
			print "rehearsal_assert_the_ui_is_ours"
			next
		}
		{ print }
	'
} >"$RUNNABLE"

printf '    %s command line(s) extracted; `make up` becomes 5 generated lines\n' \
	"$(extract_commands README.md | wc -l | tr -d ' ')"
REHEARSAL_POLL_ATTEMPTS=$POLL_ATTEMPTS
REHEARSAL_POLL_SECONDS=$POLL_SECONDS
export REHEARSAL_POLL_ATTEMPTS REHEARSAL_POLL_SECONDS

# The status is written to a file rather than read from `$?`, because `$?` after
# a pipeline is `tee`'s status and `tee` always succeeds. PIPESTATUS is a
# bashism, and this file is POSIX sh.
{
	set +e
	sh "$RUNNABLE" 2>&1
	echo $? >"$WORK/readme-status"
} | tee "$WORK/readme-run.log"
readme_status=$(cat "$WORK/readme-status")

if [ "$readme_status" -ne 0 ]; then
	echo "" >&2
	echo "the README's commands failed. The last command the trace reached:" >&2
	grep '^+ ' "$WORK/readme-run.log" | tail -1 | sed 's/^/      /' >&2
	echo "" >&2
	echo "That command is a line of README.md between the rehearsal markers, or" >&2
	echo "the poll this script generates around \`make up\`. Fix the DOCUMENT (or" >&2
	echo "this script), commit, and re-run - never the assertion." >&2
	exit 1
fi
step_done

# --- step 8: leave nothing behind ---------------------------------------------

step "8. docker compose down -v in the clone, and remove the clone"
docker compose down -v
cd "$REPO"
rm -rf "$WORK"
WORK=
CLONE=
step_done

# --- step 9: the report --------------------------------------------------------

printf '\n'
printf 'step timings\n'
printf '%s' "$STEPS"
printf '%5ss  total\n' "$(($(date +%s) - TOTAL_BEGAN))"
printf '\n'
printf 'A fresh clone of %s built from nothing, followed README.md and reached a\n' \
	"$(git rev-parse --short HEAD)"
printf 'healthy API and a green containerised test run.\n'
printf '\n'
printf 'The developer stack is DOWN, on purpose. Bring it back with:\n'
printf '\n'
printf '    make up\n'
