#!/usr/bin/env bash
# Roll staging back to a previous deploy tag. Run ON THE VPS.
#
# Usage: rollback_staging.sh staging-deploy-20260924_153000
# List available tags with: git tag -l 'staging-deploy-*'
#
# Restores the code to that tag and restarts the service. Does NOT
# automatically restore the database backup taken at that deploy — a schema
# rollback is only safe to automate when the migration is known-reversible.
# If the deploy being rolled back included a migration, restore the matching
# backups/pre_deploy/staging_<timestamp>.sql by hand after reading it, then
# re-run this script.
set -euo pipefail

APP_DIR="/var/www/ogmultiservices"
VENV_DIR="$APP_DIR/.venv"
SERVICE="ogwebsite.service"

if [ $# -ne 1 ]; then
    echo "Usage: $0 <staging-deploy-TAG>"
    echo "Available tags:"
    (cd "$APP_DIR" && git tag -l 'staging-deploy-*' | tail -10)
    exit 1
fi

TARGET_TAG="$1"
cd "$APP_DIR"

if ! git rev-parse "$TARGET_TAG" >/dev/null 2>&1; then
    echo "ERROR: tag '$TARGET_TAG' not found."
    exit 1
fi

echo "==> Rolling back to $TARGET_TAG ($(git rev-parse "$TARGET_TAG"))"
git checkout "$TARGET_TAG"

echo "==> Re-installing dependencies for this commit"
"$VENV_DIR/bin/pip" install -q -r requirements.txt

echo "==> Restarting $SERVICE"
sudo systemctl restart "$SERVICE"
sleep 3
if ! systemctl is-active --quiet "$SERVICE"; then
    echo "ERROR: $SERVICE failed to start after rollback. Last 40 log lines:"
    journalctl -u "$SERVICE" -n 40 --no-pager
    exit 1
fi

echo ""
echo "==> Rollback OK. Currently on detached HEAD at $TARGET_TAG."
echo "    Once staging is fixed forward, remember to reset the 'staging' branch"
echo "    pointer explicitly (git checkout staging && git reset --hard $TARGET_TAG"
echo "    only if you intend to discard the bad commits, or fix forward with a"
echo "    new commit instead)."
