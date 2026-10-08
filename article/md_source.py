"""Read an article from a plain Markdown file (no JSON envelope needed).

A Markdown file becomes the fields of an :class:`~article.config.Article`:

- **Front matter** (a leading ``---`` YAML block) supplies any article field
  directly: ``title``, ``subtitle``, ``slug``, ``tags``, ``description``,
  ``platforms``, ...
- **Title**: front matter ``title``, else the first level-1 ATX heading
  (``# Title``). The heading used as the title is removed from the body,
  since every platform renders the title itself.
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
_H1 = re.compile(r"^#[ \t]+(.+?)[ \t]*#*[ \t]*$")
_FENCE = re.compile(r"^[ \t]{0,3}(```|~~~)")


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


def _pop_first_h1(body: str) -> tuple[str | None, str]:
    """Return the first ``# Heading`` outside code fences, and the body without it."""
    lines = body.splitlines(keepends=True)
    in_fence = False
    for i, line in enumerate(lines):
        if _FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = _H1.match(line.rstrip("\n"))
        if match:
            return match.group(1), "".join(lines[:i] + lines[i + 1 :])
    return None, body


def markdown_to_fields(text: str, *, origin: str = "<markdown>") -> dict[str, Any]:
    """Article fields from Markdown text: front matter, then the H1 title, then the slug."""
    fields, body = _split_front_matter(text, origin=origin)
    h1, body_without_h1 = _pop_first_h1(body)
    if "title" not in fields:
        if h1 is None:
            raise ArticleValidationError(
                f"No title in {origin}: add a '# Title' heading or a 'title:' "
                f"front-matter field"
            )
        fields["title"], body = h1, body_without_h1
    elif h1 is not None and h1.strip() == str(fields["title"]).strip():
        body = body_without_h1  # the same title twice would render twice
    fields.setdefault("slug", slugify(str(fields["title"])))
    fields["content_markdown"] = body.strip("\n") + "\n"
    return fields
