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

- **tables** (Substack has no table node): refused by default, kept as a
  monospace code block with ``tables="code"``, rendered to a PNG with
  ``tables="image"`` (needs Pillow: ``pip install 'article[images]'``), or replaced
  by whatever a callable returns, never dropped;
- an **image sharing a paragraph with text** (the converter keeps only its
  alt text): put the image in its own paragraph, caption in the title slot;
- a **local image that does not exist** (paths resolve against the article's
  ``assets_dir``, the source file's directory) or that sits **inside a list, quote
  or footnote** (Substack's editor is not known to accept those; move it to the top
  level). Local image paths are rewritten to absolute ones, so conversion never
  depends on, or changes, the process's working directory;
- a **raw HTML block** (the converter drops it).

The result's ``url`` is the post's public address once published
(``<publication>/p/<slug>``), which the engine records as the canonical URL;
``detail["edit_url"]`` opens the draft in the editor.

**Updating in place.** With ``config.draft_id`` set (the CLI's ``--update`` fills it
from the state store), the existing draft is rewritten with python-substack's
``update_draft_from_markdown`` instead of creating a new one. The draft's revision
(recorded when it was created or last updated) guards against clobbering edits made
in Substack's editor: a changed draft is refused unless ``config.overwrite_edits``.
The title is not updated in place.

The client is a seam: pass ``api=`` (anything with python-substack's ``Api``
methods) to :func:`create_substack_draft`; tests pass a fake.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Iterator, Literal, Mapping, Optional, Union
from urllib.parse import quote, unquote, urlsplit

from ..base import SUBSTACK, AdapterError, PublishResult
from ..config import Article, SubstackConfig
from ..registry import register_adapter
from ..util import coalesce, get_logger

_log = get_logger()

#: How a Markdown table is handled: refuse it, keep it as a code block, or
#: replace it with the Markdown a callable returns (e.g. an image reference).
TablePolicy = Union[Literal["error", "code", "image"], Callable[[str], str]]

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


def _split_row(line: str) -> list[str]:
    cells = re.split(r"(?<!\\)\|", line.strip().strip("|"))
    return [c.strip().replace("\\|", "|") for c in cells]


def render_table_image(
    table_markdown: str, *, out_dir: Optional[str] = None, scale: int = 2
) -> str:
    """Render a Markdown table to a PNG and return the Markdown image that shows it.

    The file name is the content hash, so re-running reuses the file. Needs Pillow.
    ``out_dir`` defaults to a folder under the system temp directory.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as e:
        raise AdapterError(
            "substack: tables='image' needs Pillow: pip install 'article[images]'"
        ) from e
    rows = [
        _split_row(line)
        for line in table_markdown.strip().splitlines()
        if not re.fullmatch(r"\s*\|?[\s:|-]+\|?\s*", line) or "-" not in line
    ]
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    font = ImageFont.load_default(size=14 * scale)
    pad = 6 * scale
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    col_w = [
        max(probe.textlength(row[c], font=font) for row in rows) + 2 * pad
        for c in range(width)
    ]
    row_h = int(14 * scale * 1.4) + 2 * pad
    image = Image.new("RGB", (int(sum(col_w)) + 1, row_h * len(rows) + 1), "white")
    draw = ImageDraw.Draw(image)
    for r, row in enumerate(rows):
        x = 0.0
        for c, cell in enumerate(row):
            box = (x, r * row_h, x + col_w[c], (r + 1) * row_h)
            if r == 0:
                draw.rectangle(box, fill="#eeeeee")
            draw.rectangle(box, outline="#999999")
            draw.text((x + pad, r * row_h + pad), cell, fill="black", font=font)
            x += col_w[c]
    folder = Path(out_dir) if out_dir else Path(tempfile.gettempdir()) / "article-tables"
    folder.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(table_markdown.encode("utf-8")).hexdigest()[:16]
    path = folder / f"table-{digest}.png"
    image.save(path)
    return f"![table]({quote(str(path))})\n"


def _replace_tables(
    markdown: str, tokens: list, policy: TablePolicy, problems: list[str]
) -> str:
    lines = markdown.splitlines(keepends=True)
    tables = [t for t in tokens if t.type == "table_open"]
    if policy == "error":
        for t in tables:
            problems.append(
                f"{_where(t, lines)}: a table (Substack has no table; pass "
                f"tables='code' to keep it as a code block, or tables='image' to "
                f"render it to a picture)"
            )
        return markdown
    render = {"code": _code_table, "image": render_table_image}.get(policy, policy)
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
        nested = in_paragraph and _is_image_only(tok.children) and (
            tokens[i - 1].level > 0 or not tok.map
        )
        for img in images:
            src = img.attrs.get("src", "")
            if nested and _is_local(src) and not src.lower().startswith("data:"):
                yield (
                    f"{line}: a local image inside a list, quote or footnote "
                    f"({src}); Substack's editor is not known to accept those, so "
                    f"move it to the top level"
                )
            elif src.lower().startswith("data:"):
                yield f"{line}: an inline data: image cannot be uploaded; save it as a file"
            elif (
                _is_local(src)
                and not (base / Path(unquote(src)).expanduser()).is_file()
            ):
                yield f"{line}: image file not found: {src} (looked in {base})"


def _absolute_images(
    markdown: str, tokens: list, assets_dir: Optional[str]
) -> str:
    """Rewrite each top-level image-only paragraph's local source to an absolute path.

    python-substack resolves local image paths against the process's working
    directory; absolute paths make conversion independent of it. Only images that
    passed :func:`_image_problems` (so image-only top-level paragraphs) get here.
    """
    base = Path(assets_dir) if assets_dir else Path.cwd()
    lines = markdown.splitlines(keepends=True)
    edits = []
    for i, tok in enumerate(tokens):
        if tok.type != "inline" or not tok.children or not tok.map:
            continue
        kids = [c for c in tok.children if c.type != "softbreak"]
        image = next((c for c in kids if c.type == "image"), None)
        if image is None or not _is_local(image.attrs.get("src", "")):
            continue
        if image.attrs["src"].lower().startswith("data:"):
            continue
        path = (base / Path(unquote(image.attrs["src"])).expanduser()).resolve()
        alt = image.content.replace("]", "\\]")
        title = image.attrs.get("title")
        title_part = f' "{title.replace(chr(34), chr(92) + chr(34))}"' if title else ""
        text = f"![{alt}](<{quote(str(path))}>{title_part})"
        if kids[0].type == "link_open":
            text = f"[{text}]({kids[0].attrs.get('href', '')})"
        edits.append((tok.map, text + "\n"))
    for (start, end), text in reversed(edits):  # bottom-up keeps line numbers valid
        lines[start:end] = [text]
    return "".join(lines)


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
    markdown = _absolute_images(markdown, tokens, assets_dir)
    return markdown, list(_html_inline_warnings(tokens, lines))


# --------------------------------------------------------------------------- #
# Conversion and the client                                                   #
# --------------------------------------------------------------------------- #


def draft_document(
    article: Article,
    markdown: str,
    *,
    config: SubstackConfig,
    api: Any = None,
    user_id: int = 0,
) -> dict:
    """The draft payload python-substack posts (``draft_body`` is a JSON string).

    ``markdown`` is what :func:`preflight` returned (its local image paths are
    absolute). With ``api=None`` nothing is uploaded.
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

    if config.draft_id is not None:
        return _update_draft(
            article, markdown, warnings, config=config, api=api, publication=publication
        )
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
            "revision": _revision_of(api, draft_id),
            "counts": summarize_document(draft),
            "warnings": warnings,
        },
    )


def _revision_of(api: Any, draft_id: Any) -> Optional[dict]:
    """The draft's current revision (python-substack's conflict-check fingerprint), or None."""
    try:
        from substack.revision import compute_draft_revision

        return compute_draft_revision(api.get_draft(draft_id))
    except Exception:  # an unreadable revision only makes the next update ask to overwrite
        return None


def _update_draft(
    article: Article,
    markdown: str,
    warnings: list[str],
    *,
    config: SubstackConfig,
    api: Any,
    publication: str,
) -> PublishResult:
    """Rewrite the existing draft ``config.draft_id`` from ``markdown``, never publishing."""
    draft_id = config.draft_id
    edit_url = f"{publication}/publish/post/{draft_id}"
    tags = coalesce(config.tags, article.tags)
    try:
        result = api.update_draft_from_markdown(
            draft_id,
            markdown,
            subtitle=article.subtitle or "",
            audience=config.audience,
            search_engine_description=article.description,
            slug=article.slug,
            draft_section_id=config.section_id,
            tags=list(tags) if tags else None,
            expected_revision=config.expected_revision,
            allow_image_replacement=True,  # the Markdown is the source of truth
            allow_conflict=config.overwrite_edits,
        )
    except Exception as e:
        hint = (
            " (edited in Substack since the last run; pass overwrite_edits / "
            "--overwrite-edits to replace those edits)"
            if type(e).__name__ == "DraftConflictError"
            else ""
        )
        raise AdapterError(
            f"substack: updating draft {draft_id} ({edit_url}) failed: {e}{hint}"
        ) from e
    slug = ((result or {}).get("draft") or {}).get("slug") or article.slug
    if slug != article.slug:
        warnings.append(f"Substack changed the slug from {article.slug!r} to {slug!r}")
    warnings.append("the title is not updated in place; change it in the Substack editor")
    public_url = f"{publication}/p/{slug}"
    return PublishResult.success(
        SUBSTACK,
        url=public_url,
        status="draft",
        canonical_url=public_url,
        detail={
            "draft_id": draft_id,
            "edit_url": edit_url,
            "updated_in_place": True,
            "revision": _revision_of(api, draft_id),
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
