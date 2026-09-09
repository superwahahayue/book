# Implementation Plan — Novel Generator

Backend: Python + FastAPI. Storage: SQLite (SQLAlchemy). Scheduler: APScheduler.
Generation: Ollama (local). UI: Jinja2 + minimal JS.

## Ordered checklist

### 1. Project scaffold
- [ ] `requirements.txt` (fastapi, uvicorn, sqlalchemy, apscheduler, ollama, openai, jinja2, python-dotenv, pydantic-settings).
- [ ] Package layout under `app/` per design.md.
- [ ] `app/config.py` — Settings: DEFAULT_PROVIDER, OLLAMA_HOST, OLLAMA_DEFAULT_MODEL=`gemma4:12b`,
      online backends (name → base_url + api_key + default model), DB_PATH.
- [ ] `.env.example` (incl. online API key placeholders), `.gitignore` (excl. `.env`, db), `README.md` (skeleton).

### 2. Persistence layer
- [ ] `app/db.py` — engine/session, create_all on init.
- [ ] `app/models.py` — `Novel`, `Chapter` per data model.
- [ ] `app/schemas.py` — Pydantic create/update/read models.

### 3. Provider layer (local + online)
- [ ] `app/providers/base.py` — `LLMProvider` interface: `generate(prompt, model, **opts)`, `health()`.
- [ ] `app/providers/ollama_provider.py` — Ollama generate with timeout + clear errors.
- [ ] `app/providers/openai_compat_provider.py` — OpenAI-compatible generate (base_url + api_key).
- [ ] `app/providers/registry.py` — build providers from config; resolve by name; default; validate creds.

### 4. Generation service
- [ ] `app/services/generation.py` — `GenerationManager`:
  - per-novel lock + `is_generating` flag (try/finally).
  - `continue_novel(novel_id)`: resolve provider via registry (novel.provider or default),
    build prompt (premise/settings/outline/running_summary/last-tail), call provider,
    persist Chapter (next index), update running_summary.
  - prompt builders for outline, chapter, and chapter-summary.
- [ ] `app/services/novel_service.py` — CRUD; `create_novel` → generate outline + chapter 1.

### 5. Scheduler
- [ ] `app/scheduler.py` — start scheduler, add/remove/reschedule `novel-<id>` jobs,
  due action calls GenerationManager if idle.
- [ ] On startup: reset stale `is_generating`, register jobs for enabled novels.

### 6. API routes
- [ ] `app/api/routes.py`:
  - `POST /api/novels` create, `GET /api/novels` list, `GET /api/novels/{id}` detail.
  - `PATCH /api/novels/{id}` update settings/auto/interval/provider/model (reschedules job; validates provider).
  - `GET /api/providers` list configured backends + their default models (for UI selection).
  - `DELETE /api/novels/{id}`.
  - `POST /api/novels/{id}/continue` trigger now (409 if generating).
  - `GET /api/novels/{id}/chapters`.

### 7. Web UI
- [ ] `app/web/routes.py` + `app/templates/` : library list, create form, novel reader,
      manage controls incl. provider+model selector (populated from `/api/providers`).
- [ ] `app/static/` minimal CSS + JS polling generating-status / refresh.

### 8. App wiring
- [ ] `app/main.py` — app factory, mount routers/static, startup (DB init, scheduler start, resume), shutdown.

### 9. Docs & manual validation
- [ ] README: prerequisites (Ollama running + a pulled model), install, run, config.

## Validation commands
- [ ] `python -c "import app.main"` imports cleanly.
- [ ] `uvicorn app.main:app` starts; visit `/` lists novels.
- [ ] Create a novel → outline + chapter 1 appear.
- [ ] "Continue now" → new chapter appended; concurrent trigger returns 409.
- [ ] Enable auto with short interval → new chapter appears automatically; disable stops it.
- [ ] Restart app → enabled novels' jobs resume; no stuck "generating".
- [ ] Ollama stopped → friendly error, novel returns to idle.
- [ ] Switch a novel to the online provider (with a valid key) → next "continue now" uses it;
      invalid/missing key → clear error, chapters/settings unchanged.

## Risky areas / rollback points
- Scheduler + async/threading interaction with FastAPI event loop — verify chosen scheduler type
  matches (AsyncIOScheduler with async, or BackgroundScheduler with sync run_in_executor).
- Stuck `is_generating` on crash — startup reset + try/finally mitigate.
- Long prompts exceeding local model context — rely on running_summary; cap included history.
- Greenfield: rollback = revert/delete added files; no data migrations.

## Notes
- MVP keeps Alembic out; schema via create_all. Add migrations later if needed.
- Default chapter length and model name are config-driven for easy tuning.

## 10. Imported sources, reference style, and comics (2026-09)

### Persistence and configuration

- [x] Add upload/image settings and dependencies (`python-multipart`,
      `python-docx`, `httpx`).
- [x] Add `SourceDocument`, `NovelSourceReference`, `Comic`, and `ComicPanel`
      models plus idempotent SQLite migration support for the `Novel` style
      profile snapshot.
- [x] Write source/comic content under the existing mounted data directory;
      never place them in the repository or a public static directory.

### Services and provider boundaries

- [x] Implement text/DOCX parsing, heading splitting, text normalization and
      bounded background source analysis.
- [x] Import a novel into a linear primary chapter path and populate per-chapter
      summaries so `GenerationManager` can continue it immediately.
- [x] Extract an original-writing style profile from bounded source samples;
      include the profile (not raw text) in chapter prompts.
- [x] Add a separate Antigravity image provider and comic service: storyboard
      JSON -> sequential panel generation -> durable image files/statuses.

### API and UI

- [x] Add authenticated upload/status/list APIs, style-reference selection when
      creating a novel, comic job/panel/retry APIs, and authorized image reads.
- [x] Add a dedicated import page from the library, a source-reference step in
      the creation flow, and comic creation/viewing from a selected chapter.
- [x] Add client-side multipart handling and polling for import/style/comic
      statuses; keep existing chapter polling behavior unchanged.

### Validation and deployment

- [x] Test valid and invalid TXT/MD/DOCX imports, primary-path continuation,
      source ownership checks, and style-profile prompt composition.
- [x] Test storyboard parsing and image-response decoding with a mocked image
      client, including one failed panel and retry behavior.
- [x] Build the Vue app and import the FastAPI app; document new environment
      variables and upload-size settings in README/deployment docs.
