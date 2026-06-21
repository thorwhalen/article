"""Dev.to adapter — Phase 2 syndication via the Forem API V1 (``httpx``).

Endpoint (verified against the Forem OpenAPI spec, ``swagger/v1/api_v1.json``)::

    POST https://dev.to/api/articles

Auth + headers::

    api-key: <YOUR_API_KEY>
    Accept: application/vnd.forem.api-v1+json    # selects API V1
    Content-Type: application/json

Canonical SEO: the **``canonical_url``** field (inside the wrapped ``article``
object) carries the Substack SSOT URL.

Quirks encoded here (these *drift* — verified live):

- The payload is **wrapped** under a top-level ``"article"`` key; flat fields fail.
- In API V1, **``tags`` is a comma-separated string**, not an array.
- ``published: false`` is the *only* draft control (no separate draft flag).
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from ..base import DEV_TO, PublishResult
from ..config import Article, DevToConfig
from ..registry import register_adapter
from ..util import coalesce, get_logger, require_canonical_url

_log = get_logger()

_ENDPOINT = "https://dev.to/api/articles"
_DEVTO_MAX_TAGS = 4


def _tags_csv(article: Article, config: DevToConfig) -> str:
    """Dev.to V1 wants tags as a comma-separated string (max 4)."""
    tags = coalesce(config.tags, article.tags) or []
    return ",".join(tags[:_DEVTO_MAX_TAGS])


def _build_payload(article: Article, canonical_url: str, config: DevToConfig) -> dict:
    """Forem create-article body — wrapped under ``article``, canonical injected."""
    return {
        "article": {
            "title": coalesce(config.title, article.title),
            "body_markdown": article.content_markdown,
            "published": not config.publish_as_draft,  # draft => published: false
            "canonical_url": canonical_url,  # <-- SEO canonical back to the SSOT
            "tags": _tags_csv(article, config),  # comma-separated STRING (V1)
            "series": config.series,
            "main_image": article.cover_image_url,
            "description": article.description,
            "organization_id": config.organization_id,
        }
    }


@register_adapter(DEV_TO)
async def publish(
    article: Article,
    *,
    canonical_url: Optional[str],
    config: DevToConfig,
    secrets: Mapping[str, Any],
) -> PublishResult:
    """Syndicate ``article`` to Dev.to with ``canonical_url`` pointing at the SSOT.

    >>> import asyncio
    >>> from article.config import Article, DevToConfig
    >>> art = Article(title="T", slug="t", content_markdown="x", tags=["py", "web"])
    >>> res = asyncio.run(publish(
    ...     art, canonical_url="https://me.substack.com/p/t",
    ...     config=DevToConfig(), secrets={"api_key": "k"},
    ... ))
    >>> res.detail["payload"]["article"]["canonical_url"]
    'https://me.substack.com/p/t'
    >>> res.detail["payload"]["article"]["tags"]  # comma-separated string, not a list
    'py,web'
    >>> res.detail["payload"]["article"]["published"]  # draft default => False
    False
    """
    require_canonical_url(DEV_TO, canonical_url)
    api_key = secrets.get("api_key")
    payload = _build_payload(article, canonical_url, config)
    headers = {
        "api-key": api_key or "<DEVTO_API_KEY>",
        "Accept": "application/vnd.forem.api-v1+json",
        "Content-Type": "application/json",
    }

    # ----------------------------------------------------------------- #
    # TODO(network): replace this stub with the real httpx call.         #
    #                                                                    #
    # import httpx                                                       #
    # async with httpx.AsyncClient(timeout=30) as client:               #
    #     resp = await client.post(_ENDPOINT, json=payload, headers=headers)
    #     resp.raise_for_status()                                       #
    #     data = resp.json()                                            #
    #     return PublishResult.success(                                 #
    #         DEV_TO, url=data["url"],                                  #
    #         status="published" if data["published"] else "draft",    #
    #         canonical_url=canonical_url, detail={"id": data["id"]},   #
    #     )                                                             #
    # ----------------------------------------------------------------- #

    status = "published" if payload["article"]["published"] else "draft"
    _log.info("[dev_to] STUB: would POST %s (%s)", _ENDPOINT, status)
    return PublishResult.success(
        DEV_TO,
        url=None,
        status=status,
        canonical_url=canonical_url,
        detail={
            "stub": True,
            "endpoint": _ENDPOINT,
            "credentialed": bool(api_key),
            "payload": payload,
        },
    )
