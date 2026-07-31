# Design — Novel Generator

## Architecture overview

Single Python service (FastAPI) that serves both a JSON API and a server-rendered web UI.
Background generation and scheduling run in-process. Data persists in local SQLite.

```
[Browser] --HTTP--> [FastAPI app]
                       |- web routes (Jinja2 templates + minimal JS polling)
                       |- API routes (JSON)
                       |- service layer (novel/generation logic)
                       |     |- OllamaClient ----> [Ollama local server]
                       |     |- GenerationManager (background tasks + per-novel lock)
                       |- APScheduler (interval jobs) --triggers--> service layer
                       |- SQLAlchemy models ----> [SQLite file]
```

### Front-end approach
Server-rendered **Jinja2 templates** + small amount of vanilla JS for polling the
"generating" status and refreshing chapter lists. Rationale (first principles): single-user
local app needs minimal UI; a full SPA adds a second toolchain/build for no real benefit.
A JSON API is still exposed so a richer front-end could be added later.

## Components / boundaries

- `app/main.py` — FastAPI app factory, startup/shutdown (init DB, start scheduler, resume jobs).
- `app/config.py` — settings via env / `.env`: default provider, Ollama host + default model
  (`gemma4:12b`), and named online backends (base_url + api_key + default model). API keys
  live here only, never in the DB.
- `app/db.py` — SQLAlchemy engine/session setup, SQLite.
- `app/models.py` — ORM models: `Novel`, `Chapter`.
- `app/schemas.py` — Pydantic request/response models.
- `app/providers/base.py` — `LLMProvider` interface: `generate(prompt, model, **opts) -> str`,
  plus `health()` for connectivity checks.
- `app/providers/ollama_provider.py` — local Ollama implementation (host from config).
- `app/providers/openai_compat_provider.py` — online OpenAI-compatible implementation
  (base_url + api_key + model).
- `app/providers/registry.py` — builds providers from config (named backends), resolves a
  novel's `provider` name to an instance; supplies the default.
- `app/services/novel_service.py` — CRUD for novels/chapters; outline generation.
- `app/services/generation.py` — `GenerationManager`: build prompt, call model, persist chapter,
  update running summary; per-novel in-memory lock + DB `is_generating` flag.
- `app/scheduler.py` — APScheduler setup; add/remove/reschedule per-novel jobs; due-check.
- `app/api/routes.py` — JSON API endpoints.
- `app/web/routes.py` — HTML page routes.
- `app/templates/` , `app/static/` — Jinja2 templates + CSS/JS.

## Data model

`Novel`
- `id` (pk)
- `title`, `genre`, `premise`, `settings` (text: characters/world), `style`
- `outline` (text, generated)
- `provider` (str; named backend, e.g. `ollama` / `openai`; nullable → config default)
- `model` (nullable; falls back to the provider's default model)
- `auto_continue` (bool, default false)
- `interval_minutes` (int, default e.g. 360)
- `is_generating` (bool, default false)
- `running_summary` (text; rolling synopsis of story so far)
- `created_at`, `updated_at`

`Chapter`
- `id` (pk), `novel_id` (fk), `index` (int, 1-based order)
- `title` (nullable), `content` (text)
- `summary` (text; per-chapter summary feeding running_summary)
- `created_at`

## Generation flow (contract)

1. Acquire per-novel lock; if locked, reject ("already generating").
2. Set `is_generating = true`.
3. Build prompt:
   - System: role + style + genre.
   - Context: premise, settings, outline, `running_summary`, tail of last chapter.
   - Instruction: write the next chapter (target length), stay consistent, advance plot per outline.
4. Resolve the novel's provider via the registry (novel.provider or config default) and call
   it with the chosen model. On error: log, set `is_generating=false`, surface message.
5. Persist new `Chapter` (next index).
6. Generate a short summary of the new chapter; append/condense into `running_summary`.
7. Set `is_generating=false`, `updated_at=now`, release lock.

Outline generation at creation uses settings to produce a chapter-by-chapter outline, then
chapter 1 is generated via the same flow (running_summary empty initially).

## Scheduling

- APScheduler `BackgroundScheduler` (or AsyncIOScheduler) started on app startup.
- For each novel with `auto_continue=true`, an interval job (`interval_minutes`) is registered.
- Job action: if novel not currently generating, run continuation in a worker.
- Toggling auto / changing interval add/removes/reschedules the job.
- On startup, jobs are (re)created for all enabled novels (resume after restart).
- Job id convention: `novel-<id>`.

## Concurrency & safety

- Per-novel `asyncio.Lock` / threading lock in `GenerationManager` prevents overlapping runs.
- DB `is_generating` flag is the source of truth the UI reads; reset stale flags on startup.
- Ollama calls have a timeout; failures never leave `is_generating` stuck (try/finally).

## Error handling

- Ollama unreachable / model missing → 502-style API error + UI banner with guidance.
- Online provider: missing/invalid api_key or unreachable base_url → clear error; novel idle.
- Generation failure recorded in logs; novel returns to idle state.

## Provider switching

- Config defines named backends, e.g. `ollama` (local) and `openai` (online, OpenAI-compatible).
- A novel stores `provider` (name) + `model`. The UI lets the user pick from configured
  backends and enter a model name; switching only changes future generations.
- Registry validates that a selected provider exists/has credentials before saving or generating.

## Tradeoffs

- SQLite + in-process scheduler chosen for single-user simplicity; not horizontally scalable
  (acceptable per scope).
- Running-summary approach keeps prompts bounded vs feeding full text (which breaks on long
  novels and local context limits).

## Operational notes

- Config via `.env` / env vars; sensible defaults.
- Run: `uvicorn app.main:app`. README documents Ollama prerequisite.
- No rollback migrations needed for greenfield; schema created on startup (or Alembic optional, out of scope for MVP).
