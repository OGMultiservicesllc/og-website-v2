#!/usr/bin/env bash
# ONE-TIME bootstrap: turn the EXISTING, already-deployed /var/www/ogmultiservices
# into a git working tree, without deleting, overwriting, or touching a single
# site file, the database, or the running service.
#
# What this script does — and ONLY this:
#   1. `git init` (creates .git/, touches nothing else)
#   2. `git add -A` + one commit, capturing the exact current state as a permanent
#      snapshot/rollback point — this commit is the safety net if anything below
#      ever needs to be undone.
#   3. Tags that commit `pre-git-migration-snapshot`.
#
# What this script deliberately does NOT do:
#   - It does NOT add a remote.
#   - It does NOT fetch from GitHub.
#   - It does NOT merge, reset, checkout, or overwrite anything.
#   - It does NOT restart the service or touch the database.
# Connecting to the real repo and reconciling any drift is a separate, reviewed
# step — see deploy/README.md "Reconciliation, step 2" — precisely so that step
# can be reviewed as an ordinary diff before anything is merged, instead of being
# hidden inside a script that decides for you.
#
# Prerequisites (placed here by hand or scp BEFORE running this script):
#   - .gitignore and .gitattributes already present in this directory, identical
#     to the ones in the repo (so .env, instance/, uploads, etc. are excluded
#     from the very first `git add`, not accidentally captured and then removed
#     in a later commit).
set -euo pipefail

APP_DIR="/var/www/ogmultiservices"
cd "$APP_DIR"

if [ -d .git ]; then
    echo "ERROR: $APP_DIR is already a git repository. This script is only for the"
    echo "       one-time bootstrap and refuses to run twice. Nothing was touched."
    exit 1
fi

if [ ! -f .gitignore ] || [ ! -f .gitattributes ]; then
    echo "ERROR: .gitignore and/or .gitattributes are not present in $APP_DIR yet."
    echo "       Copy them here first (matching the repo's root versions) so the"
    echo "       very first snapshot commit already excludes .env, instance/,"
    echo "       uploads, and *.db. Nothing was touched."
    exit 1
fi

git init -q .

echo "==> Files that will be EXCLUDED from the snapshot (sanity check before we commit):"
git status --porcelain --ignored=matching | grep '^!!' | awk '{print "    ignored: " $2}' | head -50
echo "    (showing up to 50; re-run 'git status --ignored' manually to see the rest)"

echo ""
echo "==> Files that WILL be captured in the snapshot commit:"
git add -A
git status --porcelain | wc -l | xargs echo "    total files staged:"

echo ""
read -r -p "Proceed with the snapshot commit? [y/N] " CONFIRM
if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
    echo "Aborted. Removing the .git directory created by 'git init' (nothing else was touched)."
    rm -rf .git
    exit 1
fi

git commit -q -m "Snapshot: staging as currently deployed, before adopting git

This commit captures the exact state of /var/www/ogmultiservices at the moment
it was converted to a git working tree. It exists as a permanent rollback point
and audit trail — not as the start of normal history."
git tag pre-git-migration-snapshot

echo ""
echo "==> Snapshot commit created and tagged 'pre-git-migration-snapshot'."
echo "    Nothing else was changed. Next: see deploy/README.md for the reviewed"
echo "    diff-then-merge step that connects this to the real GitHub history."
