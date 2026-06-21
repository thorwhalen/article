"""Core vocabulary for the ``article`` publishing pipeline.

This module holds only *foundational* types — the names every other layer
speaks in — and no business logic:

- :data:`PlatformName` and the platform-name constants
  (:data:`SUBSTACK`, :data:`MEDIUM`, :data:`DEV_TO`, :data:`HASHNODE`).
- :class:`PublishResult` — the immutable, per-platform outcome of one publish
  attempt, with :meth:`PublishResult.success` / :meth:`~PublishResult.failure`
  / :meth:`~PublishResult.skipped` constructors so call sites read declaratively.
- :class:`RunSummary` — the structured result of a whole phase (a tuple of
  :class:`PublishResult` plus the resolved ``canonical_url``).
- The package exception hierarchy, all rooted at :class:`ArticleError`.

Keeping these here (rather than scattered) is the SSOT for the package's shared
types and keeps import edges acyclic: ``base`` imports nothing from the package.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, Mapping, Optional

# --------------------------------------------------------------------------- #
# Platform identifiers (SSOT for the names used as registry/config/state keys) #
# --------------------------------------------------------------------------- #

PlatformName = Literal["substack", "medium", "dev_to", "hashnode"]

SUBSTACK: PlatformName = "substack"
MEDIUM: PlatformName = "medium"
DEV_TO: PlatformName = "dev_to"
HASHNODE: PlatformName = "hashnode"

#: The primary platform whose assigned public URL becomes the canonical SSOT.
PRIMARY_PLATFORM: PlatformName = SUBSTACK

#: The platforms syndicated to in phase 2, each pointing canonically at the primary.
SECONDARY_PLATFORMS: tuple[PlatformName, ...] = (MEDIUM, DEV_TO, HASHNODE)

#: All known platforms, primary first.
ALL_PLATFORMS: tuple[PlatformName, ...] = (PRIMARY_PLATFORM, *SECONDARY_PLATFORMS)


class Phase(str, Enum):
    """The two pipeline phases, named exactly as their CLI commands."""

    PUBLISH_PRIMARY = "publish-primary"
    SYNDICATE_SECONDARY = "syndicate-secondary"


class PublishState(str, Enum):
    """Outcome state of a single platform publish attempt."""

    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


# --------------------------------------------------------------------------- #
# Result types                                                                #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class PublishResult:
    """Immutable outcome of one platform publish attempt.

    Construct via the classmethods rather than the raw initializer so intent is
    explicit at the call site:

    >>> PublishResult.success("medium", url="https://medium.com/p/x", status="draft").ok
    True
    >>> r = PublishResult.failure("hashnode", error="HTTP 401")
    >>> r.ok, r.state.value, r.error
    (False, 'failed', 'HTTP 401')
    >>> PublishResult.skipped("dev_to", reason="not configured").state.value
    'skipped'
    """

    platform: str
    state: PublishState
    url: Optional[str] = None
    status: Optional[str] = None  # platform-native status, e.g. "draft"/"published"
    canonical_url: Optional[str] = None
    error: Optional[str] = None
    detail: Mapping[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """True iff the attempt succeeded."""
        return self.state is PublishState.SUCCESS

    @classmethod
    def success(
        cls,
        platform: str,
        *,
        url: Optional[str] = None,
        status: Optional[str] = None,
        canonical_url: Optional[str] = None,
        detail: Optional[Mapping[str, Any]] = None,
    ) -> "PublishResult":
        """A successful publish/draft to ``platform``."""
        return cls(
            platform=platform,
            state=PublishState.SUCCESS,
            url=url,
            status=status,
            canonical_url=canonical_url,
            detail=dict(detail or {}),
        )

    @classmethod
    def failure(
        cls,
        platform: str,
        *,
        error: str,
        detail: Optional[Mapping[str, Any]] = None,
    ) -> "PublishResult":
        """A failed attempt on ``platform`` — the run continues past it."""
        return cls(
            platform=platform,
            state=PublishState.FAILED,
            error=error,
            detail=dict(detail or {}),
        )

    @classmethod
    def skipped(
        cls,
        platform: str,
        *,
        reason: str,
        detail: Optional[Mapping[str, Any]] = None,
    ) -> "PublishResult":
        """``platform`` was not attempted (e.g. absent from the article config)."""
        return cls(
            platform=platform,
            state=PublishState.SKIPPED,
            error=reason,
            detail=dict(detail or {}),
        )

    def as_record(self) -> dict[str, Any]:
        """A JSON-serializable summary, suitable for the state store."""
        return {
            "platform": self.platform,
            "state": self.state.value,
            "url": self.url,
            "status": self.status,
            "canonical_url": self.canonical_url,
            "error": self.error,
            "detail": dict(self.detail),
        }


@dataclass(frozen=True, slots=True)
class RunSummary:
    """Structured result of one pipeline phase across all targeted platforms.

    >>> results = (
    ...     PublishResult.success("medium", url="m"),
    ...     PublishResult.failure("dev_to", error="boom"),
    ... )
    >>> summary = RunSummary(phase="syndicate-secondary", results=results, canonical_url="c")
    >>> summary.ok
    False
    >>> [r.platform for r in summary.failures]
    ['dev_to']
    >>> summary.by_platform["medium"].url
    'm'
    """

    phase: str
    results: tuple[PublishResult, ...]
    canonical_url: Optional[str] = None

    @property
    def ok(self) -> bool:
        """True iff no targeted platform failed (skipped platforms don't count)."""
        return not self.failures

    @property
    def failures(self) -> tuple[PublishResult, ...]:
        """The subset of results that failed."""
        return tuple(r for r in self.results if r.state is PublishState.FAILED)

    @property
    def successes(self) -> tuple[PublishResult, ...]:
        """The subset of results that succeeded."""
        return tuple(r for r in self.results if r.state is PublishState.SUCCESS)

    @property
    def by_platform(self) -> dict[str, PublishResult]:
        """Results keyed by platform name."""
        return {r.platform: r for r in self.results}

    def render(self) -> str:
        """A compact human-readable, multi-line summary."""
        glyph = {
            PublishState.SUCCESS: "[ok]  ",
            PublishState.FAILED: "[fail]",
            PublishState.SKIPPED: "[skip]",
        }
        lines = [f"Phase: {self.phase}"]
        if self.canonical_url:
            lines.append(f"canonical_url: {self.canonical_url}")
        for r in self.results:
            tail = r.url or r.error or ""
            status = f" ({r.status})" if r.status else ""
            lines.append(f"  {glyph[r.state]} {r.platform}{status}: {tail}".rstrip())
        lines.append(
            f"=> {len(self.successes)} ok, {len(self.failures)} failed, "
            f"{len(self.results) - len(self.successes) - len(self.failures)} skipped"
        )
        return "\n".join(lines)

    def as_record(self) -> dict[str, Any]:
        """A JSON-serializable summary, suitable for the state store."""
        return {
            "phase": self.phase,
            "canonical_url": self.canonical_url,
            "results": [r.as_record() for r in self.results],
        }


# --------------------------------------------------------------------------- #
# Exception hierarchy                                                          #
# --------------------------------------------------------------------------- #


class ArticleError(Exception):
    """Base class for every error this package raises deliberately."""


class ArticleValidationError(ArticleError):
    """An article JSON file failed schema validation (with a friendly message)."""


class ConfigError(ArticleError):
    """Required configuration or secret is missing/invalid."""


class AdapterError(ArticleError):
    """A platform adapter could not complete its publish attempt."""


class UnknownPlatformError(ArticleError, KeyError):
    """No adapter is registered under the requested platform name."""


class CanonicalUrlMissing(ArticleError):
    """Phase 2 was requested before phase 1 recorded a canonical_url."""
