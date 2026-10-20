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

| [`Article`](#article.config.Article)(\*, title[, subtitle, tags, ...])          | A single-source-of-truth article authored once and published everywhere.           |
|-----------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------|
| [`DevToConfig`](#article.config.DevToConfig)(\*[, publish_as_draft, title, ...])    | Dev.to / Forem syndication options (`canonical_url` carries SEO).                  |
| [`HashnodeConfig`](#article.config.HashnodeConfig)(\*[, publish_as_draft, title, ...]) | Hashnode syndication options (`originalArticleURL` carries SEO).                   |
| [`MediumConfig`](#article.config.MediumConfig)(\*[, publish_as_draft, title, ...])   | Medium syndication options.                                                        |
| [`PlatformConfigs`](#article.config.PlatformConfigs)(\*[, substack, medium, ...])       | Per-platform map.                                                                  |
| [`Settings`](#article.config.Settings)([_case_sensitive, ...])                   | Secrets and runtime config, loaded from environment / `.env`.                      |
| [`SubstackConfig`](#article.config.SubstackConfig)(\*[, publish_as_draft, title, ...]) | Primary platform: creates an **unpublished draft** (it defines the canonical URL). |

### *class* article.config.Article(\*, title, subtitle=None, slug, content_markdown, tags=<factory>, keywords=<factory>, cover_image_url=None, description=None, assets_dir=None, platforms=<factory>)

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
against. [`load_article()`](#article.config.load_article) sets it to the source file’s directory.

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'extra': 'forbid', 'str_strip_whitespace': True}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### *class* article.config.DevToConfig(, publish_as_draft=True, title=None, tags=None, organization_id=None, series=None)

Bases: `_PlatformConfig`

Dev.to / Forem syndication options (`canonical_url` carries SEO).

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'extra': 'forbid'}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### *class* article.config.HashnodeConfig(, publish_as_draft=True, title=None, tags=None, publication_id=None, series_id=None, subtitle=None)

Bases: `_PlatformConfig`

Hashnode syndication options (`originalArticleURL` carries SEO).

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'extra': 'forbid'}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

#### publication_id *: [Optional](https://docs.python.org/3/library/typing.html#typing.Optional)[[str](https://docs.python.org/3/builtins/stdtypes.html#str)]*

ObjectId of the target publication; else taken from settings.

### *class* article.config.MediumConfig(, publish_as_draft=True, title=None, tags=None, publication_id=None, notify_followers=False, license='all-rights-reserved')

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

### *class* article.config.PlatformConfigs(, substack=None, medium=None, dev_to=None, hashnode=None)

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

### *class* article.config.Settings(\_case_sensitive=None, \_nested_model_default_partial_update=None, \_env_prefix=None, \_env_prefix_target=None, \_env_file=PosixPath('.'), \_env_file_encoding=None, \_env_file_depth=None, \_env_ignore_empty=None, \_env_nested_delimiter=None, \_env_nested_max_split=None, \_env_parse_none_str=None, \_env_parse_enums=None, \_cli_prog_name=None, \_cli_parse_args=None, \_cli_settings_source=None, \_cli_parse_none_str=None, \_cli_hide_none_type=None, \_cli_avoid_json=None, \_cli_enforce_required=None, \_cli_use_class_docs_for_groups=None, \_cli_show_env_vars=None, \_cli_exit_on_error=None, \_cli_prefix=None, \_cli_flag_prefix_char=None, \_cli_implicit_flags=None, \_cli_ignore_unknown_args=None, \_cli_kebab_case=None, \_cli_shortcuts=None, \_secrets_dir=None, \_build_sources=None, , substack_cookies=None, substack_cookies_path=None, substack_email=None, substack_password=None, substack_publication_url=None, medium_token=None, medium_user_id=None, devto_api_key=None, hashnode_token=None, hashnode_publication_id=None, state_path='pipeline_state.json')

Bases: `BaseSettings`

Secrets and runtime config, loaded from environment / `.env`.

Env var names are the field names upper-cased (e.g. `MEDIUM_TOKEN`,
`DEVTO_API_KEY`, `SUBSTACK_EMAIL`). Use [`load_settings()`](#article.config.load_settings) rather
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

### *class* article.config.SubstackConfig(, publish_as_draft=True, title=None, tags=None, publication_url=None, section_id=None, send_email=False, audience='everyone', tables='error', draft_id=None, expected_revision=None, overwrite_edits=False)

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

### article.config.load_article(source)

Load and validate an [`Article`](#article.config.Article) from a file, a JSON string, or a mapping.

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
  [`Article`](#article.config.Article)

### article.config.load_settings(, env_file=None, \*\*overrides)

Load [`Settings`](#article.config.Settings) from `.env` / environment, with optional overrides.

The single configuration facade. `env_file=None` uses the default lookup
(`.env` in the working directory); pass an explicit path to point
elsewhere; pass keyword `overrides` to set fields directly (tests, CLI).

* **Return type:**
  [`Settings`](#article.config.Settings)
