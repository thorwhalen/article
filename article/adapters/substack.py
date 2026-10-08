"""Substack adapter — Phase 1 primary: an **unpublished draft**, via python-substack.

Substack has no official write API. This adapter uses the unofficial
`python-substack <https://github.com/ma2za/python-substack>`_ library (MIT;
install with ``pip install 'article[substack]'``), which converts Markdown to
Substack's editor document, including ``[^n]`` footnotes,
``![alt](src "caption")`` captions and ``$...$`` LaTeX, and uploads local
images to Substack's CDN.

**Drafts only.** The adapter creates a draft and stops; it has no code path
that publishes. Review the draft in the Substack editor and publish it there.
``publish_as_draft=False`` is refused with an explanation.

Before anything is uploaded, :func:`preflight` checks the Markdown for what
the converter would lose silently, and refuses it with every problem listed:

- **tables** (Substack has no table node): refused by default, or kept as a
  monospace code block with ``tables="code"``, or replaced by whatever a
  callable returns (e.g. a rendered image), never dropped;
- an **image sharing a paragraph with text** (the converter keeps only its
  alt text): put the image in its own paragraph, caption in the title slot;
- a **local image that does not exist** (paths resolve against the article's
  ``assets_dir``, the source file's directory);
- a **raw HTML block** (the converter drops it).

The result's ``url`` is the post's public address once published
(``<publication>/p/<slug>``), which the engine records as the canonical URL;
``detail["edit_url"]`` opens the draft in the editor.

The client is a seam: pass ``api=`` (anything with python-substack's ``Api``
methods) to :func:`create_substack_draft`; tests pass a fake.
"""

from __future__ import annotations

import asyncio
import os
import re
import threading
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, Literal, Mapping, Optional, Union
from urllib.parse import unquote, urlsplit

from ..base import SUBSTACK, AdapterError, PublishResult
from ..config import Article, SubstackConfig
from ..registry import register_adapter
from ..util import coalesce, get_logger

_log = get_logger()

#: How a Markdown table is handled: refuse it, keep it as a code block, or
#: replace it with the Markdown a callable returns (e.g. an image reference).
TablePolicy = Union[Literal["error", "code"], Callable[[str], str]]

_INSTALL_HINT = "install the Substack extra: pip install 'article[substack]'"
_AUTH_HINT = (
    "set SUBSTACK_COOKIES (the cookie header copied from a logged-in browser), "
    "SUBSTACK_COOKIES_PATH (a cookies JSON file), or SUBSTACK_EMAIL and "
    "SUBSTACK_PASSWORD; see the README section 'Substack credentials'"
)


# --------------------------------------------------------------------------- #
# Preflight: refuse what the converter would drop silently                    #
# --------------------------------------------------------------------------- #


def _markdown_parser():
    """A parser that sees what python-substack's does, plus tables (which it skips)."""
    try:
        from markdown_it import MarkdownIt
        from mdit_py_plugins.dollarmath import dollarmath_plugin
        from mdit_py_plugins.footnote import footnote_plugin
    except ImportError as e:  # pragma: no cover - exercised only without the extra
        raise AdapterError(f"substack: {_INSTALL_HINT}") from e
    return (
        MarkdownIt("commonmark")
        .use(footnote_plugin)
        .use(dollarmath_plugin, allow_space=False, allow_digits=False)
        .enable("table")
    )


def _is_local(src: str) -> bool:
    """What python-substack uploads from disk: anything not http(s) or ``//``."""
    return urlsplit(src).scheme.lower() not in ("http", "https") and not (
        src.startswith("//")
    )


def _code_table(table_markdown: str) -> str:
    return f"```\n{table_markdown.rstrip()}\n```\n"


def _replace_tables(
    markdown: str, tokens: list, policy: TablePolicy, problems: list[str]
) -> str:
    lines = markdown.splitlines(keepends=True)
    tables = [t for t in tokens if t.type == "table_open"]
    if policy == "error":
        for t in tables:
            problems.append(
                f"{_where(t, lines)}: a table (Substack has no table; pass "
                f"tables='code' to keep it as a code block, or render it to an image)"
            )
        return markdown
    render = _code_table if policy == "code" else policy
    if not callable(render):
        raise AdapterError(f"substack: unknown tables policy {policy!r}")
    for t in reversed(tables):  # bottom-up, so earlier line numbers stay valid
        start, end = t.map
        if t.level != 0:
            problems.append(
                f"{_where(t, lines)}: a table nested in a list or quote; move it to "
                f"the top level so it can be replaced"
            )
            continue
        lines[start:end] = [render("".join(lines[start:end]))]
    return "".join(lines)


def _image_problems(
    tokens: list, lines: list[str], assets_dir: Optional[str]
) -> Iterator[str]:
    base = Path(assets_dir) if assets_dir else Path.cwd()
    for i, tok in enumerate(tokens):
        if tok.type != "inline" or not tok.children:
            continue
        images = [c for c in tok.children if c.type == "image"]
        if not images:
            continue
        line = _where(tok, lines)
        in_paragraph = i > 0 and tokens[i - 1].type == "paragraph_open"
        if not in_paragraph or not _is_image_only(tok.children):
            yield (
                f"{line}: an image shares its paragraph or heading with "
                f"text, and Substack would keep only its alt text; give the image "
                f'its own paragraph and put the caption in the title: ![alt](src "caption")'
            )
        for img in images:
            src = img.attrs.get("src", "")
            if src.lower().startswith("data:"):
                yield f"{line}: an inline data: image cannot be uploaded; save it as a file"
            elif (
                _is_local(src)
                and not (base / Path(unquote(src)).expanduser()).is_file()
            ):
                yield f"{line}: image file not found: {src} (looked in {base})"


def _is_image_only(children: list) -> bool:
    kids = [c for c in children if c.type != "softbreak"]
    if len(kids) == 1 and kids[0].type == "image":
        return True
    return (
        len(kids) == 3
        and kids[0].type == "link_open"
        and kids[1].type == "image"
        and kids[2].type == "link_close"
    )


def _where(tok, lines: list[str]) -> str:
    """``body line N ("text")``: line numbers count from the body, so quote the line."""
    if not tok.map:
        return "in a footnote"
    text = lines[tok.map[0]].strip() if tok.map[0] < len(lines) else ""
    text = text if len(text) <= 50 else text[:47] + "..."
    return f'body line {tok.map[0] + 1} ("{text}")'


def _html_problems(tokens: list, lines: list[str]) -> Iterator[str]:
    for tok in tokens:
        if tok.type == "html_block" and not tok.content.lstrip().startswith("<!--"):
            snippet = tok.content.strip().splitlines()[0][:60]
            yield f"{_where(tok, lines)}: a raw HTML block ({snippet}) would be dropped"


def _html_inline_warnings(tokens: list, lines: list[str]) -> Iterator[str]:
    for tok in tokens:
        if tok.type == "inline" and tok.children:
            for c in tok.children:
                if c.type == "html_inline" and not c.content.startswith("<!--"):
                    yield f"{_where(tok, lines)}: inline HTML {c.content} is dropped"


_UNDEFINED_REF = re.compile(r"\[\^[^\]\s]+\]")


def _footnote_problems(tokens: list, lines: list[str], env: dict) -> Iterator[str]:
    """What the converter mis-numbers or drops: nested, undefined and unused notes."""
    depth = 0
    for tok in tokens:
        if tok.type == "footnote_open":
            depth += 1
        elif tok.type == "footnote_close":
            depth -= 1
        for child in tok.children or ():
            if child.type == "footnote_ref":
                if depth:
                    yield (
                        f"footnote [^{child.meta.get('label')}] is referenced inside "
                        f"another footnote, which Substack numbers wrongly"
                    )
            elif child.type == "text":
                undefined = _UNDEFINED_REF.search(child.content)
                if undefined:
                    yield (
                        f"{_where(tok, lines)}: {undefined.group(0)} has no "
                        f"definition, so it would stay as plain text"
                    )
    # The footnote plugin emits no tokens for an unreferenced definition; its
    # parse env marks one with id -1 under the key ":<label>".
    refs = env.get("footnotes", {}).get("refs", {})
    for key in sorted(k for k, v in refs.items() if v == -1):
        yield f"footnote [^{key[1:]}] is defined but never referenced, so it would be dropped"


def preflight(
    markdown: str,
    *,
    assets_dir: Optional[str] = None,
    tables: TablePolicy = "error",
) -> tuple[str, list[str]]:
    """Check ``markdown`` for content Substack would lose; return it ready to convert.

    Returns ``(markdown, warnings)``, where tables have been replaced per
    ``tables``. Raises :class:`~article.base.AdapterError` listing every
    problem at once.

    >>> md, warnings = preflight("| a | b |\\n|---|---|\\n| 1 | 2 |\\n", tables="code")
    >>> md.splitlines()[0]
    '```'
    >>> preflight("| a | b |\\n|---|---|\\n| 1 | 2 |\\n")  # doctest: +ELLIPSIS
    Traceback (most recent call last):
    ...
    article.base.AdapterError: substack: 1 problem(s) ... body line 1 ("| a | b |"): a table ...
    """
    parser = _markdown_parser()
    problems: list[str] = []
    markdown = _replace_tables(markdown, parser.parse(markdown), tables, problems)
    env: dict = {}
    tokens, lines = parser.parse(markdown, env), markdown.splitlines()
    problems += _image_problems(tokens, lines, assets_dir)
    problems += _html_problems(tokens, lines)
    problems += _footnote_problems(tokens, lines, env)
    if problems:
        raise AdapterError(
            f"substack: {len(problems)} problem(s) would lose content in the draft:\n"
            + "\n".join(f"  - {p}" for p in problems)
        )
    return markdown, list(_html_inline_warnings(tokens, lines))


# --------------------------------------------------------------------------- #
# Conversion and the client                                                   #
# --------------------------------------------------------------------------- #


_CWD_LOCK = threading.Lock()


@contextmanager
def _working_directory(path: Optional[str]) -> Iterator[None]:
    """python-substack resolves local image paths against the cwd.

    The cwd is process-wide, so conversions are serialized by a lock; a server
    that converts concurrently should first make image paths absolute instead.
    """
    if not path:
        yield
        return
    with _CWD_LOCK:
        previous = os.getcwd()
        os.chdir(path)
        try:
            yield
        finally:
            os.chdir(previous)


def draft_document(
    article: Article,
    markdown: str,
    *,
    config: SubstackConfig,
    api: Any = None,
    user_id: int = 0,
) -> dict:
    """The draft payload python-substack posts (``draft_body`` is a JSON string).

    With ``api=None`` nothing is uploaded and local image paths stay as they are.
    """
    try:
        from substack.post import Post
    except ImportError as e:
        raise AdapterError(f"substack: {_INSTALL_HINT}") from e
    post = Post(
        title=coalesce(config.title, article.title),
        subtitle=article.subtitle or "",
        user_id=user_id,
        audience=config.audience,
    )
    with _working_directory(article.assets_dir):
        post.from_markdown(markdown, api=api)
    return post.get_draft()


def make_substack_api(
    secrets: Mapping[str, Any], *, publication_url: Optional[str] = None
):
    """A logged-in python-substack ``Api`` from ``secrets`` (cookies preferred)."""
    try:
        from substack import Api
    except ImportError as e:
        raise AdapterError(f"substack: {_INSTALL_HINT}") from e
    common = {"publication_url": publication_url}
    if secrets.get("cookies"):
        return Api(cookies_string=secrets["cookies"], **common)
    if secrets.get("cookies_path"):
        path = Path(secrets["cookies_path"]).expanduser()
        if not path.is_file():
            raise AdapterError(f"substack: cookies file not found: {path}")
        return Api(cookies_path=str(path), **common)
    if secrets.get("email") and secrets.get("password"):
        return Api(email=secrets["email"], password=secrets["password"], **common)
    raise AdapterError(f"substack: no credentials; {_AUTH_HINT}")


def _publication_base(api: Any, configured: Optional[str]) -> str:
    """``https://<pub>`` from the configured URL, else from the client's API URL."""
    if configured:
        configured = configured.rstrip("/")
        return configured if "://" in configured else f"https://{configured}"
    return str(api.publication_url).rstrip("/").removesuffix("/api/v1")


def summarize_document(draft: Mapping[str, Any]) -> dict[str, int]:
    """Count what survived conversion: footnotes, images, captions, LaTeX, ...

    >>> summarize_document({"draft_body": '{"type": "doc", "content": '
    ...     '[{"type": "footnote", "content": []}]}'})
    {'footnotes': 1}
    """
    import json

    body = draft["draft_body"]
    body = json.loads(body) if isinstance(body, str) else body
    counts: Counter = Counter()

    def walk(node: Mapping[str, Any]) -> None:
        counts[node.get("type")] += 1
        for child in node.get("content") or ():
            walk(child)

    walk(body)
    names = {
        "footnoteAnchor": "footnote_refs",
        "footnote": "footnotes",
        "captionedImage": "images",
        "caption": "captions",
        "latex": "latex_inline",
        "latex_block": "latex_blocks",
        "codeBlock": "code_blocks",
        "heading": "headings",
        "paragraph": "paragraphs",
    }
    return {name: counts[t] for t, name in names.items() if counts[t]}


def dry_run(
    article: Article,
    *,
    config: Optional[SubstackConfig] = None,
    tables: Optional[TablePolicy] = None,
) -> dict[str, Any]:
    """Preflight and convert ``article`` without credentials or network; report counts."""
    config = config or article.platforms.substack or SubstackConfig()
    markdown, warnings = preflight(
        article.content_markdown,
        assets_dir=article.assets_dir,
        tables=coalesce(tables, config.tables),
    )
    draft = draft_document(article, markdown, config=config)
    return {
        "title": draft["draft_title"],
        "subtitle": draft["draft_subtitle"],
        "slug": article.slug,
        "counts": summarize_document(draft),
        "warnings": warnings,
    }


def create_substack_draft(
    article: Article,
    *,
    config: Optional[SubstackConfig] = None,
    secrets: Optional[Mapping[str, Any]] = None,
    api: Any = None,
    tables: Optional[TablePolicy] = None,
) -> PublishResult:
    """Create an **unpublished** Substack draft of ``article``; never publishes.

    ``api`` defaults to a python-substack ``Api`` built from ``secrets``;
    ``tables`` defaults to ``config.tables``.
    """
    config = config or article.platforms.substack or SubstackConfig()
    secrets = secrets or {}
    if not config.publish_as_draft:
        raise AdapterError(
            "substack: this tool only creates drafts; publish from the Substack "
            "editor (remove publish_as_draft=false from the article)"
        )
    markdown, warnings = preflight(
        article.content_markdown,
        assets_dir=article.assets_dir,
        tables=coalesce(tables, config.tables),
    )
    configured_url = coalesce(config.publication_url, secrets.get("publication_url"))
    if api is None:
        api = make_substack_api(secrets, publication_url=configured_url)
    publication = _publication_base(api, configured_url)

    draft = draft_document(
        article, markdown, config=config, api=api, user_id=api.get_user_id()
    )
    created = api.post_draft(draft)
    draft_id = created.get("id")
    settings = {
        "slug": article.slug,
        "search_engine_description": article.description,
        "draft_section_id": config.section_id,
    }
    edit_url = f"{publication}/publish/post/{draft_id}"
    try:
        updated = api.put_draft(
            draft_id, **{k: v for k, v in settings.items() if v is not None}
        )
        tags = coalesce(config.tags, article.tags)
        if tags:
            api.add_tags_to_post(draft_id, list(tags))
    except Exception as e:
        raise AdapterError(
            f"substack: draft {draft_id} was created ({edit_url}) but setting its "
            f"slug/tags failed: {e}"
        ) from e
    # Substack may adjust a slug (e.g. one already taken); trust what it answers.
    slug = (updated or {}).get("slug") or article.slug
    if slug != article.slug:
        warnings.append(f"Substack changed the slug from {article.slug!r} to {slug!r}")

    public_url = f"{publication}/p/{slug}"
    _log.info(
        "[substack] draft %s created; public URL once published: %s",
        draft_id,
        public_url,
    )
    return PublishResult.success(
        SUBSTACK,
        url=public_url,
        status="draft",
        canonical_url=public_url,
        detail={
            "draft_id": draft_id,
            "edit_url": edit_url,
            "counts": summarize_document(draft),
            "warnings": warnings,
        },
    )


@register_adapter(SUBSTACK)
async def publish(
    article: Article,
    *,
    canonical_url: Optional[str] = None,  # ignored: the primary defines canonical
    config: SubstackConfig,
    secrets: Mapping[str, Any],
    api: Any = None,
    tables: Optional[TablePolicy] = None,
) -> PublishResult:
    """Registry entry point: :func:`create_substack_draft` off the event loop.

    The name is the registry's contract; what it does is create a **draft**.
    """
    return await asyncio.to_thread(
        create_substack_draft,
        article,
        config=config,
        secrets=secrets,
        api=api,
        tables=tables,
    )
