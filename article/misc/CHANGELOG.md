# Changelog

AI-assisted change log (major changes only).

## 2026-10-08 — Real Substack drafts; Medium becomes an Import-a-story step

- **Substack** (`adapters/substack.py`): the stub is replaced by real draft creation through the unofficial [python-substack](https://github.com/ma2za/python-substack) client (new `substack` extra, pinned `>=0.10,<0.11`). Footnotes, image captions, LaTeX and local image uploads survive. **Drafts only**: there is no publish path, `SubstackConfig.publish_as_draft` now defaults to `true`, and `false` is refused. A preflight refuses, with every case listed, what the converter would drop silently: tables (or `tables="code"` / a callable renderer), images sharing a paragraph with text, missing local images, raw HTML blocks.
- **Markdown input** (`md_source.py`): `load_article` reads a plain `.md` file: title from front matter or the first `# H1`, slug derived from the title, `assets_dir` set to the file's directory.
- **CLI**: new `draft-substack` command, with `--dry-run` (no credentials) and `--tables`.
- **Medium**: the API is closed to new integrations, so the adapter now sends nothing and returns a new `PublishState.MANUAL` result with the *Import a story* step.
- **Settings**: `SUBSTACK_COOKIES` / `SUBSTACK_COOKIES_PATH` added; the Playwright session and pacing settings are gone.
- **Tests**: offline tests against a fake client that fails on any publish call; a live smoke test, skipped without credentials. The pipeline tests now run the real Substack adapter with the fake client, and the CLI grammar test lists the new command.

## 2026-09-04 — CLI dispatch moves from argh to cw

- **CLI** (`__main__.py`): replaced `argh` (LGPL) with
  [`cw`](https://github.com/i2mint/cw) (MIT, zero runtime dependencies), which
  reproduces argh's grammar bit-for-bit. All 11 recorded argv vectors — help
  surfaces, argh's usage-to-stdout-and-exit-0 no-argument case, four grammar
  errors and both `CommandError` paths — replay byte-identically in stdout,
  stderr and exit code.
- The two `@argh.arg(help=...)` decorators became a `_dispatch_config` mapping:
  `cw` reads `config`, never decorator metadata, so the declaration had to move
  or the help string would have been dropped silently.
- `main()` now **returns** the exit code (`cw.run` returns where argh raised),
  and the `__main__` guard does `raise SystemExit(main())`.
- The hand-written `argcomplete` block is gone — `cw.run` fires completion itself.
- **Tests** (`tests/test_cli.py`): new characterization suite pinning the grammar,
  the migrated help string, the `CommandError` contract and the exit codes.

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
