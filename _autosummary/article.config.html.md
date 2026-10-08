# article.config

Domain schema + configuration facade.

Two concerns live here, both expressed as Pydantic v2 models so validation is
declarative and the SSOT for *shape*:

1. **The article domain model** ([`Article`](#article.config.Article) + the per-platform config
   models) — parsed from a standardized JSON file via [`load_article()`](#article.config.load_article),
   which turns raw Pydantic tracebacks into a single actionable message
   (which field, why).
2. **Runtime settings/secrets** ([`Settings`](#article.config.Settings)) — API tokens and Substack
   credentials loaded from `.env` / the environment via
   [`load_settings()`](#article.config.load_settings), the single facade the rest of the package calls.

   Secrets are marked `repr=False` so they never leak into logs or tracebacks.

Per-platform presence is the on/off switch: a platform absent from
`article.platforms` is simply skipped.

### Functions

| [`load_article`](#article.config.load_article)(source)          | Load and validate an [`Article`](#article.config.Article) from a file, a JSON string, or a mapping.   |
|--------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------|
| [`load_settings`](#article.config.load_settings)(\*[, env_file]) | Load [`Settings`](#article.config.Settings) from `.env` / environment, with optional overrides.        |

### Classes

| [`Article`](#article.config.Article)(\*\*data)                | A single-source-of-truth article authored once and published everywhere.           |
|-----------------------------------------------------------------------------------|------------------------------------------------------------------------------------|
| [`DevToConfig`](#article.config.DevToConfig)(\*\*data)            | Dev.to / Forem syndication options (`canonical_url` carries SEO).                  |
| [`HashnodeConfig`](#article.config.HashnodeConfig)(\*\*data)         | Hashnode syndication options (`originalArticleURL` carries SEO).                   |
| [`MediumConfig`](#article.config.MediumConfig)(\*\*data)           | Medium syndication options.                                                        |
| [`PlatformConfigs`](#article.config.PlatformConfigs)(\*\*data)        | Per-platform map.                                                                  |
| [`Settings`](#article.config.Settings)([_case_sensitive, ...]) | Secrets and runtime config, loaded from environment / `.env`.                      |
| [`SubstackConfig`](#article.config.SubstackConfig)(\*\*data)         | Primary platform: creates an **unpublished draft** (it defines the canonical URL). |

### *class* article.config.Article(\*\*data)

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

#### assets_dir *: [str](https://docs.python.org/3/builtins/stdtypes.html#str) | [None](https://docs.python.org/3/builtins/constants.html#None)*

Directory that relative image paths in `content_markdown` resolve
against. [`load_article()`](#article.config.load_article) sets it to the source file’s directory.

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'extra': 'forbid', 'str_strip_whitespace': True}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### *class* article.config.DevToConfig(\*\*data)

Bases: `_PlatformConfig`

Dev.to / Forem syndication options (`canonical_url` carries SEO).

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'extra': 'forbid'}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### *class* article.config.HashnodeConfig(\*\*data)

Bases: `_PlatformConfig`

Hashnode syndication options (`originalArticleURL` carries SEO).

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'extra': 'forbid'}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

#### publication_id *: [str](https://docs.python.org/3/builtins/stdtypes.html#str) | [None](https://docs.python.org/3/builtins/constants.html#None)*

ObjectId of the target publication; else taken from settings.

### *class* article.config.MediumConfig(\*\*data)

Bases: `_PlatformConfig`

Medium syndication options.

Medium’s API is closed to new integrations, so the adapter does not post:
it returns the *Import a story* steps (which set the canonical link). The
fields below are kept so existing article files still validate.

#### license *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)*

One of Medium’s license enum values.

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'extra': 'forbid'}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

#### publication_id *: [str](https://docs.python.org/3/builtins/stdtypes.html#str) | [None](https://docs.python.org/3/builtins/constants.html#None)*

Publish under a Medium publication instead of the user profile.

### *class* article.config.PlatformConfigs(\*\*data)

Bases: `BaseModel`

Per-platform map. A `None` (absent) entry means *skip that platform*.

#### configured()

The subset of platforms that are present (non-`None`), keyed by name.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)[[`Literal`](https://docs.python.org/3/library/typing.html#typing.Literal)[`'substack'`, `'medium'`, `'dev_to'`, `'hashnode'`], `_PlatformConfig`]

```pycon
>>> PlatformConfigs(medium=MediumConfig()).configured().keys()
dict_keys(['medium'])
```

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'extra': 'forbid'}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### *class* article.config.Settings(\_case_sensitive=None, \_nested_model_default_partial_update=None, \_env_prefix=None, \_env_prefix_target=None, \_env_file=PosixPath('.'), \_env_file_encoding=None, \_env_ignore_empty=None, \_env_nested_delimiter=None, \_env_nested_max_split=None, \_env_parse_none_str=None, \_env_parse_enums=None, \_cli_prog_name=None, \_cli_parse_args=None, \_cli_settings_source=None, \_cli_parse_none_str=None, \_cli_hide_none_type=None, \_cli_avoid_json=None, \_cli_enforce_required=None, \_cli_use_class_docs_for_groups=None, \_cli_show_env_vars=None, \_cli_exit_on_error=None, \_cli_prefix=None, \_cli_flag_prefix_char=None, \_cli_implicit_flags=None, \_cli_ignore_unknown_args=None, \_cli_kebab_case=None, \_cli_shortcuts=None, \_secrets_dir=None, \_build_sources=None, \*\*values)

Bases: `BaseSettings`

Secrets and runtime config, loaded from environment / `.env`.

Env var names are the field names upper-cased (e.g. `MEDIUM_TOKEN`,
`DEVTO_API_KEY`, `SUBSTACK_EMAIL`). Use [`load_settings()`](#article.config.load_settings) rather
than constructing this directly.

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[SettingsConfigDict]* *= {'arbitrary_types_allowed': True, 'case_sensitive': False, 'cli_avoid_json': False, 'cli_enforce_required': False, 'cli_exit_on_error': True, 'cli_flag_prefix_char': '-', 'cli_hide_none_type': False, 'cli_ignore_unknown_args': False, 'cli_implicit_flags': False, 'cli_kebab_case': False, 'cli_parse_args': None, 'cli_parse_none_str': None, 'cli_prefix': '', 'cli_prog_name': None, 'cli_shortcuts': None, 'cli_show_env_vars': False, 'cli_use_class_docs_for_groups': False, 'enable_decoding': True, 'env_file': '.env', 'env_file_encoding': 'utf-8', 'env_ignore_empty': False, 'env_nested_delimiter': None, 'env_nested_max_split': None, 'env_parse_enums': None, 'env_parse_none_str': None, 'env_prefix': '', 'env_prefix_target': 'variable', 'extra': 'ignore', 'json_file': None, 'json_file_encoding': None, 'nested_model_default_partial_update': False, 'protected_namespaces': ('model_validate', 'model_dump', 'settings_customise_sources'), 'secrets_dir': None, 'toml_file': None, 'validate_default': True, 'yaml_config_section': None, 'yaml_file': None, 'yaml_file_encoding': None}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

#### secrets_for(platform)

The minimal secrets/identity an adapter needs — injected, not global.

Returning only the relevant subset keeps adapters from reaching into a
global `Settings` (dependency injection + least privilege).

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]

```pycon
>>> s = Settings(medium_token="t", medium_user_id="u", _env_file=None)
>>> s.secrets_for("medium") == {"token": "t", "user_id": "u"}
True
```

#### state_path *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)*

JSON state store path (the canonical_url SSOT lives here, keyed by slug).

### *class* article.config.SubstackConfig(\*\*data)

Bases: `_PlatformConfig`

Primary platform: creates an **unpublished draft** (it defines the canonical URL).

This tool never publishes to Substack: `publish_as_draft=False` is refused
by the adapter. Review the draft and press *Publish* in the Substack editor.

#### audience *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)*

everyone / only_paid / founding / only_free.

* **Type:**
  Audience visibility

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'extra': 'forbid'}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

#### publication_url *: [str](https://docs.python.org/3/builtins/stdtypes.html#str) | [None](https://docs.python.org/3/builtins/constants.html#None)*

`https://<sub>.substack.com` (or custom domain); else taken from settings.

#### publish_as_draft *: [bool](https://docs.python.org/3/builtins/functions.html#bool)*

Default to a draft for visual QA before going public. Overridden per platform.

#### section_id *: [int](https://docs.python.org/3/builtins/functions.html#int) | [None](https://docs.python.org/3/builtins/constants.html#None)*

Optional Substack section id to file the post under.

#### send_email *: [bool](https://docs.python.org/3/builtins/functions.html#bool)*

Kept for article-file compatibility; unused, since this tool never publishes.

#### tables *: [Literal](https://docs.python.org/3/library/typing.html#typing.Literal)['error', 'code']*

What to do with a Markdown table, which Substack cannot represent:
`"error"` (refuse, naming every table) or `"code"` (keep it as a
monospace code block). Never dropped silently.

### article.config.load_article(source)

Load and validate an [`Article`](#article.config.Article) from a file, a JSON string, or a mapping.

A file is either an article JSON file or a plain Markdown file (`.md` /
`.markdown`; see [`article.md_source`](article.md_source.html.md#module-article.md_source) for how its title, slug and
front matter are read). Relative image paths in either resolve against the
file’s directory (`assets_dir`) unless the article sets its own.

Validation failures are re-raised as [`ArticleValidationError`](article.base.html.md#article.base.ArticleValidationError)
with a single message naming each offending field — not a raw traceback.

* **Return type:**
  [`Article`](#article.config.Article)

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

### article.config.load_settings(, env_file=None, \*\*overrides)

Load [`Settings`](#article.config.Settings) from `.env` / environment, with optional overrides.

The single configuration facade. `env_file=None` uses the default lookup
(`.env` in the working directory); pass an explicit path to point
elsewhere; pass keyword `overrides` to set fields directly (tests, CLI).

* **Return type:**
  [`Settings`](#article.config.Settings)
