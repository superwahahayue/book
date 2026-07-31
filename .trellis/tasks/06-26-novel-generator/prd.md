# Novel Generator

## Goal

Build a from-scratch application that generates long-form novels using a **local LLM**
(Ollama), automatically **continues writing** (定时续写) new chapters on a schedule based
on existing content, and provides a **web interface** for reading and managing multiple novels.

## Confirmed Facts

- Greenfield project (`D:\workspace\personal\book`); only Trellis/cursor scaffolding + AGENTS.md exist.
- Generation backend: **local model via Ollama**, not a cloud LLM API.
- Auto-update meaning: **scheduled continuation** — an in-app scheduler automatically writes
  the next chapter(s) following existing content.
- Delivery: project includes a **web UI** for reading and managing novels.
- Backend stack: **Python + FastAPI**.
- Scope: **multiple novels** (a library), each with independent settings and chapters.
- Scheduling: **in-app scheduler (APScheduler)** with per-novel configurable interval + on/off.
- Users: **single-user, no auth**.
- Model: **assume Ollama is already installed**; model name configurable; do not auto-download.
- Local hardware: Intel Arc 140T iGPU (shared memory) + 32GB RAM, no NVIDIA GPU.
  Default local model: **`gemma4:12b`** (7.6GB, 256K context) — best fit for this hardware.
- Must support **switching between local (Ollama) and online (API-key) models** via a
  provider abstraction; online uses OpenAI-compatible endpoints (base_url + api_key).

## Requirements

### Novel creation / seeding
- User creates a novel by providing: title, genre, premise (short synopsis),
  optional character/world settings, and writing style.
- System generates an outline from the settings, then writes the first chapter.
- Each novel persists: settings, generated outline, and ordered chapters.

### Model providers (local + online switching)
- A provider abstraction supports at least two backends:
  - **Ollama** (local) — host configurable, default model `gemma4:12b`.
  - **OpenAI-compatible online** — `base_url` + `api_key` + model name.
- Online API keys/base_urls are configured via `.env`/config (named backends), NOT stored
  in the DB. Each novel selects a provider + model; a global default applies otherwise.
- Switching a novel between local and online must not change its chapters/settings.

### Generation
- Backend calls the selected provider's model to generate chapter text.
- Default creative language is **Chinese (中文)**: prompts instruct the model to write in Chinese.
- Continuation builds the prompt from: novel settings + outline + a **running summary** of
  prior chapters (plus the tail of the latest chapter) to keep within context limits and
  maintain consistency.
- After a chapter is generated, its summary is produced/updated for use in the next run.
- Generation runs as a background job; the UI does not block while a chapter is written.

### Scheduled continuation (auto-update)
- Each novel has an auto-continue toggle and a configurable interval.
- An in-app scheduler triggers continuation for due novels automatically.
- Manual "continue now" is also available from the UI.
- Concurrent/duplicate generation for the same novel is prevented (a novel generating is locked).

### Web UI
- List novels (library) with status (chapter count, auto on/off, last updated, generating?).
- Create a novel via a settings form.
- Read a novel: view outline and chapters in reading order.
- Manage a novel: toggle auto-continue, set interval, trigger "continue now", edit settings, delete.

### Persistence
- Local storage (SQLite via SQLAlchemy). No external services required.

## Acceptance Criteria

- [ ] `POST` creating a novel with settings persists it and generates an outline + chapter 1.
- [ ] "Continue now" on a novel appends a new chapter consistent with prior content (uses summary + settings).
- [ ] Generation runs in the background; the API returns promptly and UI shows a "generating" state.
- [ ] Enabling auto-continue with an interval causes new chapters to be generated automatically over time without manual action.
- [ ] Disabling auto-continue stops scheduled generation for that novel.
- [ ] A novel already generating cannot be triggered again concurrently (no duplicate chapters).
- [ ] Web UI can: list novels, create a novel, read outline + chapters, toggle auto/interval, continue now, delete.
- [ ] Model name and Ollama host are configurable; a clear error is shown if Ollama is unreachable.
- [ ] A novel can be switched between local (Ollama) and an online (API-key) provider, and the next
      generation uses the selected provider; existing chapters/settings are unchanged.
- [ ] Online provider credentials come from config/.env (not the DB); missing/invalid key yields a clear error.
- [ ] App persists across restarts (SQLite); scheduled jobs resume for enabled novels on startup.
- [ ] README documents setup (Ollama prerequisite, install, run) and how to start the server.

## Out of Scope

- Multi-user accounts, authentication, authorization.
- Auto-downloading or managing Ollama models from the app.
- A full secrets-management UI (API keys are set via `.env`/config, not edited in the browser).
- Publishing/exporting to external platforms (e.g. posting to websites).
- Advanced editing of generated text in a rich editor (basic settings edit only).
- Mobile apps.

## Open Questions

- None blocking. (Front-end approach — server-rendered vs SPA — decided in design.md.)
