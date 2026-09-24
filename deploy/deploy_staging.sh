#!/usr/bin/env bash
# Staging deploy — run ON THE VPS (via SSH), from the app directory.
#
# What it does, in order: backs up the staging DB, refuses to run over
# uncommitted/foreign changes, pulls the target branch, installs deps,
# runs migrations, restarts the service, and smoke-tests the result.
# Never touches production — that is a separate script, run only on
# explicit human confirmation.
#
# Assumptions (confirm/adjust once we've reconciled the real VPS layout):
#   - App directory:      /var/www/ogmultiservices
#   - Python venv:        /var/www/ogmultiservices/.venv
#   - systemd service:    ogwebsite.service
#   - Git remote/branch:  origin/staging
#   - .env already exists on the server with a real PostgreSQL DATABASE_URL
set -euo pipefail

APP_DIR="/var/www/ogmultiservices"
VENV_DIR="$APP_DIR/.venv"
SERVICE="ogwebsite.service"
BRANCH="staging"
BACKUP_DIR="$APP_DIR/backups/pre_deploy"
HEALTH_URL="https://staging.ogmultiservicesllc.com/"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

cd "$APP_DIR"

echo "==> [1/7] Pre-flight: checking for local/uncommitted changes"
if [ ! -d .git ]; then
    echo "ERROR: $APP_DIR is not a git working tree yet."
    echo "       This script only handles ONGOING deploys to an already-reconciled repo."
    echo "       Run the one-time reconciliation procedure first (see deploy/README.md)."
    exit 1
fi
if [ -n "$(git status --porcelain)" ]; then
    echo "ERROR: the server working tree has uncommitted changes. Refusing to deploy"
    echo "       over unknown local state. Inspect with 'git status' / 'git diff' first."
    exit 1
fi

echo "==> [2/7] Backing up the staging database"
mkdir -p "$BACKUP_DIR"
# Read DATABASE_URL with python-dotenv (the same parser the app itself uses via
# load_dotenv() in wsgi.py) rather than `source .env`. .env is a dotenv file, not
# shell script: values containing spaces, '#', quotes, or '$' are valid dotenv but
# break or silently truncate under `source`. This pulls exactly one value into a
# local shell variable — the rest of .env is never exported into this process.
DB_URL="$("$VENV_DIR/bin/python" -c "
from dotenv import dotenv_values
v = dotenv_values('$APP_DIR/.env').get('DATABASE_URL', '')
print(v)
")"
if [[ "$DB_URL" == postgresql* ]]; then
    pg_dump "$DB_URL" > "$BACKUP_DIR/staging_${TIMESTAMP}.sql"
    echo "    backup written: $BACKUP_DIR/staging_${TIMESTAMP}.sql"
    # Keep the last 20 backups only, so this directory doesn't grow unbounded.
    ls -1t "$BACKUP_DIR"/staging_*.sql 2>/dev/null | tail -n +21 | xargs -r rm --
elif [ -z "$DB_URL" ]; then
    echo "ERROR: DATABASE_URL not found in .env — aborting before touching anything."
    exit 1
else
    echo "    DATABASE_URL is not PostgreSQL — skipping pg_dump (unexpected on staging, check .env)"
fi
unset DB_URL

echo "==> [3/7] Fetching and checking out latest $BRANCH"
BEFORE_COMMIT="$(git rev-parse HEAD)"
git fetch origin "$BRANCH"
git checkout "$BRANCH"
git reset --hard "origin/$BRANCH"
AFTER_COMMIT="$(git rev-parse HEAD)"
echo "    $BEFORE_COMMIT -> $AFTER_COMMIT"

if [ "$BEFORE_COMMIT" == "$AFTER_COMMIT" ]; then
    echo "    no new commits — nothing to deploy. Exiting."
    exit 0
fi

echo "==> [4/7] Installing/updating Python dependencies"
"$VENV_DIR/bin/pip" install -q -r requirements.txt

echo "==> [5/7] Running database migrations"
export FLASK_APP=wsgi.py
"$VENV_DIR/bin/flask" db upgrade

echo "==> [6/7] Restarting $SERVICE"
sudo systemctl restart "$SERVICE"
sleep 3
if ! systemctl is-active --quiet "$SERVICE"; then
    echo "ERROR: $SERVICE failed to start. Last 40 log lines:"
    journalctl -u "$SERVICE" -n 40 --no-pager
    exit 1
fi

echo "==> [7/7] Smoke test"
# -L: the site's own root "/" is a normal 301 to "/en/" (bilingual routing) — that redirect itself is a
# healthy response, not a failure; only a final non-200 (after following it) is worth flagging.
HTTP_CODE="$(curl -s -L -o /dev/null -w '%{http_code}' --max-time 10 "$HEALTH_URL" || echo "000")"
if [ "$HTTP_CODE" != "200" ]; then
    echo "WARNING: $HEALTH_URL returned HTTP $HTTP_CODE (expected 200)."
    echo "Last 30 log lines:"
    journalctl -u "$SERVICE" -n 30 --no-pager
    exit 1
fi

git tag "staging-deploy-${TIMESTAMP}" "$AFTER_COMMIT"
echo ""
echo "==> Deploy OK. $HEALTH_URL -> 200. Tagged staging-deploy-${TIMESTAMP} ($AFTER_COMMIT)."
