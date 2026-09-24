# Production media storage — `COURSE_MEDIA_DIR`

**What lives here:** every customer document upload (Case Document Vault), every "Files from OG" release,
all Academy course media (videos/slides/audio/images), and generated certificate files. Despite the name
(inherited from the Academy feature that introduced it first), this single directory is the storage
location for **every** file this application persists to disk. There is no database copy of the file
bytes and no secondary storage — if this directory is lost, that data is gone.

## The default is NOT safe for production

`config.py` defaults `COURSE_MEDIA_DIR` to `<repo>/instance/course_media` — a path **inside** the deployed
code checkout. That is fine for local development, but in production it is a real risk: any redeploy
strategy that replaces the code directory (a fresh `git clone`, `rsync --delete`, a container image
rebuild without a mounted volume, etc.) would silently destroy every customer's uploaded documents.

`config.py`'s `validate_for_production()` refuses to start the application when `APP_ENV=production` and
`COURSE_MEDIA_DIR` is unset or still equal to that in-repo default — this is a deliberate startup guard,
not a bug. Production must set `COURSE_MEDIA_DIR` explicitly.

## What to configure in production

Set the environment variable to an absolute path **outside** the code checkout, on storage that:

1. **Survives a redeploy.** A `git pull`/fresh clone/container rebuild of the application code must never
   touch this path. A separate directory on the same VPS (e.g. `/var/og/course_media`) is sufficient —
   it just must not live under wherever the application code itself is checked out.
2. **Is writable by the user the app runs as** (the Gunicorn worker's OS user needs read/write access).
   The application creates this directory automatically on startup if it doesn't exist
   (`os.makedirs(..., exist_ok=True)` in `app/__init__.py`), but the *parent* directory must already be
   writable by that user.
3. **Is included in your backup plan, separately from PostgreSQL.** A database backup alone is not a
   complete backup of this application — this directory must be backed up on the same cadence (e.g. a
   nightly `rsync`/`tar` to off-VPS storage, alongside your `pg_dump`/WAL archiving strategy). This is not
   optional: it holds real customer identity documents, tax documents, and immigration paperwork that
   cannot be regenerated if lost.

Example production `.env` entry:

```
COURSE_MEDIA_DIR=/var/og/course_media
```

## What NOT to do

- Do not leave `COURSE_MEDIA_DIR` unset in production — the app will refuse to start (see above).
- Do not point it at a path inside the deployed code directory, even a different subfolder — the whole
  point is independence from code deploys.
- Do not move or delete the current development files under `instance/course_media` to "fix" this — that
  directory continues to work exactly as before for local development; this guidance only applies to the
  production environment variable.
