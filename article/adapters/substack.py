"""Substack adapter — Phase 1 primary, via Playwright (async) browser automation.

Substack has no official public write API, so we drive the publication's own
web surface. Two paths exist (the internal REST routes under
``/api/v1/drafts``, and full browser automation); this adapter is structured
around **Playwright** because it survives editor changes better and reuses a
real logged-in session.

Flow:

1. Restore a saved Playwright ``storage_state`` (cookies/session) if present —
   so credentials aren't re-entered each run — else log in with the configured
   email/password and persist a fresh ``storage_state``.
2. Create a draft, fill title / subtitle / body, and publish.
3. Read back the **live public URL Substack assigns**
   (``https://<sub>.substack.com/p/<slug>``). That URL is the canonical SSOT
   the secondary platforms point at.

Human-like pacing (:func:`article.util.human_delay`) is used between scripted
actions so automating one's *own* account runs reliably.

.. note::
   The browser body is a clearly-marked TODO stub: it synthesizes the public
   URL deterministically so the end-to-end SSOT handoff is exercisable now.
   ``canonical_url`` is ignored here on purpose — the primary *defines* it.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from ..base import SUBSTACK, AdapterError, PublishResult
from ..config import Article, SubstackConfig
from ..registry import register_adapter
from ..util import coalesce, get_logger

_log = get_logger()


def _public_url(publication_url: str, slug: str) -> str:
    """The canonical public post URL Substack assigns: ``<pub>/p/<slug>``."""
    return f"{publication_url.rstrip('/')}/p/{slug}"


@register_adapter(SUBSTACK)
async def publish(
    article: Article,
    *,
    canonical_url: Optional[str] = None,  # ignored: the primary defines canonical
    config: SubstackConfig,
    secrets: Mapping[str, Any],
) -> PublishResult:
    """Publish ``article`` to Substack and return its live public URL.

    >>> import asyncio
    >>> from article.config import Article, SubstackConfig
    >>> art = Article(title="Hi", slug="hi-there", content_markdown="x")
    >>> res = asyncio.run(publish(
    ...     art,
    ...     config=SubstackConfig(publish_as_draft=False),
    ...     secrets={"publication_url": "https://me.substack.com"},
    ... ))
    >>> res.ok, res.url
    (True, 'https://me.substack.com/p/hi-there')
    """
    publication_url = coalesce(config.publication_url, secrets.get("publication_url"))
    if not publication_url:
        raise AdapterError(
            "substack: a publication_url is required (set platforms.substack.publication_url "
            "or SUBSTACK_PUBLICATION_URL) so the canonical public URL can be resolved"
        )

    session_path = secrets.get("session_path")
    min_delay = float(secrets.get("min_action_delay", 0.6))
    max_delay = float(secrets.get("max_action_delay", 2.4))

    # ----------------------------------------------------------------- #
    # TODO(playwright): replace this stub with the real browser flow.    #
    #                                                                    #
    # from playwright.async_api import async_playwright                  #
    # async with async_playwright() as p:                               #
    #     ctx_kwargs = {}                                                #
    #     if session_path and os.path.exists(session_path):             #
    #         ctx_kwargs["storage_state"] = session_path  # reuse login  #
    #     browser = await p.chromium.launch(headless=True)              #
    #     context = await browser.new_context(**ctx_kwargs)             #
    #     page = await context.new_page()                               #
    #     if "storage_state" not in ctx_kwargs:                         #
    #         await _login(page, secrets["email"], secrets["password"]) #
    #         await context.storage_state(path=session_path)  # persist  #
    #     await page.goto(f"{publication_url}/publish/post")            #
    #     await human_delay(min_delay, max_delay)                       #
    #     await page.fill("[data-testid=post-title]", article.title)    #
    #     ...  # fill body (markdown -> editor), set audience/section    #
    #     await _click_publish(page, send=config.send_email)            #
    #     live_url = page.url  # the assigned public URL                 #
    #     await browser.close()                                         #
    # ----------------------------------------------------------------- #

    live_url = _public_url(publication_url, article.slug)
    status = "draft" if config.publish_as_draft else "published"
    session_restored = bool(session_path)
    _log.info("[substack] STUB: would %s %r -> %s", status, article.slug, live_url)

    return PublishResult.success(
        SUBSTACK,
        url=live_url,
        status=status,
        canonical_url=live_url,  # the primary's URL *is* the canonical SSOT
        detail={
            "stub": True,
            "transport": "playwright(async)",
            "session_restored": session_restored,
            "audience": config.audience,
            "send_email": config.send_email,
            "pacing_seconds": [min_delay, max_delay],
        },
    )
