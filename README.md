# OG Multiservices — Website V2

Rebuild of the OG Multiservices LLC website. Built step by step alongside the existing
production site (`../OG Website`), which is untouched by this project.

## Running locally

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python wsgi.py
```

Then open http://localhost:5001/

## Structure

- `app/` — application package (factory pattern)
  - `blueprints/public/` — public marketing pages
  - `templates/` — Jinja templates (Tailwind CDN for styling)
  - `i18n.py` — single source of truth for EN/ES text and supported languages
- `config.py` — environment-based configuration
- `wsgi.py` — entry point

## Build log

1. **Foundation** — project scaffold, bilingual routing (`/en/...` / `/es/...`), base layout,
   home/services/courses/about/contact pages, login placeholder.
