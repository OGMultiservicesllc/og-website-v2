# Deploy scripts

One-time setup and workflow notes for the Git-based deploy pipeline. See the
main project chat history for the full architecture discussion.

## Status

- `deploy_staging.sh` / `rollback_staging.sh` — written, **not yet run**.
  They assume `/var/www/ogmultiservices`, venv at `.venv/`, systemd unit
  `ogwebsite.service`, git remote `origin/staging`, and a PostgreSQL
  `DATABASE_URL` in the server's `.env`. These match what was described for
  staging but have not yet been confirmed against the real server — the
  first run should be treated as a dry-run walkthrough, not blind trust.
- `deploy_production.sh` — not written yet. Production's actual host/path/
  service/branch have not been confirmed. Do not assume it mirrors staging
  on the same VPS.

## One-time server setup still required (see deploy/SETUP.md once written)

1. `git init` the existing `/var/www/ogmultiservices` directory on the VPS
   and reconcile it with what's already deployed there (no data loss — take
   a full directory + DB backup first).
2. Add `origin` pointing at the private GitHub repo, using the dedicated
   `og_automation` deploy key (write access, this repo only).
3. `chmod +x deploy/*.sh`.
4. Confirm the `ogadmin` user can `sudo systemctl restart ogwebsite.service`
   without a password prompt (or adjust the script to prompt / use a
   narrower sudoers rule for just that one command).

## Running a staging deploy

```
ssh og-staging
cd /var/www/ogmultiservices
./deploy/deploy_staging.sh
```

## Rolling back staging

```
ssh og-staging
cd /var/www/ogmultiservices
git tag -l 'staging-deploy-*'
./deploy/rollback_staging.sh staging-deploy-<timestamp>
```

## Production

Always requires an explicit "Deploy to production" instruction in the
conversation before `deploy_production.sh` (once it exists) is run — never
automatic, never inferred from a successful staging deploy.
