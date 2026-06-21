"""Orchestration engine — the two-phase, canonical-URL SSOT pipeline.

The engine sequences the workflow, resolves adapters from the registry, and
injects each adapter's config + secrets. It owns the one rule that makes the
whole package cohere:

    Phase 1 (``publish_primary``) publishes to the primary platform (Substack),
    captures the live public URL it assigns, and writes it to the state store
    as ``canonical_url`` — the single source of truth.

    Phase 2 (``syndicate_secondary``), run later, reads that ``canonical_url``
    back and injects it into every secondary platform's payload, so each emits
    ``<link rel="canonical">`` pointing at the primary. If phase 1 never ran,
    phase 2 refuses to proceed (:class:`~article.base.CanonicalUrlMissing`).

Reliability: a failure on one platform is caught, logged, recorded to the
state store, and the run continues with the remaining platforms — one failure
never aborts the sequence. Every phase returns a structured
:class:`~article.base.RunSummary`.

Simple things simple (module-level :func:`publish_primary` /
:func:`syndicate_secondary` build a default engine); complex things possible
(construct :class:`PipelineEngine` with an injected store, settings, or adapter
resolver for testing and alternate backends).
"""

from __future__ import annotations

from collections.abc import MutableMapping
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional

from .base import (
    PRIMARY_PLATFORM,
    SECONDARY_PLATFORMS,
    AdapterError,
    CanonicalUrlMissing,
    Phase,
    PlatformName,
    PublishResult,
    RunSummary,
)
from .config import Article, Settings, load_settings
from .registry import PublishAdapter, get_adapter
from .state import JsonStateStore
from .util import get_logger

AdapterResolver = Callable[[str], PublishAdapter]


@dataclass
class PipelineEngine:
    """Coordinates the publishing phases over an injected store + settings.

    :param settings: secrets/runtime config facade.
    :param store: the state store (any ``MutableMapping`` keyed by slug).
    :param resolve_adapter: registry lookup (injected for testing / overrides).
    """

    settings: Settings
    store: MutableMapping
    resolve_adapter: AdapterResolver = field(default=get_adapter)

    def __post_init__(self) -> None:
        self._log = get_logger()

    # ------------------------------------------------------------------ #
    # Phase 1 — publish to primary, capture canonical_url                 #
    # ------------------------------------------------------------------ #

    async def publish_primary(self, article: Article) -> RunSummary:
        """Publish to the primary platform and record its URL as ``canonical_url``."""
        platform: PlatformName = PRIMARY_PLATFORM
        config = article.platforms.configured().get(platform)

        if config is None:
            self._log.warning(
                "No %r config on article %r; nothing to publish for phase 1.",
                platform,
                article.slug,
            )
            result = PublishResult.skipped(
                platform, reason=f"no {platform} config on the article"
            )
            self._record(article, result, phase=Phase.PUBLISH_PRIMARY)
            return RunSummary(phase=Phase.PUBLISH_PRIMARY.value, results=(result,))

        result = await self._run_adapter(article, platform, config, canonical_url=None)

        canonical_url: Optional[str] = None
        if result.ok and result.url:
            canonical_url = result.url
            self.store.set_canonical_url(article.slug, canonical_url)
            self._log.info(
                "Recorded canonical_url for %r: %s", article.slug, canonical_url
            )
        elif result.ok and not result.url:
            # Succeeded but gave us no URL — the SSOT handoff would silently break.
            result = PublishResult.failure(
                platform,
                error="primary adapter returned no public URL to use as canonical_url",
                detail=dict(result.detail),
            )

        self._record(article, result, phase=Phase.PUBLISH_PRIMARY)
        return RunSummary(
            phase=Phase.PUBLISH_PRIMARY.value,
            results=(result,),
            canonical_url=canonical_url,
        )

    # ------------------------------------------------------------------ #
    # Phase 2 — syndicate to secondaries with canonical_url injected      #
    # ------------------------------------------------------------------ #

    async def syndicate_secondary(
        self,
        article: Article,
        *,
        platforms: Optional[Iterable[PlatformName]] = None,
    ) -> RunSummary:
        """Syndicate to each configured secondary, injecting the canonical URL.

        Raises :class:`~article.base.CanonicalUrlMissing` if phase 1 hasn't
        recorded a canonical URL for this slug yet.
        """
        canonical_url = self.store.get_canonical_url(article.slug)
        if not canonical_url:
            raise CanonicalUrlMissing(
                f"No canonical_url recorded for slug {article.slug!r}. "
                f"Run `publish-primary` first so the SSOT URL exists."
            )

        targets = self._secondary_targets(article, platforms)
        if not targets:
            self._log.warning("No secondary platforms configured for %r.", article.slug)

        results: list[PublishResult] = []
        for platform, config in targets:
            result = await self._run_adapter(
                article, platform, config, canonical_url=canonical_url
            )
            results.append(result)
            # Persist partial progress after *each* platform — a later crash
            # never loses what already succeeded.
            self._record(article, result, phase=Phase.SYNDICATE_SECONDARY)

        return RunSummary(
            phase=Phase.SYNDICATE_SECONDARY.value,
            results=tuple(results),
            canonical_url=canonical_url,
        )

    # ------------------------------------------------------------------ #
    # Internals                                                           #
    # ------------------------------------------------------------------ #

    def _secondary_targets(
        self,
        article: Article,
        platforms: Optional[Iterable[PlatformName]],
    ) -> list[tuple[PlatformName, object]]:
        """Configured secondary platforms, optionally filtered by ``platforms``."""
        configured = article.platforms.configured()
        wanted = set(platforms) if platforms is not None else None
        return [
            (name, configured[name])
            for name in SECONDARY_PLATFORMS
            if name in configured and (wanted is None or name in wanted)
        ]

    async def _run_adapter(
        self,
        article: Article,
        platform: PlatformName,
        config: object,
        *,
        canonical_url: Optional[str],
    ) -> PublishResult:
        """Resolve + invoke one adapter, converting any failure into a result.

        This is the graceful-degradation seam: an adapter raising *anything*
        becomes a :class:`~article.base.PublishResult` failure so the caller's
        loop keeps going.
        """
        try:
            adapter = self.resolve_adapter(platform)
            secrets = self.settings.secrets_for(platform)
            self._log.info("[%s] publishing %r ...", platform, article.slug)
            result = await adapter(
                article,
                canonical_url=canonical_url,
                config=config,
                secrets=secrets,
            )
            if result.ok:
                self._log.info("[%s] ok: %s", platform, result.url or "(no url)")
            else:
                self._log.error("[%s] failed: %s", platform, result.error)
            return result
        except AdapterError as e:
            self._log.error("[%s] adapter error: %s", platform, e)
            return PublishResult.failure(platform, error=str(e))
        except Exception as e:  # never let one platform abort the run
            self._log.exception("[%s] unexpected error", platform)
            return PublishResult.failure(platform, error=f"{type(e).__name__}: {e}")

    def _record(self, article: Article, result: PublishResult, *, phase: Phase) -> None:
        """Persist a result into the per-slug state record (best-effort)."""
        slot = "primary" if phase is Phase.PUBLISH_PRIMARY else "syndication"
        record = dict(self.store.get(article.slug, {}))
        record.setdefault("title", article.title)
        if phase is Phase.PUBLISH_PRIMARY:
            record["primary"] = result.as_record()
        else:
            syndication = dict(record.get("syndication", {}))
            syndication[result.platform] = result.as_record()
            record["syndication"] = syndication
        self.store.update_record(article.slug, **{k: v for k, v in record.items() if k != "slug"})


# --------------------------------------------------------------------------- #
# Module-level facade (shared by Python callers and the CLI)                  #
# --------------------------------------------------------------------------- #


def build_engine(
    *,
    settings: Optional[Settings] = None,
    store: Optional[MutableMapping] = None,
) -> PipelineEngine:
    """Construct a :class:`PipelineEngine` with sensible defaults.

    Defaults: settings from ``.env``/environment, and a JSON state store at
    ``settings.state_path``. Pass either explicitly to override (tests, alt backends).
    """
    settings = settings or load_settings()
    if store is None:
        store = JsonStateStore(settings.state_path)
    return PipelineEngine(settings=settings, store=store)


async def publish_primary(
    article: Article,
    *,
    settings: Optional[Settings] = None,
    store: Optional[MutableMapping] = None,
) -> RunSummary:
    """Phase 1 facade: publish to the primary platform and record canonical_url."""
    return await build_engine(settings=settings, store=store).publish_primary(article)


async def syndicate_secondary(
    article: Article,
    *,
    settings: Optional[Settings] = None,
    store: Optional[MutableMapping] = None,
    platforms: Optional[Iterable[PlatformName]] = None,
) -> RunSummary:
    """Phase 2 facade: syndicate to secondaries with the canonical_url injected."""
    engine = build_engine(settings=settings, store=store)
    return await engine.syndicate_secondary(article, platforms=platforms)
