"""Adapter ``Protocol`` + an open-closed registry keyed by platform name.

Adding a platform means writing one async adapter function and decorating it
with :func:`register_adapter` — no edits to the engine, the CLI, or any switch
statement (open-closed). Adapters are plain async callables (favour functions
over classes) that satisfy :class:`PublishAdapter`; they receive their config
and secrets by injection from the engine and never reach into globals.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping, Optional, Protocol, runtime_checkable

from .base import PlatformName, PublishResult, UnknownPlatformError

if TYPE_CHECKING:  # avoid an import cycle; only needed for type checking
    from .config import Article


@runtime_checkable
class PublishAdapter(Protocol):
    """The contract every platform adapter satisfies.

    An adapter is an ``async`` callable. The engine injects:

    - ``article``: the validated :class:`~article.config.Article`.
    - ``canonical_url``: the SSOT URL (``None`` only for the primary, which
      *defines* it; secondaries must receive and honour it).
    - ``config``: the platform's config model (overrides + options).
    - ``secrets``: the minimal credentials/identity for this platform.

    and receives a :class:`~article.base.PublishResult` back.
    """

    async def __call__(
        self,
        article: "Article",
        *,
        canonical_url: Optional[str],
        config: Any,
        secrets: Mapping[str, Any],
    ) -> PublishResult: ...


_REGISTRY: dict[str, PublishAdapter] = {}


def register_adapter(name: PlatformName):
    """Decorator registering an adapter callable under ``name``.

    >>> @register_adapter("demo")  # doctest: +SKIP
    ... async def publish(article, *, canonical_url, config, secrets):
    ...     ...
    """

    def _register(adapter: PublishAdapter) -> PublishAdapter:
        _REGISTRY[name] = adapter
        return adapter

    return _register


def get_adapter(name: str) -> PublishAdapter:
    """Resolve the adapter registered under ``name``.

    >>> get_adapter("nope")
    Traceback (most recent call last):
    ...
    article.base.UnknownPlatformError: ...no adapter registered for 'nope'...
    """
    try:
        return _REGISTRY[name]
    except KeyError:
        raise UnknownPlatformError(
            f"no adapter registered for {name!r}; available: {available_adapters()}"
        ) from None


def available_adapters() -> tuple[str, ...]:
    """The platform names with a registered adapter (sorted)."""
    return tuple(sorted(_REGISTRY))


def is_registered(name: str) -> bool:
    """Whether an adapter is registered under ``name``."""
    return name in _REGISTRY
