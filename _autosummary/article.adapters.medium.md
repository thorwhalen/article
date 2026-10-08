# article.adapters.medium

Medium adapter — Phase 2, as an honest manual step (“Import a story”).

Medium’s REST API is closed to new integrations (no new integration tokens
are issued, and the API docs repository is archived), so this adapter does
**not** post anything. Medium’s own *Import a story* tool is the supported
route, and it sets the imported story’s canonical link to the original URL,
which is exactly the SEO handoff this pipeline exists for.

The adapter returns a [`manual()`](article.base.md#article.base.PublishResult.manual) result whose
`next_step` names the URL to import and where to paste it. Nothing is ever
published to Medium.

### Module Attributes

| [`MEDIUM_IMPORT_URL`](#article.adapters.medium.MEDIUM_IMPORT_URL)   | Medium's "Import a story" page (Profile menu > Stories > Import a story).   |
|----------------------------------------------------------------------|-----------------------------------------------------------------------------|

### Functions

| [`import_steps`](#article.adapters.medium.import_steps)(canonical_url)                      | The one-line instruction for importing `canonical_url` into Medium.      |
|---------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------|
| [`publish`](#article.adapters.medium.publish)(article, \*, canonical_url, config, ...) | Return the *Import a story* step for `article`; sends nothing to Medium. |

### article.adapters.medium.MEDIUM_IMPORT_URL *= 'https://medium.com/p/import'*

Medium’s “Import a story” page (Profile menu > Stories > Import a story).

### article.adapters.medium.import_steps(canonical_url)

The one-line instruction for importing `canonical_url` into Medium.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

```pycon
>>> import_steps("https://me.substack.com/p/t")
'Once https://me.substack.com/p/t is live, open https://medium.com/p/import, ...'
```

### *async* article.adapters.medium.publish(article, , canonical_url, config, secrets)

Return the *Import a story* step for `article`; sends nothing to Medium.

* **Return type:**
  [`PublishResult`](article.base.md#article.base.PublishResult)

```pycon
>>> import asyncio
>>> from article.config import Article, MediumConfig
>>> art = Article(title="T", slug="t", content_markdown="x")
>>> res = asyncio.run(publish(
...     art, canonical_url="https://me.substack.com/p/t",
...     config=MediumConfig(), secrets={},
... ))
>>> res.state.value, res.detail["import_url"]
('manual', 'https://me.substack.com/p/t')
```
