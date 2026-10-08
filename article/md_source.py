"""Read an article from a plain Markdown file (no JSON envelope needed).

A Markdown file becomes the fields of an :class:`~article.config.Article`:

- **Front matter** (a leading ``---`` YAML block) supplies any article field
  directly: ``title``, ``subtitle``, ``slug``, ``tags``, ``description``,
  ``platforms``, ...
- **Title**: front matter ``title``, else the level-1 ATX heading
  (``# Title``) when there is exactly one, or when the first of several opens
  the file; anything else is ambiguous and refused. The heading used as the
  title is removed from the body, since every platform renders the title itself.
- **Slug**: front matter ``slug``, else derived from the title.

>>> fields = markdown_to_fields('''---
... subtitle: A test
... tags: [a, b]
... ---
... # Hello, World!
...
... Body text.[^1]
...
... [^1]: A note.
... ''')
>>> fields["title"], fields["slug"], fields["subtitle"], fields["tags"]
('Hello, World!', 'hello-world', 'A test', ['a', 'b'])
>>> fields["content_markdown"].splitlines()[0]
'Body text.[^1]'
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

import yaml

from .base import ArticleValidationError

MARKDOWN_SUFFIXES = (".md", ".markdown")

_FRONT_MATTER = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*(?:\n|\Z)", re.DOTALL)
# CommonMark: an optional closing run of ``#`` only counts after a space ("C#" stays).
_H1 = re.compile(r"^ {0,3}#[ \t]+(.+?)(?:[ \t]+#+)?[ \t]*$")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")


def slugify(text: str) -> str:
    """A URL-safe slug: ASCII-folded, lowercase, hyphen-joined alphanumerics.

    >>> slugify("Déjà vu: the Agile Religion & the Agentic Reformation")
    'deja-vu-the-agile-religion-the-agentic-reformation'
    """
    ascii_text = (
        unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    )
    return "-".join(re.findall(r"[a-z0-9]+", ascii_text.lower()))


def _split_front_matter(text: str, *, origin: str) -> tuple[dict[str, Any], str]:
    match = _FRONT_MATTER.match(text)
    if not match:
        return {}, text
    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as e:
        raise ArticleValidationError(f"Invalid front matter in {origin}: {e}") from e
    if not isinstance(meta, dict):
        raise ArticleValidationError(
            f"Front matter in {origin} must be a mapping of article fields"
        )
    return meta, text[match.end() :]


def _h1_lines(lines: list[str]) -> list[tuple[int, str]]:
    """``(index, text)`` of every ``# Heading`` line outside code fences."""
    found, fence = [], None
    for i, line in enumerate(lines):
        match = _FENCE.match(line)
        if match:
            marker = match.group(1)
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = None  # only a matching run closes the fence
            continue
        if fence is None:
            heading = _H1.match(line.rstrip("\n"))
            if heading:
                found.append((i, heading.group(1)))
    return found


def _pop_title_h1(body: str, *, origin: str) -> tuple[str | None, str]:
    """The title heading (see the module doc) and the body without it."""
    lines = body.splitlines(keepends=True)
    h1s = _h1_lines(lines)
    if not h1s:
        return None, body
    i, text = h1s[0]
    opens_the_file = all(not line.strip() for line in lines[:i])
    if len(h1s) > 1 and not opens_the_file:
        raise ArticleValidationError(
            f"Ambiguous title in {origin}: {len(h1s)} '# ' headings and none opens "
            f"the file; add a 'title:' front-matter field"
        )
    return text, "".join(lines[:i] + lines[i + 1 :])


def markdown_to_fields(text: str, *, origin: str = "<markdown>") -> dict[str, Any]:
    """Article fields from Markdown text: front matter, then the H1 title, then the slug."""
    fields, body = _split_front_matter(text.lstrip("\ufeff"), origin=origin)
    if "title" in fields:
        # Drop a heading that only repeats the title; it would render twice.
        lines = body.splitlines(keepends=True)
        h1s = _h1_lines(lines)
        if h1s and h1s[0][1].strip() == str(fields["title"]).strip():
            body = "".join(lines[: h1s[0][0]] + lines[h1s[0][0] + 1 :])
    else:
        title, body = _pop_title_h1(body, origin=origin)
        if title is None:
            raise ArticleValidationError(
                f"No title in {origin}: add a '# Title' heading or a 'title:' "
                f"front-matter field"
            )
        fields["title"] = title
    if "slug" not in fields:
        fields["slug"] = slugify(str(fields["title"]))
        if not fields["slug"]:
            raise ArticleValidationError(
                f"No ASCII letters or digits in the title of {origin} to make a slug "
                f"from; add a 'slug:' front-matter field"
            )
    fields["content_markdown"] = body.strip("\n") + "\n"
    return fields
