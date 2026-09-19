#!/bin/sh
# Write a .env with a real JWT_SECRET, and never destroy one that already works.
#
# This is step one of the evaluator's path, behind `make env`. It replaces the
# plain copy of .env.example the setup used to open with (D-15, amended by
# ADR-084): the secret published in that file is refused at boot, so copying it
# verbatim no longer produces a runnable configuration - and publishing a
# signing key that a real deployment would then use was the defect this script
# exists to remove.
#
# Three behaviours, in the order they are decided below:
#   * no .env            -> copy .env.example and generate a secret into it;
#   * .env with the published placeholder, an empty value, or no JWT_SECRET line
#                        -> rewrite that one line and leave every other byte alone;
#   * .env with any other secret
#                        -> change nothing and exit 0, so re-running is safe.
#
# POSIX sh only, and no `sed -i`: its argument differs between GNU and BSD, and
# an evaluator on macOS would get the GNU form silently creating a backup file
# named after the expression. Paths are resolved against the working directory,
# so `make` runs it at the repository root and a test can run it in a temporary
# one. The generated value is never printed.
set -eu

EXAMPLE=.env.example
TARGET=.env

if [ ! -f "$EXAMPLE" ]; then
	echo "$EXAMPLE not found - run this from the repository root." >&2
	exit 1
fi

# Read the current value before anything is written, so the decision below is
# made against the file as the developer left it.
current=
if [ -f "$TARGET" ]; then
	current=$(awk 'sub(/^JWT_SECRET=/, "") { print; exit }' "$TARGET")
	case "$current" in
	'' | replace-me*) ;;
	*)
		echo "Kept the existing $TARGET: its JWT_SECRET is already set."
		exit 0
		;;
	esac
fi

# 64 hexadecimal characters: twice the 32-character floor, and nothing in it
# that `awk -v` or a shell would reinterpret.
if command -v openssl >/dev/null 2>&1; then
	secret=$(openssl rand -hex 32)
elif [ -r /dev/urandom ]; then
	secret=$(LC_ALL=C tr -dc 'a-f0-9' </dev/urandom | head -c 64)
else
	echo "no way to generate a secret: neither openssl nor /dev/urandom is available." >&2
	exit 1
fi

if [ -f "$TARGET" ]; then
	created=no
else
	cp "$EXAMPLE" "$TARGET"
	created=yes
fi

# Streamed through a temporary file beside the target and moved over it, so an
# interrupted run cannot leave a half-written .env behind. The END clause covers
# a file that documents no JWT_SECRET at all.
tmp="$TARGET.tmp.$$"
trap 'rm -f "$tmp"' EXIT
awk -v secret="$secret" '
	/^JWT_SECRET=/ && !written { print "JWT_SECRET=" secret; written = 1; next }
	{ print }
	END { if (!written) print "JWT_SECRET=" secret }
' "$TARGET" >"$tmp"
mv "$tmp" "$TARGET"

if [ "$created" = yes ]; then
	echo "Created $TARGET from $EXAMPLE with a generated JWT_SECRET."
else
	echo "Replaced the placeholder JWT_SECRET in $TARGET with a generated value."
fi
