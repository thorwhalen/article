"""Hashnode adapter — Phase 2 syndication via the Hashnode GraphQL API (``httpx``).

Endpoint (verified against Hashnode's generated ``schema.graphql``)::

    POST https://gql.hashnode.com

Auth (a common gotcha)::

    Authorization: <PersonalAccessToken>     # RAW token, NO "Bearer" prefix

Canonical SEO: the **``originalArticleURL``** field of the input carries the
Substack SSOT URL.

Draft vs publish (encoded here — verified, and it *drifts*):

- ``publishPost(input: PublishPostInput!)`` **always publishes live** — there
  is no draft flag on it.
- To create a **draft**, use the *separate* ``createDraft(input: CreateDraftInput!)``
  mutation (its input mirrors ``PublishPostInput``).

So this adapter picks the mutation based on ``config.publish_as_draft``. The
older ``createPublicationStory`` mutation and ``api.hashnode.com`` host are
removed — don't use them.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from ..base import HASHNODE, AdapterError, PublishResult
from ..config import Article, HashnodeConfig
from ..registry import register_adapter
from ..util import coalesce, get_logger, require_canonical_url

_log = get_logger()

_ENDPOINT = "https://gql.hashnode.com"

_PUBLISH_MUTATION = (
    "mutation PublishPost($input: PublishPostInput!) "
    "{ publishPost(input: $input) { post { id slug url } } }"
)
_DRAFT_MUTATION = (
    "mutation CreateDraft($input: CreateDraftInput!) "
    "{ createDraft(input: $input) { draft { id slug } } }"
)


def _tags(article: Article, config: HashnodeConfig) -> list[dict]:
    """Hashnode tag inputs: ``{name, slug}`` per tag (id wins if both given)."""
    tags = coalesce(config.tags, article.tags) or []
    return [{"name": t, "slug": t.lower().replace(" ", "-")} for t in tags]


def _build_input(article: Article, canonical_url: str, config: HashnodeConfig, publication_id: str) -> dict:
    """The shared input for ``publishPost`` / ``createDraft`` (canonical injected)."""
    payload = {
        "title": coalesce(config.title, article.title),
        "subtitle": coalesce(config.subtitle, article.subtitle),
        "publicationId": publication_id,
        "contentMarkdown": article.content_markdown,
        "slug": article.slug,
        "tags": _tags(article, config),
        "originalArticleURL": canonical_url,  # <-- SEO canonical back to the SSOT
        "seriesId": config.series_id,
    }
    if article.cover_image_url:
        payload["coverImageOptions"] = {"coverImageURL": article.cover_image_url}
    # Drop unset optionals so the GraphQL request stays clean.
    return {k: v for k, v in payload.items() if v is not None}


@register_adapter(HASHNODE)
async def publish(
    article: Article,
    *,
    canonical_url: Optional[str],
    config: HashnodeConfig,
    secrets: Mapping[str, Any],
) -> PublishResult:
    """Syndicate ``article`` to Hashnode with ``originalArticleURL`` set to the SSOT.

    >>> import asyncio
    >>> from article.config import Article, HashnodeConfig
    >>> art = Article(title="T", slug="t", content_markdown="x", tags=["Python"])
    >>> res = asyncio.run(publish(
    ...     art, canonical_url="https://me.substack.com/p/t",
    ...     config=HashnodeConfig(publish_as_draft=True),
    ...     secrets={"token": "pat", "publication_id": "pub123"},
    ... ))
    >>> res.detail["variables"]["input"]["originalArticleURL"]
    'https://me.substack.com/p/t'
    >>> res.detail["mutation"].startswith("mutation CreateDraft")  # draft path
    True
    >>> res.detail["variables"]["input"]["tags"]
    [{'name': 'Python', 'slug': 'python'}]
    """
    require_canonical_url(HASHNODE, canonical_url)
    token = secrets.get("token")
    publication_id = coalesce(config.publication_id, secrets.get("publication_id"))
    if not publication_id:
        raise AdapterError(
            "hashnode: a publication_id is required (set platforms.hashnode.publication_id "
            "or HASHNODE_PUBLICATION_ID)"
        )

    mutation = _DRAFT_MUTATION if config.publish_as_draft else _PUBLISH_MUTATION
    variables = {"input": _build_input(article, canonical_url, config, publication_id)}
    headers = {
        "Authorization": token or "<HASHNODE_TOKEN>",  # RAW PAT, no "Bearer"
        "Content-Type": "application/json",
    }

    # ----------------------------------------------------------------- #
    # TODO(network): replace this stub with the real httpx GraphQL call. #
    #                                                                    #
    # import httpx                                                       #
    # async with httpx.AsyncClient(timeout=30) as client:               #
    #     resp = await client.post(                                     #
    #         _ENDPOINT, headers=headers,                               #
    #         json={"query": mutation, "variables": variables},        #
    #     )                                                             #
    #     resp.raise_for_status()                                       #
    #     body = resp.json()                                            #
    #     if body.get("errors"):                                        #
    #         return PublishResult.failure(HASHNODE, error=str(body["errors"]))
    #     data = body["data"]                                           #
    #     if config.publish_as_draft:                                   #
    #         return PublishResult.success(HASHNODE, status="draft",    #
    #             canonical_url=canonical_url, detail=data)             #
    #     post = data["publishPost"]["post"]                            #
    #     return PublishResult.success(HASHNODE, url=post["url"],       #
    #         status="published", canonical_url=canonical_url)          #
    # ----------------------------------------------------------------- #

    status = "draft" if config.publish_as_draft else "published"
    _log.info("[hashnode] STUB: would POST %s (%s)", _ENDPOINT, status)
    return PublishResult.success(
        HASHNODE,
        url=None,
        status=status,
        canonical_url=canonical_url,
        detail={
            "stub": True,
            "endpoint": _ENDPOINT,
            "credentialed": bool(token),
            "mutation": mutation,
            "variables": variables,
        },
    )
