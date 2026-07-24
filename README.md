# article

Tools to semi-automate the publication of articles.

Write an article **once** as a JSON file. Publish it to a **primary** platform
(Substack), then **syndicate** it to secondary platforms (Medium, Dev.to,
Hashnode) — each pointing its canonical URL back to the primary, so you get
cross-platform reach without an SEO duplicate-content penalty.

```bash
pip install article
```

## The single source of truth

The Substack public URL captured in phase 1 is the SSOT. It is stored
(keyed by article slug) and injected as `canonical_url` into every secondary
platform in phase 2, so each emits `<link rel="canonical" href="…">` pointing
back at the original.

```
author.json ──► publish-primary ──► Substack ──► live URL ─┐
                                                           │ stored as canonical_url
                                                           ▼  (pipeline_state.json, by slug)
                          syndicate-secondary ──► Medium / Dev.to / Hashnode
                                                  each canonical → Substack URL
```

The two phases are deliberately separate commands so you can syndicate later
(e.g. `+3 days`) on your own schedule.

## Two-command flow

```bash
# 1. Author once, then publish to the primary (records the canonical URL):
python -m article publish-primary article.json

# 2. Later — syndicate everywhere, injecting the canonical URL for SEO:
python -m article syndicate-secondary article.json

# Subset / machine-readable output:
python -m article syndicate-secondary article.json --platforms medium,dev_to --json-out
```

After `pip install`, the `article` console script is equivalent
(`article publish-primary article.json`).

## The article JSON

One standardized file is the single source of truth for content **and** which
platforms to publish to — a platform is published only if it appears under
`platforms` (see [`examples/article.example.json`](examples/article.example.json)):

```json
{
  "title": "Designing an SSOT Publishing Pipeline",
  "slug": "ssot-publishing-pipeline",
  "content_markdown": "# Designing an SSOT Publishing Pipeline\n\n…",
  "tags": ["python", "automation", "seo"],
  "platforms": {
    "substack": { "publish_as_draft": false },
    "medium":   { "publish_as_draft": true },
    "dev_to":   { "publish_as_draft": true },
    "hashnode": { "publish_as_draft": true }
  }
}
```

## Configuration

Secrets and settings load from `.env` (see
[`.env.example`](.env.example)) — copy it and fill in what you use:

```bash
cp .env.example .env
```

Every platform is optional; omit a platform's secrets (or its `platforms`
entry) to skip it.

## Using it from Python

The CLI is a thin wrapper over the same functions, so everything is callable
programmatically:

```python
import asyncio
from article import load_article, publish_primary, syndicate_secondary

art = load_article("article.json")
asyncio.run(publish_primary(art))  # phase 1 → records canonical_url
asyncio.run(syndicate_secondary(art))  # phase 2 → canonical SEO everywhere
```

## Adding a platform

Adapters are registered in an open-closed registry. To add a platform, write
one async function satisfying the `PublishAdapter` protocol and register it —
no core changes:

```python
from article import register_adapter, PublishResult
from article.util import require_canonical_url


@register_adapter("my_platform")
async def publish(article, *, canonical_url, config, secrets):
    require_canonical_url("my_platform", canonical_url)  # SSOT is never optional
    # … call the platform's API, injecting canonical_url …
    return PublishResult.success("my_platform", url="…", canonical_url=canonical_url)
```

## Architecture

| Layer | Module | Responsibility |
|------|--------|----------------|
| Schema + config | `article/config.py` | Pydantic `Article` model, `.env` `Settings`, `load_article` (friendly errors) |
| Vocabulary | `article/base.py` | `PublishResult`, `RunSummary`, platform names, exceptions |
| State store | `article/state.py` | `MutableMapping` facade over JSON, keyed by slug (the SSOT) |
| Registry | `article/registry.py` | `PublishAdapter` protocol + open-closed registry |
| Engine | `article/engine.py` | Orchestrates phase 1 → phase 2; canonical handoff; graceful errors |
| Adapters | `article/adapters/*` | One module per platform (config + secrets injected) |
| CLI | `article/__main__.py` | `argh` dispatch of the two commands |

> **Status:** the layers above are complete and tested; each adapter's actual
> network / Playwright call is a clearly-marked `TODO` stub that returns a typed
> placeholder result. Payload field names are verified against each platform's
> live API (`canonicalUrl` / `canonical_url` / `originalArticleURL`).
