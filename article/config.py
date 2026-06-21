"""Domain schema + configuration facade.

Two concerns live here, both expressed as Pydantic v2 models so validation is
declarative and the SSOT for *shape*:

1. **The article domain model** (:class:`Article` + the per-platform config
   models) — parsed from a standardized JSON file via :func:`load_article`,
   which turns raw Pydantic tracebacks into a single actionable message
   (which field, why).
2. **Runtime settings/secrets** (:class:`Settings`) — API tokens and Substack
   credentials loaded from ``.env`` / the environment via
   :func:`load_settings`, the single facade the rest of the package calls.
   Secrets are marked ``repr=False`` so they never leak into logs or tracebacks.

Per-platform presence is the on/off switch: a platform absent from
``article.platforms`` is simply skipped.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .base import (
    DEV_TO,
    HASHNODE,
    MEDIUM,
    SUBSTACK,
    ArticleValidationError,
    PlatformName,
)

# --------------------------------------------------------------------------- #
# Per-platform configuration (overrides + publishing options)                 #
# --------------------------------------------------------------------------- #


class _PlatformConfig(BaseModel):
    """Shared base for per-platform overrides. Unknown keys are rejected."""

    model_config = ConfigDict(extra="forbid")

    #: Default to a draft for visual QA before going public. Overridden per platform.
    publish_as_draft: bool = True
    #: Optional per-platform title override (falls back to the article title).
    title: Optional[str] = None
    #: Optional per-platform tag override (falls back to the article tags).
    tags: Optional[list[str]] = None


class SubstackConfig(_PlatformConfig):
    """Primary platform. Defaults to *publishing* (it defines the canonical URL)."""

    publish_as_draft: bool = False
    #: ``https://<sub>.substack.com`` (or custom domain); else taken from settings.
    publication_url: Optional[str] = None
    #: Optional Substack section id to file the post under.
    section_id: Optional[int] = None
    #: Whether publishing emails subscribers (the Substack ``send`` flag).
    send_email: bool = False
    #: Audience visibility: everyone / only_paid / founding / only_free.
    audience: str = "everyone"


class MediumConfig(_PlatformConfig):
    """Medium syndication options (REST API; ``canonicalUrl`` carries SEO)."""

    #: Publish under a Medium publication instead of the user profile.
    publication_id: Optional[str] = None
    notify_followers: bool = False
    #: One of Medium's license enum values.
    license: str = "all-rights-reserved"


class DevToConfig(_PlatformConfig):
    """Dev.to / Forem syndication options (``canonical_url`` carries SEO)."""

    organization_id: Optional[int] = None
    series: Optional[str] = None


class HashnodeConfig(_PlatformConfig):
    """Hashnode syndication options (``originalArticleURL`` carries SEO)."""

    #: ObjectId of the target publication; else taken from settings.
    publication_id: Optional[str] = None
    series_id: Optional[str] = None
    subtitle: Optional[str] = None


class PlatformConfigs(BaseModel):
    """Per-platform map. A ``None`` (absent) entry means *skip that platform*."""

    model_config = ConfigDict(extra="forbid")

    substack: Optional[SubstackConfig] = None
    medium: Optional[MediumConfig] = None
    dev_to: Optional[DevToConfig] = None
    hashnode: Optional[HashnodeConfig] = None

    def configured(self) -> dict[PlatformName, _PlatformConfig]:
        """The subset of platforms that are present (non-``None``), keyed by name.

        >>> PlatformConfigs(medium=MediumConfig()).configured().keys()
        dict_keys(['medium'])
        """
        items: dict[PlatformName, Optional[_PlatformConfig]] = {
            SUBSTACK: self.substack,
            MEDIUM: self.medium,
            DEV_TO: self.dev_to,
            HASHNODE: self.hashnode,
        }
        return {name: cfg for name, cfg in items.items() if cfg is not None}


# --------------------------------------------------------------------------- #
# Article domain model                                                        #
# --------------------------------------------------------------------------- #

_SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"


class Article(BaseModel):
    """A single-source-of-truth article authored once and published everywhere.

    >>> art = Article(
    ...     title="Hello World",
    ...     slug="hello-world",
    ...     content_markdown="# Hi\\n\\nBody text.",
    ...     tags=["python", "automation"],
    ...     platforms=PlatformConfigs(medium=MediumConfig(), dev_to=DevToConfig()),
    ... )
    >>> art.slug
    'hello-world'
    >>> sorted(art.platforms.configured())
    ['dev_to', 'medium']
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    # Core content
    title: str = Field(min_length=1)
    subtitle: Optional[str] = None
    slug: str = Field(
        min_length=1,
        pattern=_SLUG_PATTERN,
        description="URL-safe identifier: lowercase alphanumerics joined by single hyphens",
    )
    content_markdown: str = Field(min_length=1)

    # Metadata
    tags: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    cover_image_url: Optional[str] = None
    description: Optional[str] = None

    # Per-platform configuration (presence = publish there)
    platforms: PlatformConfigs = Field(default_factory=PlatformConfigs)

    @field_validator("cover_image_url")
    @classmethod
    def _validate_cover_url(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.startswith(("http://", "https://")):
            raise ValueError("cover_image_url must be an http(s) URL")
        return v


# --------------------------------------------------------------------------- #
# Loading & validation                                                        #
# --------------------------------------------------------------------------- #

ArticleSource = Union[str, os.PathLike, Mapping[str, Any]]


def _format_validation_error(exc: ValidationError, *, source: str) -> str:
    """Turn a Pydantic ``ValidationError`` into an actionable, field-keyed message."""
    lines = [f"Invalid article ({source}): {exc.error_count()} problem(s):"]
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"]) or "(root)"
        lines.append(f"  - {loc}: {err['msg']}")
    return "\n".join(lines)


def load_article(source: ArticleSource) -> Article:
    """Load and validate an :class:`Article` from a JSON file path, JSON string, or mapping.

    Validation failures are re-raised as :class:`~article.base.ArticleValidationError`
    with a single message naming each offending field — not a raw traceback.

    >>> load_article({
    ...     "title": "Hello",
    ...     "slug": "hello-world",
    ...     "content_markdown": "x",
    ...     "platforms": {"dev_to": {}},
    ... }).slug
    'hello-world'

    >>> load_article({"title": "x"})  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
    ...
    article.base.ArticleValidationError: Invalid article ...slug... content_markdown...

    >>> load_article({"title": "x", "slug": "Bad Slug", "content_markdown": "y"})  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
    ...
    article.base.ArticleValidationError: Invalid article ...slug: String should match pattern...
    """
    if isinstance(source, Mapping):
        data, origin = dict(source), "<mapping>"
    else:
        text = str(source)
        # Heuristic: a path that exists is a file; otherwise treat as inline JSON.
        if Path(text).expanduser().exists():
            origin = text
            with Path(text).expanduser().open("r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            origin = "<json-string>"
            try:
                data = json.loads(text)
            except json.JSONDecodeError as e:
                raise ArticleValidationError(
                    f"Could not read article from {text!r}: not an existing file "
                    f"and not valid JSON ({e})."
                ) from e
    try:
        return Article.model_validate(data)
    except ValidationError as e:
        raise ArticleValidationError(_format_validation_error(e, source=origin)) from e


# --------------------------------------------------------------------------- #
# Runtime settings / secrets facade                                           #
# --------------------------------------------------------------------------- #


class Settings(BaseSettings):
    """Secrets and runtime config, loaded from environment / ``.env``.

    Env var names are the field names upper-cased (e.g. ``MEDIUM_TOKEN``,
    ``DEVTO_API_KEY``, ``SUBSTACK_EMAIL``). Use :func:`load_settings` rather
    than constructing this directly.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Substack (primary; Playwright/session based)
    substack_email: Optional[str] = None
    substack_password: Optional[str] = Field(default=None, repr=False)
    substack_publication_url: Optional[str] = None
    #: Where the persisted Playwright storage_state (cookies/session) is saved.
    substack_session_path: str = ".article/substack_session.json"

    # Medium (REST)
    medium_token: Optional[str] = Field(default=None, repr=False)
    medium_user_id: Optional[str] = None

    # Dev.to / Forem (REST)
    devto_api_key: Optional[str] = Field(default=None, repr=False)

    # Hashnode (GraphQL)
    hashnode_token: Optional[str] = Field(default=None, repr=False)
    hashnode_publication_id: Optional[str] = None

    # Pipeline
    #: JSON state store path (the canonical_url SSOT lives here, keyed by slug).
    state_path: str = "pipeline_state.json"

    # Human-like pacing window (seconds) for browser automation.
    min_action_delay: float = 0.6
    max_action_delay: float = 2.4

    def secrets_for(self, platform: PlatformName) -> dict[str, Any]:
        """The minimal secrets/identity an adapter needs — injected, not global.

        Returning only the relevant subset keeps adapters from reaching into a
        global ``Settings`` (dependency injection + least privilege).

        >>> s = Settings(medium_token="t", medium_user_id="u", _env_file=None)
        >>> s.secrets_for("medium") == {"token": "t", "user_id": "u"}
        True
        """
        by_platform: dict[str, dict[str, Any]] = {
            SUBSTACK: {
                "email": self.substack_email,
                "password": self.substack_password,
                "publication_url": self.substack_publication_url,
                "session_path": self.substack_session_path,
                "min_action_delay": self.min_action_delay,
                "max_action_delay": self.max_action_delay,
            },
            MEDIUM: {"token": self.medium_token, "user_id": self.medium_user_id},
            DEV_TO: {"api_key": self.devto_api_key},
            HASHNODE: {
                "token": self.hashnode_token,
                "publication_id": self.hashnode_publication_id,
            },
        }
        return by_platform[platform]


def load_settings(
    *,
    env_file: Optional[Union[str, os.PathLike]] = None,
    **overrides: Any,
) -> Settings:
    """Load :class:`Settings` from ``.env`` / environment, with optional overrides.

    The single configuration facade. ``env_file=None`` uses the default lookup
    (``.env`` in the working directory); pass an explicit path to point
    elsewhere; pass keyword ``overrides`` to set fields directly (tests, CLI).
    """
    kwargs: dict[str, Any] = dict(overrides)
    if env_file is not None:
        kwargs["_env_file"] = env_file
    return Settings(**kwargs)
