"""End-to-end tests for the two-phase, canonical-URL SSOT pipeline.

These exercise every layer above the network: schema validation, the state
store, the registry, and the engine's phase-1 -> phase-2 handoff, including the
canonical-URL injection, the missing-canonical guard, and graceful per-platform
failure. Adapter network bodies are stubs, so no credentials or I/O are needed.

Async adapters are driven with ``asyncio.run`` directly, so the suite needs no
``pytest-asyncio`` plugin.
"""

from __future__ import annotations

import asyncio
import os

import pytest

from article import (
    Article,
    ArticleValidationError,
    CanonicalUrlMissing,
    JsonStateStore,
    PipelineEngine,
    Settings,
    available_adapters,
    get_adapter,
    load_article,
)
from article.base import DEV_TO, HASHNODE, MEDIUM, SUBSTACK

PUBLICATION_URL = "https://tester.substack.com"


def _settings(tmp_path) -> Settings:
    """Isolated settings: no .env read, a temp state file, a fixed publication URL."""
    return Settings(
        _env_file=None,
        substack_publication_url=PUBLICATION_URL,
        hashnode_publication_id="pub-test",
        state_path=str(tmp_path / "pipeline_state.json"),
    )


def _article() -> Article:
    return load_article(
        {
            "title": "Hello SSOT",
            "slug": "hello-ssot",
            "content_markdown": "# Hello\n\nBody.",
            "tags": ["python", "automation"],
            "platforms": {
                "substack": {"publish_as_draft": False},
                "medium": {},
                "dev_to": {},
                "hashnode": {},
            },
        }
    )


def _engine(tmp_path, **kw) -> PipelineEngine:
    settings = _settings(tmp_path)
    store = JsonStateStore(settings.state_path)
    return PipelineEngine(settings=settings, store=store, **kw)


# --------------------------------------------------------------------------- #
# Schema / loading                                                            #
# --------------------------------------------------------------------------- #


def test_load_article_valid():
    art = _article()
    assert art.slug == "hello-ssot"
    assert sorted(art.platforms.configured()) == ["dev_to", "hashnode", "medium", "substack"]


def test_load_article_friendly_error_names_fields():
    with pytest.raises(ArticleValidationError) as ei:
        load_article({"title": "x", "slug": "Bad Slug", "content_markdown": ""})
    msg = str(ei.value)
    assert "slug" in msg and "content_markdown" in msg  # both offenders named


def test_unknown_platform_key_rejected():
    with pytest.raises(ArticleValidationError):
        load_article(
            {"title": "x", "slug": "x", "content_markdown": "y", "platforms": {"twitter": {}}}
        )


# --------------------------------------------------------------------------- #
# State store                                                                 #
# --------------------------------------------------------------------------- #


def test_state_store_roundtrip_and_persistence(tmp_path):
    path = str(tmp_path / "s.json")
    store = JsonStateStore(path)
    store.set_canonical_url("a-slug", "https://x/p/a-slug")
    # A fresh instance over the same file sees it (file is the SSOT).
    assert JsonStateStore(path).get_canonical_url("a-slug") == "https://x/p/a-slug"
    assert os.path.exists(path)


# --------------------------------------------------------------------------- #
# Registry                                                                    #
# --------------------------------------------------------------------------- #


def test_registry_has_all_builtin_adapters():
    assert available_adapters() == (DEV_TO, HASHNODE, MEDIUM, SUBSTACK)
    assert callable(get_adapter(MEDIUM))


# --------------------------------------------------------------------------- #
# Phase 1 -> Phase 2 SSOT handoff                                             #
# --------------------------------------------------------------------------- #


def test_phase1_records_canonical_url(tmp_path):
    engine = _engine(tmp_path)
    art = _article()
    summary = asyncio.run(engine.publish_primary(art))
    expected = f"{PUBLICATION_URL}/p/{art.slug}"
    assert summary.ok
    assert summary.canonical_url == expected
    # Persisted to the state store, keyed by slug.
    assert engine.store.get_canonical_url(art.slug) == expected


def test_phase2_injects_canonical_into_every_secondary(tmp_path):
    engine = _engine(tmp_path)
    art = _article()
    asyncio.run(engine.publish_primary(art))
    summary = asyncio.run(engine.syndicate_secondary(art))

    canonical = f"{PUBLICATION_URL}/p/{art.slug}"
    assert summary.ok
    assert {r.platform for r in summary.results} == {MEDIUM, DEV_TO, HASHNODE}
    # Every secondary result carries the canonical, and so does its payload.
    for r in summary.results:
        assert r.canonical_url == canonical
    payloads = summary.by_platform
    assert payloads[MEDIUM].detail["payload"]["canonicalUrl"] == canonical
    assert payloads[DEV_TO].detail["payload"]["article"]["canonical_url"] == canonical
    assert payloads[HASHNODE].detail["variables"]["input"]["originalArticleURL"] == canonical


def test_phase2_before_phase1_raises(tmp_path):
    engine = _engine(tmp_path)
    with pytest.raises(CanonicalUrlMissing):
        asyncio.run(engine.syndicate_secondary(_article()))


def test_devto_tags_are_comma_joined_string(tmp_path):
    """Encodes the verified Forem V1 drift: tags is a string, not a list."""
    engine = _engine(tmp_path)
    art = _article()
    asyncio.run(engine.publish_primary(art))
    summary = asyncio.run(engine.syndicate_secondary(art, platforms=[DEV_TO]))
    assert summary.by_platform[DEV_TO].detail["payload"]["article"]["tags"] == "python,automation"


# --------------------------------------------------------------------------- #
# Reliability: one platform failing never aborts the run                      #
# --------------------------------------------------------------------------- #


def test_one_platform_failure_does_not_abort(tmp_path):
    async def _boom(article, *, canonical_url, config, secrets):
        raise RuntimeError("kaboom")

    def resolver(name):
        return _boom if name == MEDIUM else get_adapter(name)

    engine = _engine(tmp_path, resolve_adapter=resolver)
    art = _article()
    asyncio.run(engine.publish_primary(art))
    summary = asyncio.run(engine.syndicate_secondary(art))

    assert not summary.ok  # there was a failure ...
    assert [r.platform for r in summary.failures] == [MEDIUM]
    # ... but the other platforms still ran and succeeded.
    assert {r.platform for r in summary.successes} == {DEV_TO, HASHNODE}
    # Partial progress was persisted for the survivors.
    record = engine.store[art.slug]
    assert record["syndication"][DEV_TO]["state"] == "success"
    assert record["syndication"][MEDIUM]["state"] == "failed"


def test_unconfigured_secondary_is_not_attempted(tmp_path):
    engine = _engine(tmp_path)
    art = load_article(
        {
            "title": "Solo",
            "slug": "solo",
            "content_markdown": "x",
            "platforms": {"substack": {}, "medium": {}},  # no dev_to/hashnode
        }
    )
    asyncio.run(engine.publish_primary(art))
    summary = asyncio.run(engine.syndicate_secondary(art))
    assert {r.platform for r in summary.results} == {MEDIUM}
