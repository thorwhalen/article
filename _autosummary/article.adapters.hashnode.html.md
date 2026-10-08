# article.adapters.hashnode

Hashnode adapter — Phase 2 syndication via the Hashnode GraphQL API (`httpx`).

Endpoint (verified against Hashnode’s generated `schema.graphql`):

```default
POST https://gql.hashnode.com
```

Auth (a common gotcha):

```default
Authorization: <PersonalAccessToken>     # RAW token, NO "Bearer" prefix
```

Canonical SEO: the **\`\`originalArticleURL\`\`** field of the input carries the
Substack SSOT URL.

Draft vs publish (encoded here — verified, and it *drifts*):

- `publishPost(input: PublishPostInput!)` **always publishes live** — there
  is no draft flag on it.
- To create a **draft**, use the *separate* `createDraft(input: CreateDraftInput!)`
  mutation (its input mirrors `PublishPostInput`).

So this adapter picks the mutation based on `config.publish_as_draft`. The
older `createPublicationStory` mutation and `api.hashnode.com` host are
removed — don’t use them.

### Functions

| [`publish`](#article.adapters.hashnode.publish)(article, \*, canonical_url, config, ...)   | Syndicate `article` to Hashnode with `originalArticleURL` set to the SSOT.   |
|-----------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------|

### *async* article.adapters.hashnode.publish(article, , canonical_url, config, secrets)

Syndicate `article` to Hashnode with `originalArticleURL` set to the SSOT.

* **Return type:**
  [`PublishResult`](article.base.html.md#article.base.PublishResult)

```pycon
>>> import asyncio
>>> from article.config import Article, HashnodeConfig
>>> art = Article(title="T", slug="t", content_markdown="x", tags=["Python"])
>>> res = asyncio.run(publish(
...     art, canonical_url="https://me.substack.com/p/t",
...     config=HashnodeConfig(publish_as_draft=True),
...     secrets={"token": "pat", "publication_id": "pub123"},
... ))
>>> res.detail["variables"]["input"]["originalArticleURL"]
'https://me.substack.com/p/t'
>>> res.detail["mutation"].startswith("mutation CreateDraft")  # draft path
True
>>> res.detail["variables"]["input"]["tags"]
[{'name': 'Python', 'slug': 'python'}]
```
