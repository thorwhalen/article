"""article — semi-automate single-source-of-truth article publishing.

Author an article once as a JSON file, publish it to a **primary** platform
(Substack), then **syndicate** it to secondaries (Medium, Dev.to, Hashnode)
with correct canonical-URL SEO. The Substack public URL captured in phase 1 is
the single source of truth (SSOT) injected as ``canonical_url`` into every
secondary in phase 2.

Quick start (Python)::

    import asyncio
    from article import load_article, publish_primary, syndicate_secondary

    art = load_article("article.json")
    asyncio.run(publish_primary(art))        # phase 1 -> records canonical_url
    asyncio.run(syndicate_secondary(art))    # phase 2 -> canonical SEO everywhere

Or via the CLI::

    python -m article publish-primary     article.json
    python -m article syndicate-secondary article.json

The public surface below is curated; everything else is an implementation
detail. Importing this package registers the built-in platform adapters.

>>> from article import load_article, available_adapters
>>> load_article({"title": "T", "slug": "t", "content_markdown": "x"}).slug
't'
>>> available_adapters()
('dev_to', 'hashnode', 'medium', 'substack')
"""

from __future__ import annotations

# Vocabulary / result types / exceptions
from .base import (
    ALL_PLATFORMS,
    DEV_TO,
    HASHNODE,
    MEDIUM,
    PRIMARY_PLATFORM,
    SECONDARY_PLATFORMS,
    SUBSTACK,
    AdapterError,
    ArticleError,
    ArticleValidationError,
    CanonicalUrlMissing,
    ConfigError,
    Phase,
    PlatformName,
    PublishResult,
    PublishState,
    RunSummary,
    UnknownPlatformError,
)

# Domain schema + config facade
from .config import (
    Article,
    DevToConfig,
    HashnodeConfig,
    MediumConfig,
    PlatformConfigs,
    Settings,
    SubstackConfig,
    load_article,
    load_settings,
)

# State store (MutableMapping facade)
from .state import JsonStateStore, default_state_store

# Adapter Protocol + open-closed registry
from .registry import (
    PublishAdapter,
    available_adapters,
    get_adapter,
    is_registered,
    register_adapter,
)

# Orchestration engine + module-level facade
from .engine import (
    PipelineEngine,
    build_engine,
    publish_primary,
    syndicate_secondary,
)

# Importing the adapters package registers all built-in adapters.
from . import adapters  # noqa: F401  (side-effect: populate the registry)

__all__ = [
    # domain
    "Article",
    "PlatformConfigs",
    "SubstackConfig",
    "MediumConfig",
    "DevToConfig",
    "HashnodeConfig",
    "load_article",
    # config / settings
    "Settings",
    "load_settings",
    # results / vocabulary
    "PublishResult",
    "PublishState",
    "RunSummary",
    "Phase",
    "PlatformName",
    "PRIMARY_PLATFORM",
    "SECONDARY_PLATFORMS",
    "ALL_PLATFORMS",
    "SUBSTACK",
    "MEDIUM",
    "DEV_TO",
    "HASHNODE",
    # errors
    "ArticleError",
    "ArticleValidationError",
    "ConfigError",
    "AdapterError",
    "UnknownPlatformError",
    "CanonicalUrlMissing",
    # state
    "JsonStateStore",
    "default_state_store",
    # registry
    "PublishAdapter",
    "register_adapter",
    "get_adapter",
    "available_adapters",
    "is_registered",
    # engine
    "PipelineEngine",
    "build_engine",
    "publish_primary",
    "syndicate_secondary",
]

__version__ = "0.1.0"
