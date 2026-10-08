# article.md_source

Read an article from a plain Markdown file (no JSON envelope needed).

A Markdown file becomes the fields of an [`Article`](article.config.md#article.config.Article):

- **Front matter** (a leading `---` YAML block) supplies any article field
  directly: `title`, `subtitle`, `slug`, `tags`, `description`,
  `platforms`, …
- **Title**: front matter `title`, else the level-1 ATX heading
  (`# Title`) when there is exactly one, or when the first of several opens
  the file; anything else is ambiguous and refused. The heading used as the
  title is removed from the body, since every platform renders the title itself.
- **Slug**: front matter `slug`, else derived from the title.

```pycon
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
```

### Functions

| [`markdown_to_fields`](#article.md_source.markdown_to_fields)(text, \*[, origin])   | Article fields from Markdown text: front matter, then the H1 title, then the slug.   |
|-------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------|
| [`slugify`](#article.md_source.slugify)(text)                            | A URL-safe slug: ASCII-folded, lowercase, hyphen-joined alphanumerics.               |

### article.md_source.markdown_to_fields(text, , origin='<markdown>')

Article fields from Markdown text: front matter, then the H1 title, then the slug.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]

### article.md_source.slugify(text)

A URL-safe slug: ASCII-folded, lowercase, hyphen-joined alphanumerics.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

```pycon
>>> slugify("Déjà vu: the Agile Religion & the Agentic Reformation")
'deja-vu-the-agile-religion-the-agentic-reformation'
```
