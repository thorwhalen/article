# article.base

Core vocabulary for the `article` publishing pipeline.

This module holds only *foundational* types — the names every other layer
speaks in — and no business logic:

- `PlatformName` and the platform-name constants
  (`SUBSTACK`, `MEDIUM`, `DEV_TO`, `HASHNODE`).
- [`PublishResult`](#article.base.PublishResult) — the immutable, per-platform outcome of one publish
  attempt, with [`PublishResult.success()`](#article.base.PublishResult.success) / [`failure()`](#article.base.PublishResult.failure)
  / [`skipped()`](#article.base.PublishResult.skipped) constructors so call sites read declaratively.
- [`RunSummary`](#article.base.RunSummary) — the structured result of a whole phase (a tuple of
  [`PublishResult`](#article.base.PublishResult) plus the resolved `canonical_url`).
- The package exception hierarchy, all rooted at [`ArticleError`](#article.base.ArticleError).

Keeping these here (rather than scattered) is the SSOT for the package’s shared
types and keeps import edges acyclic: `base` imports nothing from the package.

### Module Attributes

| [`PRIMARY_PLATFORM`](#article.base.PRIMARY_PLATFORM)    | The primary platform whose assigned public URL becomes the canonical SSOT.        |
|----------------------------------------------------------------------|-----------------------------------------------------------------------------------|
| [`SECONDARY_PLATFORMS`](#article.base.SECONDARY_PLATFORMS) | The platforms syndicated to in phase 2, each pointing canonically at the primary. |
| [`ALL_PLATFORMS`](#article.base.ALL_PLATFORMS)       | All known platforms, primary first.                                               |

### Classes

| [`Phase`](#article.base.Phase)(\*values)                             | The two pipeline phases, named exactly as their CLI commands.          |
|----------------------------------------------------------------------------------------------|------------------------------------------------------------------------|
| [`PublishResult`](#article.base.PublishResult)(platform, state[, url, ...])  | Immutable outcome of one platform publish attempt.                     |
| [`PublishState`](#article.base.PublishState)(\*values)                      | Outcome state of a single platform publish attempt.                    |
| [`RunSummary`](#article.base.RunSummary)(phase, results[, canonical_url]) | Structured result of one pipeline phase across all targeted platforms. |

### Exceptions

| [`AdapterError`](#article.base.AdapterError)           | A platform adapter could not complete its publish attempt.               |
|-------------------------------------------------------------------------|--------------------------------------------------------------------------|
| [`ArticleError`](#article.base.ArticleError)           | Base class for every error this package raises deliberately.             |
| [`ArticleValidationError`](#article.base.ArticleValidationError) | An article JSON file failed schema validation (with a friendly message). |
| [`CanonicalUrlMissing`](#article.base.CanonicalUrlMissing)    | Phase 2 was requested before phase 1 recorded a canonical_url.           |
| [`ConfigError`](#article.base.ConfigError)            | Required configuration or secret is missing/invalid.                     |
| [`UnknownPlatformError`](#article.base.UnknownPlatformError)   | No adapter is registered under the requested platform name.              |

### article.base.ALL_PLATFORMS *: [tuple](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[Literal](https://docs.python.org/3/library/typing.html#typing.Literal)['substack', 'medium', 'dev_to', 'hashnode'], ...]* *= ('substack', 'medium', 'dev_to', 'hashnode')*

All known platforms, primary first.

### *exception* article.base.AdapterError

Bases: [`ArticleError`](#article.base.ArticleError)

A platform adapter could not complete its publish attempt.

### *exception* article.base.ArticleError

Bases: [`Exception`](https://docs.python.org/3/builtins/exceptions.html#Exception)

Base class for every error this package raises deliberately.

### *exception* article.base.ArticleValidationError

Bases: [`ArticleError`](#article.base.ArticleError)

An article JSON file failed schema validation (with a friendly message).

### *exception* article.base.CanonicalUrlMissing

Bases: [`ArticleError`](#article.base.ArticleError)

Phase 2 was requested before phase 1 recorded a canonical_url.

### *exception* article.base.ConfigError

Bases: [`ArticleError`](#article.base.ArticleError)

Required configuration or secret is missing/invalid.

### article.base.PRIMARY_PLATFORM *: [Literal](https://docs.python.org/3/library/typing.html#typing.Literal)['substack', 'medium', 'dev_to', 'hashnode']* *= 'substack'*

The primary platform whose assigned public URL becomes the canonical SSOT.

### *class* article.base.Phase(\*values)

Bases: [`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Enum`](https://docs.python.org/3/library/enum.html#enum.Enum)

The two pipeline phases, named exactly as their CLI commands.

### *class* article.base.PublishResult(platform, state, url=None, status=None, canonical_url=None, error=None, detail=<factory>)

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
  [`PublishResult`](#article.base.PublishResult)

#### *classmethod* manual(platform, , next_step, canonical_url=None, detail=None)

Nothing was sent to `platform`; `next_step` says what a person must do.

* **Return type:**
  [`PublishResult`](#article.base.PublishResult)

#### *property* ok *: [bool](https://docs.python.org/3/builtins/functions.html#bool)*

True iff the attempt succeeded.

#### *classmethod* skipped(platform, , reason, detail=None)

`platform` was not attempted (e.g. absent from the article config).

* **Return type:**
  [`PublishResult`](#article.base.PublishResult)

#### *classmethod* success(platform, , url=None, status=None, canonical_url=None, detail=None)

A successful publish/draft to `platform`.

* **Return type:**
  [`PublishResult`](#article.base.PublishResult)

### *class* article.base.PublishState(\*values)

Bases: [`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Enum`](https://docs.python.org/3/library/enum.html#enum.Enum)

Outcome state of a single platform publish attempt.

#### MANUAL *= 'manual'*

the platform has no usable API, so the result carries
the steps for a person to do by hand (`detail["next_step"]`).

* **Type:**
  Nothing was sent

### *class* article.base.RunSummary(phase, results, canonical_url=None)

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

#### *property* by_platform *: [dict](https://docs.python.org/3/builtins/stdtypes.html#dict)[[str](https://docs.python.org/3/builtins/stdtypes.html#str), [PublishResult](#article.base.PublishResult)]*

Results keyed by platform name.

#### *property* failures *: [tuple](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[PublishResult](#article.base.PublishResult), ...]*

The subset of results that failed.

#### *property* manual_steps *: [tuple](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[PublishResult](#article.base.PublishResult), ...]*

The subset of results that need a person to finish them by hand.

#### *property* ok *: [bool](https://docs.python.org/3/builtins/functions.html#bool)*

True iff no targeted platform failed (skipped platforms don’t count).

#### render()

A compact human-readable, multi-line summary.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

#### *property* successes *: [tuple](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[PublishResult](#article.base.PublishResult), ...]*

The subset of results that succeeded.

### article.base.SECONDARY_PLATFORMS *: [tuple](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[Literal](https://docs.python.org/3/library/typing.html#typing.Literal)['substack', 'medium', 'dev_to', 'hashnode'], ...]* *= ('medium', 'dev_to', 'hashnode')*

The platforms syndicated to in phase 2, each pointing canonically at the primary.

### *exception* article.base.UnknownPlatformError

Bases: [`ArticleError`](#article.base.ArticleError), [`KeyError`](https://docs.python.org/3/builtins/exceptions.html#KeyError)

No adapter is registered under the requested platform name.
