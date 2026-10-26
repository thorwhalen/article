# article.adapters.substack

Substack adapter — Phase 1 primary: an **unpublished draft**, via python-substack.

Substack has no official write API. This adapter uses the unofficial
[python-substack](https://github.com/ma2za/python-substack) library (MIT;
install with `pip install 'article[substack]'`), which converts Markdown to
Substack’s editor document, including `[^n]` footnotes,
`![alt](src "caption")` captions and `$...$` LaTeX, and uploads local
images to Substack’s CDN.

**Drafts only.** The adapter creates a draft and stops; it has no code path
that publishes. Review the draft in the Substack editor and publish it there.
`publish_as_draft=False` is refused with an explanation.

Before anything is uploaded, [`preflight()`](#article.adapters.substack.preflight) checks the Markdown for what
the converter would lose silently, and refuses it with every problem listed:

- **tables** (Substack has no table node): refused by default, kept as a
  monospace code block with `tables="code"`, rendered to a PNG with
  `tables="image"` (needs Pillow: `pip install 'article[images]'`), or replaced
  by whatever a callable returns, never dropped;
- an **image sharing a paragraph with text** (the converter keeps only its
  alt text): put the image in its own paragraph, caption in the title slot;
- a **local image that does not exist** (paths resolve against the article’s
  `assets_dir`, the source file’s directory) or that sits \*\*inside a list, quote
  or footnote\*\* (Substack’s editor is not known to accept those; move it to the top
  level). Local image paths are rewritten to absolute ones, so conversion never
  depends on, or changes, the process’s working directory;
- a **raw HTML block** (the converter drops it).

The result’s `url` is the post’s public address once published
(`<publication>/p/<slug>`), which the engine records as the canonical URL;
`detail["edit_url"]` opens the draft in the editor.

**Updating in place.** With `config.draft_id` set (the CLI’s `--update` fills it
from the state store), the existing draft is rewritten with python-substack’s
`update_draft_from_markdown` instead of creating a new one. The draft’s revision
(recorded when it was created or last updated) guards against clobbering edits made
in Substack’s editor: a changed draft is refused unless `config.overwrite_edits`.
The title is not updated in place.

The client is a seam: pass `api=` (anything with python-substack’s `Api`
methods) to [`create_substack_draft()`](#article.adapters.substack.create_substack_draft); tests pass a fake.

### Module Attributes

| [`TablePolicy`](#article.adapters.substack.TablePolicy)   | refuse it, keep it as a code block, or replace it with the Markdown a callable returns (e.g. an image reference).   |
|----------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------|

### Functions

| [`create_substack_draft`](#article.adapters.substack.create_substack_draft)(article, \*[, config, ...])   | Create an **unpublished** Substack draft of `article`; never publishes.                                            |
|------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------|
| [`draft_document`](#article.adapters.substack.draft_document)(article, markdown, \*, config)       | The draft payload python-substack posts (`draft_body` is a JSON string).                                           |
| [`dry_run`](#article.adapters.substack.dry_run)(article, \*[, config, tables])              | Preflight and convert `article` without credentials or network; report counts.                                     |
| [`image_size`](#article.adapters.substack.image_size)(path)                                    | `(width, height)` of a PNG, GIF or JPEG file read from its header, else `None`.                                    |
| [`make_substack_api`](#article.adapters.substack.make_substack_api)(secrets, \*[, publication_url])   | A logged-in python-substack `Api` from `secrets` (cookies preferred).                                              |
| [`preflight`](#article.adapters.substack.preflight)(markdown, \*[, assets_dir, tables])       | Check `markdown` for content Substack would lose; return it ready to convert.                                      |
| [`publish`](#article.adapters.substack.publish)(article, \*[, canonical_url, api, tables])  | Registry entry point: [`create_substack_draft()`](#article.adapters.substack.create_substack_draft) off the event loop. |
| [`render_table_image`](#article.adapters.substack.render_table_image)(table_markdown, \*[, ...])       | Render a Markdown table to a PNG and return the Markdown image that shows it.                                      |
| [`summarize_document`](#article.adapters.substack.summarize_document)(draft)                           | Count what survived conversion: footnotes, images, captions, LaTeX, ...                                            |

### article.adapters.substack.TablePolicy

refuse it, keep it as a code block, or
replace it with the Markdown a callable returns (e.g. an image reference).

* **Type:**
  How a Markdown table is handled

alias of [`Literal`](https://docs.python.org/3/library/typing.html#typing.Literal)[‘error’, ‘code’, ‘image’] | `Callable`[[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)], [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]

### article.adapters.substack.create_substack_draft(article, , config=None, secrets=None, api=None, tables=None)

Create an **unpublished** Substack draft of `article`; never publishes.

`api` defaults to a python-substack `Api` built from `secrets`;
`tables` defaults to `config.tables`.

* **Return type:**
  [`PublishResult`](article.base.html.md#article.base.PublishResult)

### article.adapters.substack.draft_document(article, markdown, , config, api=None, user_id=0)

The draft payload python-substack posts (`draft_body` is a JSON string).

`markdown` is what [`preflight()`](#article.adapters.substack.preflight) returned (its local image paths are
absolute). With `api=None` nothing is uploaded.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### article.adapters.substack.dry_run(article, , config=None, tables=None)

Preflight and convert `article` without credentials or network; report counts.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]

### article.adapters.substack.image_size(path)

`(width, height)` of a PNG, GIF or JPEG file read from its header, else `None`.

Stdlib only; other formats are measured with Pillow when it is installed.

* **Return type:**
  [`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`int`](https://docs.python.org/3/builtins/functions.html#int), [`int`](https://docs.python.org/3/builtins/functions.html#int)]]

### article.adapters.substack.make_substack_api(secrets, , publication_url=None)

A logged-in python-substack `Api` from `secrets` (cookies preferred).

### article.adapters.substack.preflight(markdown, , assets_dir=None, tables='error')

Check `markdown` for content Substack would lose; return it ready to convert.

Returns `(markdown, warnings)`, where tables have been replaced per
`tables`. Raises [`AdapterError`](article.base.html.md#article.base.AdapterError) listing every
problem at once.

```pycon
>>> md, warnings = preflight("| a | b |\n|---|---|\n| 1 | 2 |\n", tables="code")
>>> md.splitlines()[0]
'```'
>>> preflight("| a | b |\n|---|---|\n| 1 | 2 |\n")
Traceback (most recent call last):
...
article.base.AdapterError: substack: 1 problem(s) ... body line 1 ("| a | b |"): a table ...
```

* **Return type:**
  [`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]]

### *async* article.adapters.substack.publish(article, , canonical_url=None, config, secrets, api=None, tables=None)

Registry entry point: [`create_substack_draft()`](#article.adapters.substack.create_substack_draft) off the event loop.

The name is the registry’s contract; what it does is create a **draft**.

* **Return type:**
  [`PublishResult`](article.base.html.md#article.base.PublishResult)

### article.adapters.substack.render_table_image(table_markdown, , out_dir=None, scale=2)

Render a Markdown table to a PNG and return the Markdown image that shows it.

The file name is the content hash, so re-running reuses the file. Needs Pillow.
`out_dir` defaults to a folder under the system temp directory.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### article.adapters.substack.summarize_document(draft)

Count what survived conversion: footnotes, images, captions, LaTeX, …

```pycon
>>> summarize_document({"draft_body": '{"type": "doc", "content": '
...     '[{"type": "footnote", "content": []}]}'})
{'footnotes': 1}
```

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`int`](https://docs.python.org/3/builtins/functions.html#int)]
