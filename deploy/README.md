# Deploy scripts

## Key architecture (two separate SSH keys, different purposes)

1. **`og_automation`** (already generated, on the local PC) — PC → VPS staging
   only. Used to SSH in and run commands/scripts. Goes into
   `~ogadmin/.ssh/authorized_keys` on the VPS.
2. **A second, dedicated key, generated ON the VPS itself** — VPS → GitHub
   only, so the server can `git fetch`/`git pull` the private repo. Never
   leaves the VPS; its *public* half is added to GitHub as a **read-only**
   Deploy Key (write access only if a concrete future need requires the VPS
   to push, which is not expected). These two keys are never the same key
   and never copied between machines.

## Status

- `deploy_staging.sh` / `rollback_staging.sh` — written, **not yet run**.
- `reconcile_staging.sh` — written, **not yet run**. One-time, non-destructive
  bootstrap (see "Reconciliation plan" below).
- `deploy_production.sh` — not written yet. Pending confirmed production
  host/path/service details, and always gated on an explicit
  "Deploy to production" instruction regardless of what staging automation
  is allowed to do.

## Reconciliation plan — turning the live staging directory into a git repo

`/var/www/ogmultiservices` currently has a working site on it and is **not**
a git repository. This is done in reviewed stages, never one blind command,
and nothing here has been executed against the VPS yet.

**Stage 0 — read-only audit (before touching anything).**
Confirm, over SSH, read-only:
- `flask db current` on the server matches the local head (`8b3bd7e6bbd8`) —
  cross-checks what the user already reported.
- Where `COURSE_MEDIA_DIR` (and any other persistent-data path) actually
  points on staging, to confirm it's outside `/var/www/ogmultiservices` as
  `config.py`'s `validate_for_production()` requires — but that check only
  runs when `APP_ENV=production`, and staging likely runs `APP_ENV=staging`,
  so it is **not proven yet** and must be confirmed, not assumed.
- A file listing (`find /var/www/ogmultiservices -type f`) to compare against
  the local repo and catch any server-only hotfix that never made it back
  into the local copy.

**Stage 1 — local snapshot commit (`reconcile_staging.sh`).**
Copies `.gitignore`/`.gitattributes` into place first (so `.env`, `instance/`,
uploads, `*.db` are excluded from the very first commit), then `git init` +
one commit that captures **exactly** what's currently live, tagged
`pre-git-migration-snapshot`. This is a safety net / rollback point, not a
step toward changing anything. The script prompts for confirmation before
committing and shows what will be excluded vs. captured first. It refuses to
run if `.git` already exists (no double-run risk).

**Stage 2 — reviewed diff, no merge yet (manual, run together, not scripted).**
Deliberately NOT automated — this is the step where any real drift between
"what's live" and "what's in GitHub" has to be looked at by a human before
anything merges:
```
git remote add origin <github-url>
git fetch origin
git diff --stat HEAD origin/staging
git diff HEAD origin/staging          # full diff, read before proceeding
```
If this diff shows only the expected difference (GitHub has the payments
work + the two bugfixes that staging's *code* doesn't have yet, even though
staging's *database* is already migrated to `8b3bd7e6bbd8`) — proceed to
Stage 3. If it shows anything unexpected (a file that exists live but was
never in the local repo, or content that differs from what's expected),
stop and resolve that first.

**Stage 3 — merge (only after Stage 2 is reviewed and approved).**
```
git merge origin/staging
```
An ordinary, invertible git merge on top of the Stage-1 snapshot — never a
`reset --hard`, so nothing is silently discarded; anything unexpected surfaces
as a merge conflict instead of a silent overwrite. This is also the first
point where the **code** for the payments work / `og_form.js` fix /
`app/tax/seed.py` actually lands on disk — the database side of the payments
migration is already done (staging is at `8b3bd7e6bbd8`), so this step is
pure code sync with **no pending migration** (`flask db upgrade` will be a
no-op the first time `deploy_staging.sh` runs afterward, per the current
single-head check against the local migration chain).

**Stage 4 — only then, `deploy_staging.sh`.**
By this point the directory is a real git repo with `origin` configured and
`HEAD` already equal to `origin/staging`, which is exactly the state
`deploy_staging.sh` assumes. Nothing about Stages 0-3 restarts the service,
runs a migration, or touches `.env`/uploads/the database.

## Persistent data across deploys/rollbacks

- `.env` — gitignored everywhere (root repo and the VPS copy placed before
  Stage 1); no git operation in this plan ever reads, writes, or moves it.
- Uploads / media (`COURSE_MEDIA_DIR`, customer documents, etc.) — per
  `config.py`, these are meant to live outside the deployed code directory
  entirely; Stage 0 confirms this is actually true on staging before we rely
  on it. If it turns out something persistent currently lives *inside*
  `/var/www/ogmultiservices`, that gets moved out and reconfigured **before**
  Stage 1, not discovered by accident during a later deploy.
- Database — never touched by git at all; `deploy_staging.sh` only ever runs
  forward migrations (`flask db upgrade`) and takes a `pg_dump` backup first.

## Rollback never runs a destructive DB downgrade

`rollback_staging.sh` only does `git checkout <tag>` + reinstall deps +
restart the service. It contains no Alembic/Flask-Migrate command of any
kind — confirmed by inspection, not by assumption. If a deploy being rolled
back included a migration, the database is restored by hand from the
matching `backups/pre_deploy/staging_<timestamp>.sql` (reviewed first, never
applied blind), exactly because an automatic schema downgrade is not always
safe or even defined for every migration.

## Running a staging deploy (only after the reconciliation plan above)

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
