#!/usr/bin/env bash
#
# Phase 0 exit criterion: prove the guards block rather than decorate.
#
# PLAN.md asks for one pull request carrying three defects, with all three checks
# reporting failure. That was done, as PR #5, and all three did go red. It is not
# sufficient, for two reasons this script exists to close.
#
# 1. A red check is not evidence the check ran. size-guard used to build before
#    measuring, so a missing build.py failed the job having measured nothing -
#    indistinguishable, from the outside, from catching an oversized file. That
#    is not hypothetical: it is what happened on phase-1/registries and
#    phase-2/baseline. So every assertion here greps the job log for the guard's
#    OWN error string, never just conclusion == failure.
#
# 2. One PR carrying three defects shows the three guards fail together. It does
#    not show they fail independently. A guard that goes red because a *different*
#    defect broke its setup looks identical. So three single-defect PRs run
#    first, and each asserts the other two guards stay GREEN. That is the part
#    that proves independence, and it is the part PLAN.md's shape cannot express.
#
# Re-runnable by design. PLAN.md Phase 12 warns that branch protection does not
# always survive a repo transfer, and that protection you believe in but do not
# have is worse than none. Run this again after the transfer.
#
#   ./tools/ci_negative_test.sh                 # against origin's default branch
#   BASE=phase-0/reconcile ./tools/ci_negative_test.sh
#   KEEP=1 ./tools/ci_negative_test.sh          # leave the PRs open for inspection

set -euo pipefail

REPO="${REPO:-$(gh repo view --json nameWithOwner -q .nameWithOwner)}"
BASE="${BASE:-$(gh repo view --json defaultBranchRef -q .defaultBranchRef.name)}"
KEEP="${KEEP:-0}"
TIMEOUT_SECS="${TIMEOUT_SECS:-900}"

# The three guards under test, and the string each prints when it genuinely
# catches its own defect. Matching on these rather than on the conclusion is the
# whole point: it is what tells "the guard caught it" apart from "the job died".
GUARDS=(lint size validate)
declare -A EVIDENCE=(
  [lint]="F821"
  [size]="over the 1 MB cap"
  [validate]="an unpopulated cell must never look rankable"
)

# The four cases, named once, so teardown can derive branch names instead of
# tracking them in a variable.
#
# It used to track them in an array appended to inside `open_pr`, which is called
# as `B=$(open_pr ...)`. Command substitution runs in a subshell, so every append
# landed in a copy and the parent's array stayed empty. Teardown then looped over
# nothing, printed its header, and left four pull requests open - reporting a
# step it had not performed, which is precisely the failure mode this script
# exists to detect. It was caught by verifying the teardown rather than trusting
# the header, which is now done below.
SLUGS=(lint validate size all)
PREFIX="test/ci-negative"
FAILURES=0

say()  { printf '\n\033[1m== %s\033[0m\n' "$*"; }
pass() { printf '  \033[32mPASS\033[0m %s\n' "$*"; }
fail() { printf '  \033[31mFAIL\033[0m %s\n' "$*"; FAILURES=$((FAILURES + 1)); }

cleanup() {
  # A half-finished teardown is worse than a reported one, so nothing in here is
  # allowed to abort on a non-zero status.
  set +e
  if [ "$KEEP" = "1" ]; then
    say "KEEP=1, leaving branches"
    return 0
  fi
  say "Tearing down"
  local b num left
  for slug in "${SLUGS[@]}"; do
    b="${PREFIX}-${slug}"
    num=$(gh pr list -R "$REPO" --head "$b" --state open --json number -q '.[0].number' 2>/dev/null)
    if [ -n "$num" ] && gh pr close -R "$REPO" "$num" --delete-branch >/dev/null 2>&1; then
      echo "  closed #$num and deleted $b"
      continue
    fi
    git push -q origin --delete "$b" >/dev/null 2>&1 && echo "  deleted $b"
  done

  # Verify, do not assume. The script's own thesis applied to itself: state what
  # is actually left, so a silent no-op cannot pass for work done.
  left=$(gh api "repos/$REPO/branches" --jq "[.[].name | select(startswith(\"$PREFIX\"))] | length" 2>/dev/null)
  if [ "${left:-unknown}" = "0" ]; then
    echo "  verified: no ${PREFIX}-* branches remain"
  else
    echo "  WARNING: ${left:-unknown} ${PREFIX}-* branch(es) still present; delete them by hand"
  fi
  # The 2 MB blob is now unreferenced and will be garbage collected. It is
  # deliberately never merged, so it does not enter main's history.
}
trap cleanup EXIT

# ---------------------------------------------------------------- the defects

defect_lint() {
  cat > tools/_negative_lint.py <<'EOF'
"""Deliberately broken. Part of the Phase 0 negative test; never merged."""

import os  # F401: imported but unused


def broken() -> int:
    return undefined_name  # F821: undefined name
EOF
  git add tools/_negative_lint.py
}

defect_validate() {
  # Give three VOID cells a rankable number. The baseline-csv check exists to
  # catch exactly this: an unpopulated cell that looks like a real baseline can
  # be picked up and ranked against.
  python3 - <<'EOF'
import csv, pathlib
p = pathlib.Path("docs/sources/table8_baseline.csv")
rows = list(csv.DictReader(p.open(encoding="utf-8")))
hit = 0
for r in rows:
    if r["kind"] == "VOID" and hit < 3:
        r["value"] = "0.42"
        hit += 1
assert hit == 3, f"expected 3 VOID rows to corrupt, found {hit}"
with p.open("w", encoding="utf-8", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=rows[0].keys())
    w.writeheader()
    w.writerows(rows)
EOF
  git add docs/sources/table8_baseline.csv
}

defect_size() {
  # 2 MB, over the 1 MB cap. Random bytes so it does not compress away.
  head -c 2097152 /dev/urandom > assets_blob.bin
  git add assets_blob.bin
}

# ------------------------------------------------------------------ mechanics

open_pr() {
  local slug="$1" title="$2"; shift 2
  local branch="${PREFIX}-${slug}"

  git checkout -q -B "$branch" "origin/${BASE}"
  for d in "$@"; do "$d"; done
  git commit -q -m "test: negative case ${slug} (must not merge)"
  git push -q -f origin "$branch"
  gh pr create -R "$REPO" --base "$BASE" --head "$branch" \
    --title "CI negative test: ${title}" \
    --body "Deliberately broken. **Must not merge.** Opened and torn down by \`tools/ci_negative_test.sh\`." \
    >/dev/null
  echo "$branch"
}

wait_for_checks() {
  local branch="$1" deadline=$(( SECONDS + TIMEOUT_SECS )) sha pending
  sha=$(git rev-parse "$branch")
  while [ $SECONDS -lt $deadline ]; do
    pending=$(gh api "repos/$REPO/commits/$sha/check-runs" \
      --jq "[.check_runs[] | select(.name==\"lint\" or .name==\"size\" or .name==\"validate\") | select(.status!=\"completed\")] | length" 2>/dev/null || echo 9)
    total=$(gh api "repos/$REPO/commits/$sha/check-runs" \
      --jq "[.check_runs[] | select(.name==\"lint\" or .name==\"size\" or .name==\"validate\")] | length" 2>/dev/null || echo 0)
    [ "$total" -eq 3 ] && [ "$pending" -eq 0 ] && return 0
    sleep 10
  done
  echo "  timed out after ${TIMEOUT_SECS}s waiting for checks on $branch" >&2
  return 1
}

conclusion_of() {
  gh api "repos/$REPO/commits/$(git rev-parse "$1")/check-runs" \
    --jq ".check_runs[] | select(.name==\"$2\") | .conclusion" 2>/dev/null | head -1
}

logs_of() {
  local branch="$1" id
  for id in $(gh run list -R "$REPO" --branch "$branch" --json databaseId -q '.[].databaseId' 2>/dev/null); do
    gh run view -R "$REPO" "$id" --log 2>/dev/null || true
  done
}

# Assert one guard went red FOR ITS OWN REASON, and the others stayed green.
assert_case() {
  local branch="$1" expect_red="$2"
  local logs; logs=$(logs_of "$branch")

  for g in "${GUARDS[@]}"; do
    local got; got=$(conclusion_of "$branch" "$g")
    if [ "$g" = "$expect_red" ]; then
      if [ "$got" != "failure" ]; then
        fail "$branch: $g concluded '$got', expected failure - the guard is decorative"
        continue
      fi
      if grep -qF "${EVIDENCE[$g]}" <<<"$logs"; then
        pass "$branch: $g failed, and its log carries \"${EVIDENCE[$g]}\""
      else
        fail "$branch: $g failed but its log never printed \"${EVIDENCE[$g]}\" - it died before asserting, which is not a catch"
      fi
    else
      if [ "$got" = "success" ]; then
        pass "$branch: $g stayed green (independent of the $expect_red defect)"
      else
        fail "$branch: $g concluded '$got' on a defect that is not its own - the guards are not independent"
      fi
    fi
  done
}

# ----------------------------------------------------------------------- main

say "Negative test against $REPO, base $BASE"
git fetch -q origin "$BASE"
START_REF=$(git rev-parse --abbrev-ref HEAD)
trap 'git checkout -q "$START_REF" 2>/dev/null || true; cleanup' EXIT

open_pr lint     "ruff error only"       defect_lint     >/dev/null
open_pr validate "schema violation only" defect_validate >/dev/null
open_pr size     "2 MB binary only"      defect_size     >/dev/null
open_pr all      "all three defects"     defect_lint defect_validate defect_size >/dev/null
git checkout -q "$START_REF"

B_LINT="${PREFIX}-lint"; B_VALD="${PREFIX}-validate"
B_SIZE="${PREFIX}-size"; B_ALL="${PREFIX}-all"

for b in "$B_LINT" "$B_VALD" "$B_SIZE" "$B_ALL"; do
  say "Waiting on $b"
  wait_for_checks "$b" || FAILURES=$((FAILURES + 1))
done

say "Independence: one defect each, other two guards must stay green"
assert_case "$B_LINT" lint
assert_case "$B_VALD" validate
assert_case "$B_SIZE" size

say "Combined: all three must fail together, each for its own reason"
combined_logs=$(logs_of "$B_ALL")
for g in "${GUARDS[@]}"; do
  got=$(conclusion_of "$B_ALL" "$g")
  if [ "$got" != "failure" ]; then
    fail "combined: $g concluded '$got', expected failure"
  elif grep -qF "${EVIDENCE[$g]}" <<<"$combined_logs"; then
    pass "combined: $g failed, and its log carries \"${EVIDENCE[$g]}\""
  else
    fail "combined: $g failed without printing \"${EVIDENCE[$g]}\""
  fi
done

say "Result"
if [ "$FAILURES" -eq 0 ]; then
  echo "  All guards block, each for its own reason, independently of the others."
  exit 0
fi
echo "  $FAILURES assertion(s) failed. A guard that does not block is decorative."
exit 1
