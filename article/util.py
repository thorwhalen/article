"""Thin, dependency-light utilities shared across the package.

Nothing here knows about platforms or pipelines — these are general helpers:
logging, human-like async pacing (so automating your *own* account doesn't trip
automated-traffic heuristics), atomic JSON IO for the state store, and the
canonical-URL guard that every secondary adapter calls so the SSOT link is
never silently dropped.

Side-effecting primitives (sleeping, the clock, the RNG) are injected as
keyword-only parameters so the helpers stay deterministic under test.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional, TypeVar, Union

from .base import AdapterError

T = TypeVar("T")
PathLike = Union[str, os.PathLike]

_LOGGER_NAME = "article"


def get_logger(name: str = _LOGGER_NAME) -> logging.Logger:
    """Return the package logger, attaching a single stderr handler once.

    Idempotent: repeated calls don't stack handlers.

    >>> log = get_logger()
    >>> log.name
    'article'
    >>> get_logger() is log
    True
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def coalesce(*values: Optional[T]) -> Optional[T]:
    """First non-``None`` value, else ``None`` (SQL ``COALESCE``).

    >>> coalesce(None, None, 3, 4)
    3
    >>> coalesce(None, None) is None
    True
    """
    return next((v for v in values if v is not None), None)


def utcnow_iso(
    *, _now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)
) -> str:
    """Current UTC time as an ISO-8601 string (clock injectable for tests).

    >>> from datetime import datetime, timezone
    >>> utcnow_iso(_now=lambda: datetime(2026, 6, 21, tzinfo=timezone.utc))
    '2026-06-21T00:00:00+00:00'
    """
    return _now().isoformat()


async def human_delay(
    min_seconds: float,
    max_seconds: float,
    *,
    _sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    _rand: Callable[[float, float], float] = random.uniform,
) -> float:
    """Sleep a randomized, human-like interval; return the delay used.

    Used between scripted browser actions so automation of one's own account
    paces like a person. The sleeper and RNG are injectable for deterministic
    tests:

    >>> import asyncio
    >>> async def _no_sleep(_): pass
    >>> asyncio.run(human_delay(0.5, 0.5, _sleep=_no_sleep))
    0.5
    """
    delay = _rand(min_seconds, max_seconds)
    await _sleep(delay)
    return delay


def require_canonical_url(platform: str, canonical_url: Optional[str]) -> str:
    """Return ``canonical_url`` or raise — the SSOT link is never optional.

    Every *secondary* adapter calls this first so a missing canonical link
    fails loudly instead of silently emitting a self-canonical post.

    >>> require_canonical_url("medium", "https://x.substack.com/p/y")
    'https://x.substack.com/p/y'
    >>> require_canonical_url("medium", None)
    Traceback (most recent call last):
    ...
    article.base.AdapterError: medium: canonical_url is required for syndication but was missing
    """
    if not canonical_url:
        raise AdapterError(
            f"{platform}: canonical_url is required for syndication but was missing"
        )
    return canonical_url


def read_json(path: PathLike, *, default: Any = None) -> Any:
    """Read and parse a JSON file, returning ``default`` if it doesn't exist."""
    p = Path(path)
    if not p.exists():
        return default
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def atomic_write_json(path: PathLike, data: Any, *, indent: int = 2) -> None:
    """Write ``data`` as JSON atomically (temp file + ``os.replace``).

    Creates parent directories as needed. The temp-then-replace dance means a
    crashed write never leaves a half-written state file behind.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=f".{p.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=False, sort_keys=True)
            f.write("\n")
        os.replace(tmp, p)
    except BaseException:
        with suppress_errors():
            os.unlink(tmp)
        raise


class suppress_errors:
    """A tiny ``contextlib.suppress(Exception)`` without the import churn."""

    def __enter__(self) -> "suppress_errors":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return exc_type is not None and issubclass(exc_type, Exception)


def run_sync(coro: Awaitable[T]) -> T:
    """Run an async coroutine to completion from sync code (CLI entry points).

    A thin, named wrapper over :func:`asyncio.run` so the dispatch-to-interface
    seam is obvious and easy to swap (e.g. for an existing event loop later).
    """
    return asyncio.run(coro)  # type: ignore[arg-type]
