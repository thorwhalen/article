# article

article — semi-automate single-source-of-truth article publishing.

Author an article once as a JSON file, publish it to a **primary** platform
(Substack), then **syndicate** it to secondaries (Medium, Dev.to, Hashnode)
with correct canonical-URL SEO. The Substack public URL captured in phase 1 is
the single source of truth (SSOT) injected as `canonical_url` into every
secondary in phase 2.

Quick start (Python):

```default
import asyncio
from article import load_article, publish_primary, syndicate_secondary

art = load_article("article.json")
asyncio.run(publish_primary(art))        # phase 1 -> records canonical_url
asyncio.run(syndicate_secondary(art))    # phase 2 -> canonical SEO everywhere
```

Or via the CLI:

```default
python -m article publish-primary     article.json
python -m article syndicate-secondary article.json
```

The public surface below is curated; everything else is an implementation
detail. Importing this package registers the built-in platform adapters.

```pycon
>>> from article import load_article, available_adapters
>>> load_article({"title": "T", "slug": "t", "content_markdown": "x"}).slug
't'
>>> available_adapters()
('dev_to', 'hashnode', 'medium', 'substack')
```

### Functions

| [`load_article`](#article.load_article)(source)                              | Load and validate an [`Article`](#article.Article) from a file, a JSON string, or a mapping.   |
|----------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------|
| [`load_settings`](#article.load_settings)(\*[, env_file])                     | Load [`Settings`](#article.Settings) from `.env` / environment, with optional overrides.        |
| [`default_state_store`](#article.default_state_store)(state_path)                   | Construct the default (JSON-file) state store at `state_path`.                                                            |
| [`register_adapter`](#article.register_adapter)(name)                            | Decorator registering an adapter callable under `name`.                                                                   |
| [`get_adapter`](#article.get_adapter)(name)                                 | Resolve the adapter registered under `name`.                                                                              |
| [`available_adapters`](#article.available_adapters)()                              | The platform names with a registered adapter (sorted).                                                                    |
| [`is_registered`](#article.is_registered)(name)                               | Whether an adapter is registered under `name`.                                                                            |
| [`build_engine`](#article.build_engine)(\*[, settings, store])               | Construct a [`PipelineEngine`](#article.PipelineEngine) with sensible defaults.                       |
| [`publish_primary`](#article.publish_primary)(article, \*[, settings, store])   | Phase 1 facade: publish to the primary platform and record canonical_url.                                                 |
| [`syndicate_secondary`](#article.syndicate_secondary)(article, \*[, settings, ...]) | Phase 2 facade: syndicate to secondaries with the canonical_url injected.                                                 |

### Classes

| [`Article`](#article.Article)(\*, title[, subtitle, tags, ...])          | A single-source-of-truth article authored once and published everywhere.           |
|-----------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------|
| [`PlatformConfigs`](#article.PlatformConfigs)(\*[, substack, medium, ...])       | Per-platform map.                                                                  |
| [`SubstackConfig`](#article.SubstackConfig)(\*[, publish_as_draft, title, ...]) | Primary platform: creates an **unpublished draft** (it defines the canonical URL). |
| [`MediumConfig`](#article.MediumConfig)(\*[, publish_as_draft, title, ...])   | Medium syndication options.                                                        |
| [`DevToConfig`](#article.DevToConfig)(\*[, publish_as_draft, title, ...])    | Dev.to / Forem syndication options (`canonical_url` carries SEO).                  |
| [`HashnodeConfig`](#article.HashnodeConfig)(\*[, publish_as_draft, title, ...]) | Hashnode syndication options (`originalArticleURL` carries SEO).                   |
| [`Settings`](#article.Settings)([_case_sensitive, ...])                   | Secrets and runtime config, loaded from environment / `.env`.                      |
| [`PublishResult`](#article.PublishResult)(platform, state[, url, ...])         | Immutable outcome of one platform publish attempt.                                 |
| [`PublishState`](#article.PublishState)(\*values)                             | Outcome state of a single platform publish attempt.                                |
| [`RunSummary`](#article.RunSummary)(phase, results[, canonical_url])        | Structured result of one pipeline phase across all targeted platforms.             |
| [`Phase`](#article.Phase)(\*values)                                    | The two pipeline phases, named exactly as their CLI commands.                      |
| [`JsonStateStore`](#article.JsonStateStore)(path)                               | A whole-file JSON `MutableMapping` keyed by article slug.                          |
| [`PublishAdapter`](#article.PublishAdapter)(\*args, \*\*kwargs)                 | The contract every platform adapter satisfies.                                     |
| [`PipelineEngine`](#article.PipelineEngine)(settings, store[, ...])             | Coordinates the publishing phases over an injected store + settings.               |

### Exceptions

| [`ArticleError`](#article.ArticleError)           | Base class for every error this package raises deliberately.                |
|-------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| [`ArticleValidationError`](#article.ArticleValidationError) | An article JSON file failed schema validation (with a friendly message).    |
| [`ConfigError`](#article.ConfigError)            | Required configuration or secret is missing/invalid.                        |
| [`AdapterError`](#article.AdapterError)           | A platform adapter could not complete its publish attempt.                  |
| [`UnknownPlatformError`](#article.UnknownPlatformError)   | No adapter is registered under the requested platform name.                 |
| [`CanonicalUrlMissing`](#article.CanonicalUrlMissing)    | Phase 2 was requested before phase 1 recorded a canonical_url.              |
| [`CanonicalUrlNotLive`](#article.CanonicalUrlNotLive)    | Phase 2 was requested while the primary post is still an unpublished draft. |

### *exception* article.AdapterError

Bases: [`ArticleError`](article.base.html.md#article.base.ArticleError)

A platform adapter could not complete its publish attempt.

### *class* article.Article(\*, title, subtitle=None, slug, content_markdown, tags=<factory>, keywords=<factory>, cover_image_url=None, description=None, assets_dir=None, platforms=<factory>)

Bases: `BaseModel`

A single-source-of-truth article authored once and published everywhere.

```pycon
>>> art = Article(
...     title="Hello World",
...     slug="hello-world",
...     content_markdown="# Hi\n\nBody text.",
...     tags=["python", "automation"],
...     platforms=PlatformConfigs(medium=MediumConfig(), dev_to=DevToConfig()),
... )
>>> art.slug
'hello-world'
>>> sorted(art.platforms.configured())
['dev_to', 'medium']
```

#### assets_dir *: [Optional](https://docs.python.org/3/library/typing.html#typing.Optional)[[str](https://docs.python.org/3/builtins/stdtypes.html#str)]*

Directory that relative image paths in `content_markdown` resolve
against. [`load_article()`](#article.load_article) sets it to the source file’s directory.

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'extra': 'forbid', 'str_strip_whitespace': True}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### *exception* article.ArticleError

Bases: [`Exception`](https://docs.python.org/3/builtins/exceptions.html#Exception)

Base class for every error this package raises deliberately.

### *exception* article.ArticleValidationError

Bases: [`ArticleError`](article.base.html.md#article.base.ArticleError)

An article JSON file failed schema validation (with a friendly message).

### *exception* article.CanonicalUrlMissing

Bases: [`ArticleError`](article.base.html.md#article.base.ArticleError)

Phase 2 was requested before phase 1 recorded a canonical_url.

### *exception* article.CanonicalUrlNotLive

Bases: [`ArticleError`](article.base.html.md#article.base.ArticleError)

Phase 2 was requested while the primary post is still an unpublished draft.

The recorded canonical URL is the post’s *future* address, so syndicating now
would point other platforms at a 404.

### *exception* article.ConfigError

Bases: [`ArticleError`](article.base.html.md#article.base.ArticleError)

Required configuration or secret is missing/invalid.

### *class* article.DevToConfig(, publish_as_draft=True, title=None, tags=None, organization_id=None, series=None)

Bases: `_PlatformConfig`

Dev.to / Forem syndication options (`canonical_url` carries SEO).

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'extra': 'forbid'}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### *class* article.HashnodeConfig(, publish_as_draft=True, title=None, tags=None, publication_id=None, series_id=None, subtitle=None)

Bases: `_PlatformConfig`

Hashnode syndication options (`originalArticleURL` carries SEO).

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'extra': 'forbid'}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

#### publication_id *: [Optional](https://docs.python.org/3/library/typing.html#typing.Optional)[[str](https://docs.python.org/3/builtins/stdtypes.html#str)]*

ObjectId of the target publication; else taken from settings.

### *class* article.JsonStateStore(path)

Bases: [`MutableMapping`](https://docs.python.org/3/library/collections.abc.html#collections.abc.MutableMapping)

A whole-file JSON `MutableMapping` keyed by article slug.

Reads parse the file fresh and writes replace it atomically, so the file on
disk is always the source of truth (no in-memory drift) and never left
half-written.

```pycon
>>> import tempfile, os
>>> path = os.path.join(tempfile.mkdtemp(), "pipeline_state.json")
>>> store = JsonStateStore(path)
>>> store["hello-world"] = {"canonical_url": "https://me.substack.com/p/hello-world"}
>>> # A fresh instance over the same file sees the persisted record:
>>> JsonStateStore(path)["hello-world"]["canonical_url"]
'https://me.substack.com/p/hello-world'
>>> list(store)
['hello-world']
>>> len(store)
1
>>> del store["hello-world"]
>>> list(store)
[]
```

#### get_canonical_url(slug)

The recorded canonical URL for `slug`, or `None` if not yet set.

* **Return type:**
  [`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]

#### set_canonical_url(slug, canonical_url)

Record `canonical_url` for `slug` (the phase-1 → phase-2 SSOT handoff).

* **Return type:**
  [`None`](https://docs.python.org/3/builtins/constants.html#None)

#### update_record(slug, \*\*fields)

Merge `fields` into the record for `slug` (read-modify-write).

Creates the record if absent and stamps `updated_at`. Returns the
merged record.

```pycon
>>> import tempfile, os
>>> store = JsonStateStore(os.path.join(tempfile.mkdtemp(), "s.json"))
>>> _ = store.update_record("x", title="T")
>>> rec = store.update_record("x", canonical_url="c")
>>> rec["title"], rec["canonical_url"]
('T', 'c')
```

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]

### *class* article.MediumConfig(, publish_as_draft=True, title=None, tags=None, publication_id=None, notify_followers=False, license='all-rights-reserved')

Bases: `_PlatformConfig`

Medium syndication options.

Medium’s API is closed to new integrations, so the adapter does not post:
it returns the *Import a story* steps (which set the canonical link). The
fields below are kept so existing article files still validate.

#### license *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)*

One of Medium’s license enum values.

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'extra': 'forbid'}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

#### publication_id *: [Optional](https://docs.python.org/3/library/typing.html#typing.Optional)[[str](https://docs.python.org/3/builtins/stdtypes.html#str)]*

Publish under a Medium publication instead of the user profile.

### *class* article.Phase(\*values)

Bases: [`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Enum`](https://docs.python.org/3/library/enum.html#enum.Enum)

The two pipeline phases, named exactly as their CLI commands.

### *class* article.PipelineEngine(settings, store, resolve_adapter=<function get_adapter>, is_live=<function url_is_live>)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Coordinates the publishing phases over an injected store + settings.

* **Parameters:**
  * **settings** ([`Settings`](article.config.html.md#article.config.Settings)) – secrets/runtime config facade.
  * **store** ([`MutableMapping`](https://docs.python.org/3/library/collections.abc.html#collections.abc.MutableMapping)) – the state store (any `MutableMapping` keyed by slug).
  * **resolve_adapter** ([`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)[[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)], [`PublishAdapter`](article.registry.html.md#article.registry.PublishAdapter)]) – registry lookup (injected for testing / overrides).

#### is_live(, timeout=10.0)

`url -> bool`: is the canonical URL live? Asked in phase 2 only while the
primary post is still a draft. Defaults to one HTTP GET (`url_is_live()`).

* **Return type:**
  [`bool`](https://docs.python.org/3/builtins/functions.html#bool)

#### *async* publish_primary(article)

Publish to the primary platform and record its URL as `canonical_url`.

* **Return type:**
  [`RunSummary`](article.base.html.md#article.base.RunSummary)

#### resolve_adapter()

Resolve the adapter registered under `name`.

```pycon
>>> get_adapter("nope")
Traceback (most recent call last):
...
article.base.UnknownPlatformError: ...no adapter registered for 'nope'...
```

* **Return type:**
  [`PublishAdapter`](article.registry.html.md#article.registry.PublishAdapter)

#### *async* syndicate_secondary(article, , platforms=None, allow_unpublished=False)

Syndicate to each configured secondary, injecting the canonical URL.

Raises [`CanonicalUrlMissing`](article.base.html.md#article.base.CanonicalUrlMissing) if phase 1 hasn’t
recorded a canonical URL for this slug yet, and
[`CanonicalUrlNotLive`](article.base.html.md#article.base.CanonicalUrlNotLive) if the primary post is still a
draft whose URL does not resolve (`allow_unpublished=True` skips the check).

* **Return type:**
  [`RunSummary`](article.base.html.md#article.base.RunSummary)

### *class* article.PlatformConfigs(, substack=None, medium=None, dev_to=None, hashnode=None)

Bases: `BaseModel`

Per-platform map. A `None` (absent) entry means *skip that platform*.

#### configured()

The subset of platforms that are present (non-`None`), keyed by name.

```pycon
>>> PlatformConfigs(medium=MediumConfig()).configured().keys()
dict_keys(['medium'])
```

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)[[`Literal`](https://docs.python.org/3/library/typing.html#typing.Literal)[`'substack'`, `'medium'`, `'dev_to'`, `'hashnode'`], `_PlatformConfig`]

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'extra': 'forbid'}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### *class* article.PublishAdapter(\*args, \*\*kwargs)

Bases: [`Protocol`](https://docs.python.org/3/library/typing.html#typing.Protocol)

The contract every platform adapter satisfies.

An adapter is an `async` callable. The engine injects:

- `article`: the validated [`Article`](article.config.html.md#article.config.Article).
- `canonical_url`: the SSOT URL (`None` only for the primary, which
  *defines* it; secondaries must receive and honour it).
- `config`: the platform’s config model (overrides + options).
- `secrets`: the minimal credentials/identity for this platform.

and receives a [`PublishResult`](article.base.html.md#article.base.PublishResult) back.

### *class* article.PublishResult(platform, state, url=None, status=None, canonical_url=None, error=None, detail=dict())

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Immutable outcome of one platform publish attempt.

Construct via the classmethods rather than the raw initializer so intent is
explicit at the call site:

```pycon
>>> PublishResult.success("medium", url="https://medium.com/p/x", status="draft").ok
True
>>> r = PublishResult.failure("hashnode", error="HTTP 401")
>>> r.ok, r.state.value, r.error
(False, 'failed', 'HTTP 401')
>>> PublishResult.skipped("dev_to", reason="not configured").state.value
'skipped'
>>> PublishResult.manual("medium", next_step="import it").ok
False
```

#### as_record()

A JSON-serializable summary, suitable for the state store.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]

#### *classmethod* failure(platform, , error, detail=None)

A failed attempt on `platform` — the run continues past it.

* **Return type:**
  [`PublishResult`](article.base.html.md#article.base.PublishResult)

#### *classmethod* manual(platform, , next_step, canonical_url=None, detail=None)

Nothing was sent to `platform`; `next_step` says what a person must do.

* **Return type:**
  [`PublishResult`](article.base.html.md#article.base.PublishResult)

#### *property* ok *: [bool](https://docs.python.org/3/builtins/functions.html#bool)*

True iff the attempt succeeded.

#### *classmethod* skipped(platform, , reason, detail=None)

`platform` was not attempted (e.g. absent from the article config).

* **Return type:**
  [`PublishResult`](article.base.html.md#article.base.PublishResult)

#### *classmethod* success(platform, , url=None, status=None, canonical_url=None, detail=None)

A successful publish/draft to `platform`.

* **Return type:**
  [`PublishResult`](article.base.html.md#article.base.PublishResult)

### *class* article.PublishState(\*values)

Bases: [`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Enum`](https://docs.python.org/3/library/enum.html#enum.Enum)

Outcome state of a single platform publish attempt.

#### MANUAL *= 'manual'*

the platform has no usable API, so the result carries
the steps for a person to do by hand (`detail["next_step"]`).

* **Type:**
  Nothing was sent

### *class* article.RunSummary(phase, results, canonical_url=None)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Structured result of one pipeline phase across all targeted platforms.

```pycon
>>> results = (
...     PublishResult.success("medium", url="m"),
...     PublishResult.failure("dev_to", error="boom"),
... )
>>> summary = RunSummary(phase="syndicate-secondary", results=results, canonical_url="c")
>>> summary.ok
False
>>> [r.platform for r in summary.failures]
['dev_to']
>>> summary.by_platform["medium"].url
'm'
```

#### as_record()

A JSON-serializable summary, suitable for the state store.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]

#### *property* by_platform *: [dict](https://docs.python.org/3/builtins/stdtypes.html#dict)[[str](https://docs.python.org/3/builtins/stdtypes.html#str), [PublishResult](article.base.html.md#article.base.PublishResult)]*

Results keyed by platform name.

#### *property* failures *: [tuple](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[PublishResult](article.base.html.md#article.base.PublishResult), ...]*

The subset of results that failed.

#### *property* manual_steps *: [tuple](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[PublishResult](article.base.html.md#article.base.PublishResult), ...]*

The subset of results that need a person to finish them by hand.

#### *property* ok *: [bool](https://docs.python.org/3/builtins/functions.html#bool)*

True iff no targeted platform failed (skipped platforms don’t count).

#### render()

A compact human-readable, multi-line summary.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

#### *property* successes *: [tuple](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[PublishResult](article.base.html.md#article.base.PublishResult), ...]*

The subset of results that succeeded.

### *class* article.Settings(\_case_sensitive=None, \_nested_model_default_partial_update=None, \_env_prefix=None, \_env_prefix_target=None, \_env_file=PosixPath('.'), \_env_file_encoding=None, \_env_file_depth=None, \_env_ignore_empty=None, \_env_nested_delimiter=None, \_env_nested_max_split=None, \_env_parse_none_str=None, \_env_parse_enums=None, \_cli_prog_name=None, \_cli_parse_args=None, \_cli_settings_source=None, \_cli_parse_none_str=None, \_cli_hide_none_type=None, \_cli_avoid_json=None, \_cli_enforce_required=None, \_cli_use_class_docs_for_groups=None, \_cli_show_env_vars=None, \_cli_exit_on_error=None, \_cli_prefix=None, \_cli_flag_prefix_char=None, \_cli_implicit_flags=None, \_cli_ignore_unknown_args=None, \_cli_kebab_case=None, \_cli_shortcuts=None, \_secrets_dir=None, \_build_sources=None, , substack_cookies=None, substack_cookies_path=None, substack_email=None, substack_password=None, substack_publication_url=None, medium_token=None, medium_user_id=None, devto_api_key=None, hashnode_token=None, hashnode_publication_id=None, state_path='pipeline_state.json')

Bases: `BaseSettings`

Secrets and runtime config, loaded from environment / `.env`.

Env var names are the field names upper-cased (e.g. `MEDIUM_TOKEN`,
`DEVTO_API_KEY`, `SUBSTACK_EMAIL`). Use [`load_settings()`](#article.load_settings) rather
than constructing this directly.

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[SettingsConfigDict]* *= {'arbitrary_types_allowed': True, 'case_sensitive': False, 'cli_avoid_json': False, 'cli_enforce_required': False, 'cli_exit_on_error': True, 'cli_flag_prefix_char': '-', 'cli_hide_none_type': False, 'cli_ignore_unknown_args': False, 'cli_implicit_flags': False, 'cli_kebab_case': False, 'cli_parse_args': None, 'cli_parse_none_str': None, 'cli_prefix': '', 'cli_prog_name': None, 'cli_shortcuts': None, 'cli_show_env_vars': False, 'cli_use_class_docs_for_groups': False, 'enable_decoding': True, 'env_file': '.env', 'env_file_depth': 0, 'env_file_encoding': 'utf-8', 'env_ignore_empty': False, 'env_nested_delimiter': None, 'env_nested_max_split': None, 'env_parse_enums': None, 'env_parse_none_str': None, 'env_prefix': '', 'env_prefix_target': 'variable', 'extra': 'ignore', 'json_file': None, 'json_file_encoding': None, 'nested_model_default_partial_update': False, 'protected_namespaces': ('model_validate', 'model_dump', 'settings_cached', 'settings_clear_cache', 'settings_customise_sources'), 'secrets_case_sensitive': None, 'secrets_dir': None, 'secrets_dir_max_size': None, 'secrets_dir_missing': None, 'secrets_nested_delimiter': None, 'secrets_nested_subdir': None, 'secrets_prefix': None, 'toml_file': None, 'validate_default': True, 'yaml_config_section': None, 'yaml_file': None, 'yaml_file_encoding': None}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

#### secrets_for(platform)

The minimal secrets/identity an adapter needs — injected, not global.

Returning only the relevant subset keeps adapters from reaching into a
global `Settings` (dependency injection + least privilege).

```pycon
>>> s = Settings(medium_token="t", medium_user_id="u", _env_file=None)
>>> s.secrets_for("medium") == {"token": "t", "user_id": "u"}
True
```

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]

#### state_path *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)*

JSON state store path (the canonical_url SSOT lives here, keyed by slug).

### *class* article.SubstackConfig(, publish_as_draft=True, title=None, tags=None, publication_url=None, section_id=None, send_email=False, audience='everyone', tables='error', draft_id=None, expected_revision=None, overwrite_edits=False)

Bases: `_PlatformConfig`

Primary platform: creates an **unpublished draft** (it defines the canonical URL).

This tool never publishes to Substack: `publish_as_draft=False` is refused
by the adapter. Review the draft and press *Publish* in the Substack editor.

#### audience *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)*

everyone / only_paid / founding / only_free.

* **Type:**
  Audience visibility

#### draft_id *: [Optional](https://docs.python.org/3/library/typing.html#typing.Optional)[[int](https://docs.python.org/3/builtins/functions.html#int)]*

Update this existing draft in place instead of creating a new one (the CLI’s
`--update` fills it, and `expected_revision`, from the state store).

#### expected_revision *: [Optional](https://docs.python.org/3/library/typing.html#typing.Optional)[[dict](https://docs.python.org/3/builtins/stdtypes.html#dict)]*

The draft’s revision as last recorded; a draft edited since is refused.

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'extra': 'forbid'}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

#### overwrite_edits *: [bool](https://docs.python.org/3/builtins/functions.html#bool)*

Overwrite edits made in the Substack editor since `expected_revision`.

#### publication_url *: [Optional](https://docs.python.org/3/library/typing.html#typing.Optional)[[str](https://docs.python.org/3/builtins/stdtypes.html#str)]*

`https://<sub>.substack.com` (or custom domain); else taken from settings.

#### publish_as_draft *: [bool](https://docs.python.org/3/builtins/functions.html#bool)*

Default to a draft for visual QA before going public. Overridden per platform.

#### section_id *: [Optional](https://docs.python.org/3/library/typing.html#typing.Optional)[[int](https://docs.python.org/3/builtins/functions.html#int)]*

Optional Substack section id to file the post under.

#### send_email *: [bool](https://docs.python.org/3/builtins/functions.html#bool)*

Kept for article-file compatibility; unused, since this tool never publishes.

#### tables *: [Literal](https://docs.python.org/3/library/typing.html#typing.Literal)['error', 'code', 'image']*

What to do with a Markdown table, which Substack cannot represent:
`"error"` (refuse, naming every table) or `"code"` (keep it as a
monospace code block). Never dropped silently.

### *exception* article.UnknownPlatformError

Bases: [`ArticleError`](article.base.html.md#article.base.ArticleError), [`KeyError`](https://docs.python.org/3/builtins/exceptions.html#KeyError)

No adapter is registered under the requested platform name.

### article.available_adapters()

The platform names with a registered adapter (sorted).

* **Return type:**
  [`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`...`](https://docs.python.org/3/builtins/constants.html#Ellipsis)]

### article.build_engine(, settings=None, store=None)

Construct a [`PipelineEngine`](#article.PipelineEngine) with sensible defaults.

Defaults: settings from `.env`/environment, and a JSON state store at
`settings.state_path`. Pass either explicitly to override (tests, alt backends).

* **Return type:**
  [`PipelineEngine`](article.engine.html.md#article.engine.PipelineEngine)

### article.default_state_store(state_path)

Construct the default (JSON-file) state store at `state_path`.

A single seam to swap the backend implementation package-wide.

* **Return type:**
  [`JsonStateStore`](article.state.html.md#article.state.JsonStateStore)

### article.get_adapter(name)

Resolve the adapter registered under `name`.

```pycon
>>> get_adapter("nope")
Traceback (most recent call last):
...
article.base.UnknownPlatformError: ...no adapter registered for 'nope'...
```

* **Return type:**
  [`PublishAdapter`](article.registry.html.md#article.registry.PublishAdapter)

### article.is_registered(name)

Whether an adapter is registered under `name`.

* **Return type:**
  [`bool`](https://docs.python.org/3/builtins/functions.html#bool)

### article.load_article(source)

Load and validate an [`Article`](#article.Article) from a file, a JSON string, or a mapping.

A file is either an article JSON file or a plain Markdown file (`.md` /
`.markdown`; see [`article.md_source`](article.md_source.html.md#module-article.md_source) for how its title, slug and
front matter are read). Relative image paths in either resolve against the
file’s directory (`assets_dir`) unless the article sets its own.

Validation failures are re-raised as [`ArticleValidationError`](article.base.html.md#article.base.ArticleValidationError)
with a single message naming each offending field — not a raw traceback.

```pycon
>>> load_article({
...     "title": "Hello",
...     "slug": "hello-world",
...     "content_markdown": "x",
...     "platforms": {"dev_to": {}},
... }).slug
'hello-world'
```

```pycon
>>> load_article({"title": "x"})
Traceback (most recent call last):
...
article.base.ArticleValidationError: Invalid article ...slug... content_markdown...
```

```pycon
>>> load_article({"title": "x", "slug": "Bad Slug", "content_markdown": "y"})
Traceback (most recent call last):
...
article.base.ArticleValidationError: Invalid article ...slug: String should match pattern...
```

* **Return type:**
  [`Article`](article.config.html.md#article.config.Article)

### article.load_settings(, env_file=None, \*\*overrides)

Load [`Settings`](#article.Settings) from `.env` / environment, with optional overrides.

The single configuration facade. `env_file=None` uses the default lookup
(`.env` in the working directory); pass an explicit path to point
elsewhere; pass keyword `overrides` to set fields directly (tests, CLI).

* **Return type:**
  [`Settings`](article.config.html.md#article.config.Settings)

### *async* article.publish_primary(article, , settings=None, store=None)

Phase 1 facade: publish to the primary platform and record canonical_url.

* **Return type:**
  [`RunSummary`](article.base.html.md#article.base.RunSummary)

### article.register_adapter(name)

Decorator registering an adapter callable under `name`.

```pycon
>>> @register_adapter("demo")
... async def publish(article, *, canonical_url, config, secrets):
...     ...
```

### *async* article.syndicate_secondary(article, , settings=None, store=None, platforms=None, allow_unpublished=False)

Phase 2 facade: syndicate to secondaries with the canonical_url injected.

* **Return type:**
  [`RunSummary`](article.base.html.md#article.base.RunSummary)

### Modules

| [`adapters`](article.adapters.html.md#module-article.adapters)   | Built-in platform adapters.                                           |
|-------------------------------------------------------------------------------------|-----------------------------------------------------------------------|
| [`base`](article.base.html.md#module-article.base)           | Core vocabulary for the `article` publishing pipeline.                |
| [`config`](article.config.html.md#module-article.config)       | Domain schema + configuration facade.                                 |
| [`engine`](article.engine.html.md#module-article.engine)       | Orchestration engine — the two-phase, canonical-URL SSOT pipeline.    |
| [`md_source`](article.md_source.html.md#module-article.md_source) | Read an article from a plain Markdown file (no JSON envelope needed). |
| [`registry`](article.registry.html.md#module-article.registry)   | Adapter `Protocol` + an open-closed registry keyed by platform name.  |
| [`state`](article.state.html.md#module-article.state)         | Pipeline state store — a `MutableMapping` facade over a JSON backend. |
| [`util`](article.util.html.md#module-article.util)           | Thin, dependency-light utilities shared across the package.           |
