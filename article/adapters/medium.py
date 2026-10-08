"""Medium adapter — Phase 2, as an honest manual step ("Import a story").

Medium's REST API is closed to new integrations (no new integration tokens
are issued, and the API docs repository is archived), so this adapter does
**not** post anything. Medium's own *Import a story* tool is the supported
route, and it sets the imported story's canonical link to the original URL,
which is exactly the SEO handoff this pipeline exists for.

The adapter returns a :meth:`~article.base.PublishResult.manual` result whose
``next_step`` names the URL to import and where to paste it. Nothing is ever
published to Medium.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from ..base import MEDIUM, PublishResult
from ..config import Article, MediumConfig
from ..registry import register_adapter
from ..util import require_canonical_url

#: Medium's "Import a story" page (Profile menu > Stories > Import a story).
MEDIUM_IMPORT_URL = "https://medium.com/p/import"


def import_steps(canonical_url: str) -> str:
    """The one-line instruction for importing ``canonical_url`` into Medium.

    >>> import_steps("https://me.substack.com/p/t")  # doctest: +ELLIPSIS
    'Once https://me.substack.com/p/t is live, open https://medium.com/p/import, ...'
    """
    return (
        f"Once {canonical_url} is live, open {MEDIUM_IMPORT_URL}, paste that URL "
        f"and press Import; Medium sets the canonical link to it. Review the "
        f"imported draft (footnotes, tables, captions) before publishing."
    )


@register_adapter(MEDIUM)
async def publish(
    article: Article,
    *,
    canonical_url: Optional[str],
    config: MediumConfig,
    secrets: Mapping[str, Any],
) -> PublishResult:
    """Return the *Import a story* step for ``article``; sends nothing to Medium.

    >>> import asyncio
    >>> from article.config import Article, MediumConfig
    >>> art = Article(title="T", slug="t", content_markdown="x")
    >>> res = asyncio.run(publish(
    ...     art, canonical_url="https://me.substack.com/p/t",
    ...     config=MediumConfig(), secrets={},
    ... ))
    >>> res.state.value, res.detail["import_url"]
    ('manual', 'https://me.substack.com/p/t')
    """
    require_canonical_url(MEDIUM, canonical_url)
    return PublishResult.manual(
        MEDIUM,
        next_step=import_steps(canonical_url),
        canonical_url=canonical_url,
        detail={"import_url": canonical_url, "import_page": MEDIUM_IMPORT_URL},
    )
