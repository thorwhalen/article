# article.adapters.dev_to

Dev.to adapter — Phase 2 syndication via the Forem API V1 (`httpx`).

Endpoint (verified against the Forem OpenAPI spec, `swagger/v1/api_v1.json`):

```default
POST https://dev.to/api/articles
```

Auth + headers:

```default
api-key: <YOUR_API_KEY>
Accept: application/vnd.forem.api-v1+json    # selects API V1
Content-Type: application/json
```

Canonical SEO: the **\`\`canonical_url\`\`** field (inside the wrapped `article`
object) carries the Substack SSOT URL.

Quirks encoded here (these *drift* — verified live):

- The payload is **wrapped** under a top-level `"article"` key; flat fields fail.
- In API V1, **\`\`tags\`\` is a comma-separated string**, not an array.
- `published: false` is the *only* draft control (no separate draft flag).

### Functions

| [`publish`](#article.adapters.dev_to.publish)(article, \*, canonical_url, config, ...)   | Syndicate `article` to Dev.to with `canonical_url` pointing at the SSOT.   |
|-----------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------|

### *async* article.adapters.dev_to.publish(article, , canonical_url, config, secrets)

Syndicate `article` to Dev.to with `canonical_url` pointing at the SSOT.

* **Return type:**
  [`PublishResult`](article.base.md#article.base.PublishResult)

```pycon
>>> import asyncio
>>> from article.config import Article, DevToConfig
>>> art = Article(title="T", slug="t", content_markdown="x", tags=["py", "web"])
>>> res = asyncio.run(publish(
...     art, canonical_url="https://me.substack.com/p/t",
...     config=DevToConfig(), secrets={"api_key": "k"},
... ))
>>> res.detail["payload"]["article"]["canonical_url"]
'https://me.substack.com/p/t'
>>> res.detail["payload"]["article"]["tags"]  # comma-separated string, not a list
'py,web'
>>> res.detail["payload"]["article"]["published"]  # draft default => False
False
```
