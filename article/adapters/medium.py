"""Medium adapter — Phase 2 syndication via the Medium REST API (``httpx``).

Endpoint (verified against github.com/Medium/medium-api-docs)::

    POST https://api.medium.com/v1/users/{userId}/posts
    # or, under a publication:
    POST https://api.medium.com/v1/publications/{publicationId}/posts

Auth: ``Authorization: Bearer <integration_token>``. The ``{userId}`` comes
from ``GET /v1/me`` (``data.id``).

Canonical SEO: the **``canonicalUrl``** field carries the Substack SSOT URL so
Medium emits ``<link rel="canonical">`` back to it.

.. warning::
   Medium's API is officially **deprecated** ("no longer supported"; the docs
   repo is archived and no new OAuth apps are issued). It still works for a
   single user with a **self-issued integration token** (Settings → Security
   and apps → Integration tokens). We implement to the documented shape; the
   network body is a TODO stub.

Quirks encoded here: ``title`` is metadata only (the rendered title is the
first heading in ``content``); only the first **3** tags are honoured.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from ..base import MEDIUM, PublishResult
from ..config import Article, MediumConfig
from ..registry import register_adapter
from ..util import coalesce, get_logger, require_canonical_url

_log = get_logger()

_MEDIUM_MAX_TAGS = 3
_API_ROOT = "https://api.medium.com/v1"


def _endpoint(config: MediumConfig, user_id: Optional[str]) -> str:
    if config.publication_id:
        return f"{_API_ROOT}/publications/{config.publication_id}/posts"
    return f"{_API_ROOT}/users/{user_id or '{userId}'}/posts"


def _build_payload(article: Article, canonical_url: str, config: MediumConfig) -> dict:
    """Construct the Medium create-post JSON body (canonical injected, not optional)."""
    tags = coalesce(config.tags, article.tags) or []
    return {
        "title": coalesce(config.title, article.title),
        "contentFormat": "markdown",
        "content": article.content_markdown,
        "tags": tags[:_MEDIUM_MAX_TAGS],
        "canonicalUrl": canonical_url,  # <-- SEO canonical back to the SSOT
        "publishStatus": "draft" if config.publish_as_draft else "public",
        "license": config.license,
        "notifyFollowers": config.notify_followers,
    }


@register_adapter(MEDIUM)
async def publish(
    article: Article,
    *,
    canonical_url: Optional[str],
    config: MediumConfig,
    secrets: Mapping[str, Any],
) -> PublishResult:
    """Syndicate ``article`` to Medium with ``canonicalUrl`` pointing at the SSOT.

    >>> import asyncio
    >>> from article.config import Article, MediumConfig
    >>> art = Article(title="T", slug="t", content_markdown="x", tags=["a", "b", "c", "d"])
    >>> res = asyncio.run(publish(
    ...     art, canonical_url="https://me.substack.com/p/t",
    ...     config=MediumConfig(), secrets={"token": "tok", "user_id": "u1"},
    ... ))
    >>> res.detail["payload"]["canonicalUrl"]
    'https://me.substack.com/p/t'
    >>> res.detail["payload"]["tags"]  # capped at 3
    ['a', 'b', 'c']
    """
    require_canonical_url(MEDIUM, canonical_url)
    token = secrets.get("token")
    user_id = coalesce(config.publication_id, secrets.get("user_id"))
    payload = _build_payload(article, canonical_url, config)
    endpoint = _endpoint(config, secrets.get("user_id"))
    headers = {
        "Authorization": f"Bearer {token}" if token else "Bearer <MEDIUM_TOKEN>",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    # ----------------------------------------------------------------- #
    # TODO(network): replace this stub with the real httpx call.         #
    #                                                                    #
    # import httpx                                                       #
    # async with httpx.AsyncClient(timeout=30) as client:               #
    #     if not user_id and not config.publication_id:                 #
    #         me = await client.get(f"{_API_ROOT}/me", headers=headers) #
    #         me.raise_for_status()                                     #
    #         endpoint = _endpoint(config, me.json()["data"]["id"])     #
    #     resp = await client.post(endpoint, json=payload, headers=headers)
    #     resp.raise_for_status()                                       #
    #     data = resp.json()["data"]                                    #
    #     return PublishResult.success(                                 #
    #         MEDIUM, url=data["url"], status=data["publishStatus"],    #
    #         canonical_url=canonical_url, detail={"id": data["id"]},   #
    #     )                                                             #
    # ----------------------------------------------------------------- #

    status = payload["publishStatus"]
    _log.info("[medium] STUB: would POST %s (%s)", endpoint, status)
    return PublishResult.success(
        MEDIUM,
        url=None,
        status=status,
        canonical_url=canonical_url,
        detail={
            "stub": True,
            "endpoint": endpoint,
            "credentialed": bool(token),
            "payload": payload,
        },
    )
