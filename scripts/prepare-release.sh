#!/usr/bin/env bash
#
# prepare-release.sh - mechanical, error-prone middle of a release.
#
# Given ONE version, it normalizes the two forms that must agree (the PEP 440
# package version and the SemVer git tag), runs a few guard checks, bumps
# pyproject.toml + uv.lock, and then PRINTS the git commands for you to run.
# It never commits, tags, or pushes - the irreversible steps stay in your hands.
#
# Usage:
#   ./scripts/prepare-release.sh 2.0.0-rc2     # any of these forms work:
#   ./scripts/prepare-release.sh 2.0.0rc2      #   2.0.0-rc2 / 2.0.0rc2 /
#   ./scripts/prepare-release.sh v2.0.0-rc2    #   v2.0.0-rc2 / 2.0.0
#
# See CONTRIBUTING.md "How to release a new version".

set -euo pipefail

die() { echo "error: $*" >&2; exit 1; }

[ "$#" -eq 1 ] || die "expected exactly one argument (the version), e.g. 2.0.0-rc2"

# Run from the repo root so file paths are reliable.
cd "$(git rev-parse --show-toplevel 2>/dev/null)" || die "not inside a git repository"

# --- Normalize the version into its three forms ---------------------------
# Strip an optional leading "v", then drop hyphens to get the PEP 440 form.
# Only the canonical pre-release spellings (aN / bN / rcN) are accepted; that
# is all this project uses, and rejecting the rest keeps the parsing simple.
ver="${1#v}"
ver="${ver//-/}"
if [[ ! "$ver" =~ ^([0-9]+\.[0-9]+\.[0-9]+)((a|b|rc)([0-9]+))?$ ]]; then
    die "'$1' is not a supported version. Use MAJOR.MINOR.PATCH with an
       optional aN/bN/rcN pre-release, e.g. 2.0.0 or 2.0.0-rc2."
fi
core="${BASH_REMATCH[1]}"          # 2.0.0
pre="${BASH_REMATCH[2]}"           # rc2  (empty for a stable release)
pep440="$ver"                      # 2.0.0rc2   -> pyproject.toml
if [ -n "$pre" ]; then
    display="${core}-${pre}"       # 2.0.0-rc2  -> CHANGELOG heading
else
    display="${core}"              # 2.0.0
fi
tag="v${display}"                  # v2.0.0-rc2 -> git tag

echo "==> Releasing: package $pep440 / tag $tag"

# --- Guard checks ---------------------------------------------------------
branch="$(git rev-parse --abbrev-ref HEAD)"
[ "$branch" != "HEAD" ] || die "detached HEAD; check out a branch first"
echo "==> Current branch: $branch"
if [ -n "$pre" ] && [ "$branch" = "main" ]; then
    echo "    note: pre-releases normally stay on devel, not main (see CONTRIBUTING.md)."
fi

# The CHANGELOG entry is yours to write; assert it exists before we tag.
head_line="$(grep -m1 '^# ' CHANGELOG.md || true)"
case "$head_line" in
    "# $display "*) echo "==> CHANGELOG top entry matches: $head_line" ;;
    *) die "CHANGELOG.md top entry is '$head_line', expected it to start with
       '# $display '. Add the release notes first." ;;
esac

# Refuse to clobber an existing tag.
if git rev-parse -q --verify "refs/tags/$tag" >/dev/null; then
    die "tag $tag already exists"
fi

# --- Bump pyproject.toml + uv.lock ----------------------------------------
echo "==> uv version $pep440 (updates pyproject.toml and uv.lock)"
uv version "$pep440"
uv lock                            # idempotent; ensures the lock is refreshed
uv lock --check                    # prove pyproject.toml and uv.lock agree
echo "==> uv.lock is in sync"

# --- Show what changed and hand back the wheel ----------------------------
echo
echo "==> Changes staged for your review:"
git --no-pager diff --stat -- pyproject.toml uv.lock
echo
echo "Next steps (review the diff above, then run):"
echo
if [ -z "$pre" ] && [ "$branch" != "main" ]; then
    echo "  # stable release: merge $branch to main first, then tag (see CONTRIBUTING.md)"
fi
echo "  git add CHANGELOG.md pyproject.toml uv.lock"
echo "  git commit -m \"release: $tag\""
echo "  git tag $tag"
echo "  git push origin $branch"
echo "  git push origin $tag"
echo
echo "Nothing has been committed, tagged, or pushed."
