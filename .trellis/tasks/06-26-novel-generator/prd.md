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

## Imported-source and comic extension (2026-09)

### Goal

Let an authenticated user bring an existing novel into the product in three
connected ways: continue it as a story tree, use its high-level writing
characteristics as a reference for an original new story, and turn selected
chapters into an illustrated comic storyboard.

### Confirmed scope for the first release

- Import `.txt`, `.md`, and `.docx` files up to a configurable size limit.
- Detect common Chinese chapter headings (`第…章`, Markdown headings); fall back
  to one chapter when no headings are found.
- Import chapters as the primary linear path of a normal `Novel`, so the
  existing director/continuation flow continues from its last chapter.
- Store the source document, a bounded cross-book continuity profile, and a
  model-generated style profile where requested; never put an entire imported
  book into every generation prompt. The continuity profile samples the full
  chapter range so middle-plot developments remain available offline.
- A new story may select a ready style reference. Its profile is copied onto
  the new novel as a snapshot and guides future generation alongside the
  user's own instructions.
- Style analysis describes broad attributes (viewpoint, rhythm, dialogue,
  imagery, emotional pacing, and avoidances) and asks the model for original
  output rather than verbatim or near-verbatim reproduction.
- Generate a real, illustrated comic for one selected chapter at a time:
  first produce a 4–8 panel storyboard, then generate one image per panel.
  Default output is a colorful anime-inspired 16:9 panel at standard quality.
- Image files remain in the mounted application data directory and are served
  only through owner-authorized API endpoints.

### Acceptance Criteria

- [ ] A user can upload a valid `.txt`, `.md`, or `.docx` file, see progress,
      and open the resulting imported novel when processing finishes.
- [ ] Imported multi-chapter content becomes one primary chapter path; its last
      node can be continued with the existing "续写故事" action.
- [ ] The import workflow returns a clear per-file error for unsupported files,
      invalid encodings, unsafe/oversized content, empty content, or processing
      failures. Style-reference analysis separately reports model failures.
- [ ] A user can upload an authorized reference text, wait for style analysis,
      and choose it from the new-story form.
- [ ] The selected style profile is persisted on the created novel and is used
      by future chapter prompts even if the original reference is later removed.
- [ ] A user can request a comic from an accessible chapter, review generated
      panels, and receive individual image/error status without blocking the UI.
- [ ] Comic images survive a container recreation because they are written
      below the mounted `data/` directory; another user cannot read them.
- [ ] A user can erase retained source prose without deleting an already-created
      novel; deleting a novel also removes its generated panel files.

### Explicit non-goals for this release

- EPUB/PDF parsing, OCR, and automatic whole-book comic conversion.
- Exact imitation of an identified living author's unique style.
- Cross-panel character-reference image editing; this can be added later using
  Antigravity's image-edit endpoint.
