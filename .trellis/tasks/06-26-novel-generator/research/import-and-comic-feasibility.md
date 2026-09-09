# Import and comic feasibility research

Date: 2026-09-09

## Existing project findings

- `Chapter.parent_id` and `Chapter.is_primary` already represent a primary
  continuation path. Imported chapters can therefore reuse the existing
  director-mode continuation endpoint instead of creating a separate sequel
  subsystem.
- `GenerationManager` prompts with summaries along the selected path and the
  tail of the parent chapter. Import must backfill summaries for reliable
  continuation.
- `Novel.style` is short free text; a reusable source document and a copied
  profile snapshot are required for safe, bounded style reference context.
- Auth is already enforced for novels via `require_novel_access`; new source
  and comic resources must use equivalent owner checks.

## Antigravity image interface

Antigravity Manager documents an OpenAI-compatible image endpoint:

- `POST /v1/images/generations` for text-to-image;
- `POST /v1/images/edits` for later reference-image/image-edit support;
- `gemini-3-pro-image`, an aspect ratio/size, `quality`, and
  `response_format=b64_json` are supported request options.

Source: <https://github.com/lbjlaq/Antigravity-Manager/blob/main/docs/gemini-3-image-guide.md>

The current `GeminiProvider` returns only `response.text`, so it is unsuitable
for persisting binary panel output. The feature needs a distinct image client.

## First-release decisions

- Parse TXT, Markdown and DOCX; defer EPUB/PDF/OCR.
- Create 4–8 panel comics from a selected chapter, rather than an unbounded
  whole-book image task.
- Store original writing as a bounded, high-level profile for prompts. Demand
  original output and avoid exact reproduction or named-author imitation.
- Process panel images sequentially and save per-panel failures, because image
  quotas/capacity may be more constrained than text generation.
