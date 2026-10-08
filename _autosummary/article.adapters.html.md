# article.adapters

Built-in platform adapters.

Importing this package has the side effect of registering every built-in
adapter in [`article.registry`](article.registry.html.md#module-article.registry). The top-level [`article`](article.html.md#module-article) package
imports it, so the registry is populated as soon as `article` is imported.

To add a platform: drop a new module here that decorates an async function with
`@register_adapter("<name>")`, then import it below. No core code changes.

### Modules

| [`dev_to`](article.adapters.dev_to.html.md#module-article.adapters.dev_to)     | Dev.to adapter — Phase 2 syndication via the Forem API V1 (`httpx`).               |
|--------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------|
| [`hashnode`](article.adapters.hashnode.html.md#module-article.adapters.hashnode) | Hashnode adapter — Phase 2 syndication via the Hashnode GraphQL API (`httpx`).     |
| [`medium`](article.adapters.medium.html.md#module-article.adapters.medium)     | Medium adapter — Phase 2, as an honest manual step ("Import a story").             |
| [`substack`](article.adapters.substack.html.md#module-article.adapters.substack) | Substack adapter — Phase 1 primary: an **unpublished draft**, via python-substack. |
