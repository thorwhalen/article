# Changelog

AI-assisted change log (major changes only).

## 2026-06-21 — Initial pipeline scaffold (0.1.0)

Built the full SSOT publishing pipeline skeleton, fully wired and importable:

- **Domain schema** (`config.py`): Pydantic v2 `Article` + per-platform config
  models, `Settings` (`.env`) facade, and `load_article` with friendly,
  field-keyed validation errors.
- **State store** (`state.py`): `JsonStateStore`, a `MutableMapping` facade over
  a JSON backend keyed by article slug; holds the canonical-URL SSOT.
- **Registry** (`registry.py`): `PublishAdapter` Protocol + open-closed,
  decorator-based adapter registry.
- **Engine** (`engine.py`): async orchestration of phase 1 (publish-primary →
  capture canonical_url) → phase 2 (syndicate-secondary → inject canonical_url),
  with per-platform graceful failure and a structured `RunSummary`.
- **Adapters** (`adapters/`): Substack (Playwright async), Medium, Dev.to,
  Hashnode. Network/browser bodies are clearly-marked TODO stubs returning typed
  placeholder results; payload shaping uses field names **verified against each
  platform's live API docs** (`canonicalUrl` / `canonical_url` /
  `originalArticleURL`; Dev.to V1 tags-as-string; Hashnode raw-PAT auth +
  `publishPost`/`createDraft` split).
- **CLI** (`__main__.py`): `argh` dispatch of `publish-primary` /
  `syndicate-secondary`, sharing the engine functions (dispatch-to-interface).
