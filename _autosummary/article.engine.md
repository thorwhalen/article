# article.engine

Orchestration engine — the two-phase, canonical-URL SSOT pipeline.

The engine sequences the workflow, resolves adapters from the registry, and
injects each adapter’s config + secrets. It owns the one rule that makes the
whole package cohere:

> Phase 1 (`publish_primary`) publishes to the primary platform (Substack),
> captures the live public URL it assigns, and writes it to the state store
> as `canonical_url` — the single source of truth.

> Phase 2 (`syndicate_secondary`), run later, reads that `canonical_url`
> back and injects it into every secondary platform’s payload, so each emits
> `<link rel="canonical">` pointing at the primary. If phase 1 never ran,
> phase 2 refuses to proceed ([`CanonicalUrlMissing`](article.base.md#article.base.CanonicalUrlMissing)).

Reliability: a failure on one platform is caught, logged, recorded to the
state store, and the run continues with the remaining platforms — one failure
never aborts the sequence. Every phase returns a structured
[`RunSummary`](article.base.md#article.base.RunSummary).

Simple things simple (module-level [`publish_primary()`](#article.engine.publish_primary) /
[`syndicate_secondary()`](#article.engine.syndicate_secondary) build a default engine); complex things possible
(construct [`PipelineEngine`](#article.engine.PipelineEngine) with an injected store, settings, or adapter
resolver for testing and alternate backends).

### Functions

| [`build_engine`](#article.engine.build_engine)(\*[, settings, store])               | Construct a [`PipelineEngine`](#article.engine.PipelineEngine) with sensible defaults.   |
|----------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------|
| [`publish_primary`](#article.engine.publish_primary)(article, \*[, settings, store])   | Phase 1 facade: publish to the primary platform and record canonical_url.                             |
| [`syndicate_secondary`](#article.engine.syndicate_secondary)(article, \*[, settings, ...]) | Phase 2 facade: syndicate to secondaries with the canonical_url injected.                             |

### Classes

| [`PipelineEngine`](#article.engine.PipelineEngine)(settings, store[, ...])   | Coordinates the publishing phases over an injected store + settings.   |
|-------------------------------------------------------------------------------------------|------------------------------------------------------------------------|

### *class* article.engine.PipelineEngine(settings, store, resolve_adapter=<function get_adapter>)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Coordinates the publishing phases over an injected store + settings.

* **Parameters:**
  * **settings** ([`Settings`](article.config.md#article.config.Settings)) – secrets/runtime config facade.
  * **store** ([`MutableMapping`](https://docs.python.org/3/library/collections.abc.html#collections.abc.MutableMapping)) – the state store (any `MutableMapping` keyed by slug).
  * **resolve_adapter** ([`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)[[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)], [`PublishAdapter`](article.registry.md#article.registry.PublishAdapter)]) – registry lookup (injected for testing / overrides).

#### *async* publish_primary(article)

Publish to the primary platform and record its URL as `canonical_url`.

* **Return type:**
  [`RunSummary`](article.base.md#article.base.RunSummary)

#### resolve_adapter()

Resolve the adapter registered under `name`.

* **Return type:**
  [`PublishAdapter`](article.registry.md#article.registry.PublishAdapter)

```pycon
>>> get_adapter("nope")
Traceback (most recent call last):
...
article.base.UnknownPlatformError: ...no adapter registered for 'nope'...
```

#### *async* syndicate_secondary(article, , platforms=None)

Syndicate to each configured secondary, injecting the canonical URL.

Raises [`CanonicalUrlMissing`](article.base.md#article.base.CanonicalUrlMissing) if phase 1 hasn’t
recorded a canonical URL for this slug yet.

* **Return type:**
  [`RunSummary`](article.base.md#article.base.RunSummary)

### article.engine.build_engine(, settings=None, store=None)

Construct a [`PipelineEngine`](#article.engine.PipelineEngine) with sensible defaults.

Defaults: settings from `.env`/environment, and a JSON state store at
`settings.state_path`. Pass either explicitly to override (tests, alt backends).

* **Return type:**
  [`PipelineEngine`](#article.engine.PipelineEngine)

### *async* article.engine.publish_primary(article, , settings=None, store=None)

Phase 1 facade: publish to the primary platform and record canonical_url.

* **Return type:**
  [`RunSummary`](article.base.md#article.base.RunSummary)

### *async* article.engine.syndicate_secondary(article, , settings=None, store=None, platforms=None)

Phase 2 facade: syndicate to secondaries with the canonical_url injected.

* **Return type:**
  [`RunSummary`](article.base.md#article.base.RunSummary)
