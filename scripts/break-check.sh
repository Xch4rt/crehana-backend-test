#!/bin/sh
# Break the code on purpose, five times, and prove the suite notices.
#
# This is roadmap SC-4 behind one command: `make break-check`. A green suite
# only means something if a defect turns it red, so each break below is a real
# one-literal mutation of `src/`, applied, run against the tests that should
# care, asserted RED, and reverted. A break that comes back GREEN is this
# script's failure, and it exits non-zero naming which one survived.
#
# The five breaks, and what each one is asking:
#   1 completion.py   - the percentage formula inverted (the break the roadmap
#                       mandates). Does anything check the number, or only its
#                       presence?
#   2 task_status.py  - completed -> pending added to ALLOWED_TRANSITIONS. Is
#                       the state machine asserted, or just exercised?
#   3 access.py       - the assignee comparison inverted in both guards. Is
#                       visibility tested from both sides?
#   4 tokens.py       - `"verify_exp": False` added to the decode options. Is
#                       expiry enforcement observable over HTTP? It was not,
#                       until plan 06-01 seeded the caller (see the incident
#                       entry in AI_WORKFLOW.md).
#   5 delete.py       - the list deletion's locking read downgraded to a plain
#                       one. Does anything but a fakes-based road pin notice?
#
# Safety, because this is the only tool in this repository that deliberately
# writes to `src/`:
#   * it refuses to start unless `git status --porcelain -- src/` is empty, so
#     it can never be blamed for - or destroy - uncommitted work;
#   * a trap installed BEFORE the first mutation restores on any exit, including
#     INT and TERM, and it restores exactly the files this script itself touched,
#     never a blanket checkout of the tree;
#   * after every restore the clean-tree check is re-run, so break 2 cannot
#     start on top of break 1.
#
# Deliberately in NO gate path (D-09): not in `make test`, not in
# .pre-commit-config.yaml, not in .github/workflows/ci.yml. It runs the whole
# relevant selection five times over, which costs about a minute; the normal
# loop is ten seconds and stays that way. An evaluator runs it once, on demand.
# Each break's tests are named per break rather than running the whole suite -
# which is also what makes the report meaningful, since a break has to redden a
# test that is not a mirror of the implementation.
#
# Breaks 2-5 reach integration tests, so PostgreSQL must be up: `make up`, or
# `docker compose up -d db`.
#
# POSIX sh only, and no `sed -i`: its argument differs between GNU and BSD, and
# an evaluator on macOS would get the GNU form silently creating a backup file
# named after the expression (the reason scripts/init-env.sh uses awk + mv).
# Each mutation is instead an exact `str.replace` in Python, guarded by
# `assert old in s`, so a source line that has drifted since this script was
# written fails loudly instead of quietly mutating nothing and reporting a
# survivor. `python3` is enough for that - it imports nothing from the project.
# Paths resolve against the working directory, so `make` runs it at the
# repository root and tests/unit/test_break_check.py runs it in a temporary one.
set -eu

# The one knob, and it exists for tests/unit/test_break_check.py: that module
# drives this file as a program in a throwaway git repository, where there is no
# virtualenv and where running the real suite would defeat the point of a unit
# test. Nothing else overrides it.
PYTEST=${BREAK_CHECK_PYTEST:-.venv/bin/pytest}

if [ "${BREAK_CHECK_PYTEST:-}" = "" ] && [ ! -x "$PYTEST" ]; then
	echo "$PYTEST not found - run \`make install\` first." >&2
	exit 1
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
	echo "not inside a git repository - this script restores src/ with git." >&2
	exit 1
fi

# The files mutated so far, so the trap restores those and only those. A blanket
# `git checkout -- .` here would be able to destroy work this script never
# touched, which is not a trade a diagnostic tool gets to make.
MUTATED=

assert_src_is_clean() {
	if [ -n "$(git status --porcelain -- src/)" ]; then
		echo "src/ has uncommitted changes:" >&2
		git status --porcelain -- src/ >&2
		echo "" >&2
		echo "This script mutates src/ and restores it with git, so it needs a" >&2
		echo "clean tree to restore to. Commit or stash your work, then re-run" >&2
		echo "\`make break-check\`." >&2
		exit 1
	fi
}

restore_mutated() {
	for mutated_file in $MUTATED; do
		git checkout -- "$mutated_file"
	done
	MUTATED=
}

cleanup() {
	restore_mutated
	rm -rf "$LOGDIR"
}

on_signal() {
	cleanup
	echo "" >&2
	echo "interrupted - src/ restored." >&2
	exit 143
}

assert_src_is_clean

# Outside the repository on purpose: a log written under it would show up in the
# clean-tree check this script depends on.
LOGDIR=$(mktemp -d)
trap cleanup EXIT
trap on_signal INT TERM

survivors=0
checked=0

# check_break <number> <label> <file> <old> <new> <test file>...
check_break() {
	number=$1
	label=$2
	file=$3
	old=$4
	new=$5
	shift 5

	printf '\n--- break %s: %s\n' "$number" "$label"
	printf '    %s\n' "$file"

	# Recorded before the write, so an interrupted or refused mutation is still
	# restored.
	MUTATED="$MUTATED $file"
	BREAK_FILE=$file BREAK_OLD=$old BREAK_NEW=$new python3 - <<'PY'
import os
import pathlib

path = pathlib.Path(os.environ["BREAK_FILE"])
old = os.environ["BREAK_OLD"]
source = path.read_text(encoding="utf-8")
assert old in source, f"{path}: nothing to mutate, this literal is gone: {old!r}"
path.write_text(source.replace(old, os.environ["BREAK_NEW"]), encoding="utf-8")
PY

	log="$LOGDIR/break-$number.log"
	# $PYTEST is deliberately unquoted: the override above may be several words.
	set +e
	$PYTEST "$@" --no-cov -p no:cacheprovider >"$log" 2>&1
	status=$?
	set -e

	restore_mutated
	assert_src_is_clean

	checked=$((checked + 1))
	if [ "$status" -eq 0 ]; then
		survivors=$((survivors + 1))
		printf '    SURVIVED: every test passed with the defect in place.\n'
		printf '    Nothing in these files can tell the difference:\n'
		for test_file in "$@"; do
			printf '      %s\n' "$test_file"
		done
	else
		red=$(grep -c '^FAILED ' "$log" || true)
		printf '    red: %s test(s) failed\n' "$red"
		sed -n 's/^FAILED \([^ ]*\).*/      \1/p' "$log"
	fi
}

check_break 1 "the completion percentage is inverted" \
	src/taskmanager/domain/value_objects/completion.py \
	'round(self.completed / self.total * 100, 2)' \
	'round((self.total - self.completed) / self.total * 100, 2)' \
	tests/unit/domain/test_completion.py \
	tests/integration/api/test_task_lists.py \
	tests/integration/api/test_tasks.py

check_break 2 "completed -> pending becomes a legal transition" \
	src/taskmanager/domain/value_objects/task_status.py \
	'TaskStatus.COMPLETED: frozenset({TaskStatus.IN_PROGRESS}),' \
	'TaskStatus.COMPLETED: frozenset({TaskStatus.IN_PROGRESS, TaskStatus.PENDING}),' \
	tests/unit/domain/test_task_status.py \
	tests/unit/application/test_change_task_status.py \
	tests/integration/api/test_tasks.py \
	tests/integration/test_concurrent_writes.py

# Both occurrences are mutated - the assignee clause of visible_task and the one
# in owned_task - which is the point: one literal, two guards, and a suite that
# only ever asked from the owner's side would not notice either.
check_break 3 "the assignee visibility comparison is inverted" \
	src/taskmanager/application/use_cases/access.py \
	'if task.assignee_id == actor_id:' \
	'if task.assignee_id != actor_id:' \
	tests/unit/application/test_access.py \
	tests/integration/api/test_permission_matrix.py \
	tests/integration/api/test_assignment.py

check_break 4 "token expiry is not verified" \
	src/taskmanager/infrastructure/security/tokens.py \
	'options={"require": _REQUIRED_CLAIMS},' \
	'options={"require": _REQUIRED_CLAIMS, "verify_exp": False},' \
	tests/unit/infrastructure/test_tokens.py \
	tests/integration/api/test_auth.py

check_break 5 "the list deletion no longer locks the row it removes" \
	src/taskmanager/application/use_cases/task_lists/delete.py \
	'self._uow, command.task_list_id, command.actor_id, for_update=True' \
	'self._uow, command.task_list_id, command.actor_id' \
	tests/unit/application/test_write_paths_hold_what_they_change.py \
	tests/integration/test_concurrent_writes.py

printf '\n'
if [ "$survivors" -ne 0 ]; then
	printf '%s of %s breaks SURVIVED. The suite cannot see them.\n' \
		"$survivors" "$checked" >&2
	exit 1
fi
printf 'All %s breaks turned the suite red. src/ is back as it was.\n' "$checked"
