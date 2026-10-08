# article.util

Thin, dependency-light utilities shared across the package.

Nothing here knows about platforms or pipelines — these are general helpers:
logging, human-like async pacing (so automating your *own* account doesn’t trip
automated-traffic heuristics), atomic JSON IO for the state store, and the
canonical-URL guard that every secondary adapter calls so the SSOT link is
never silently dropped.

Side-effecting primitives (sleeping, the clock, the RNG) are injected as
keyword-only parameters so the helpers stay deterministic under test.

### Functions

| [`atomic_write_json`](#article.util.atomic_write_json)(path, data, \*[, indent])      | Write `data` as JSON atomically (temp file + `os.replace`).             |
|---------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------|
| [`coalesce`](#article.util.coalesce)(\*values)                               | First non-`None` value, else `None` (SQL `COALESCE`).                   |
| [`get_logger`](#article.util.get_logger)([name])                               | Return the package logger, attaching a single stderr handler once.      |
| [`human_delay`](#article.util.human_delay)(min_seconds, max_seconds, \*[, ...]) | Sleep a randomized, human-like interval; return the delay used.         |
| [`read_json`](#article.util.read_json)(path, \*[, default])                   | Read and parse a JSON file, returning `default` if it doesn't exist.    |
| [`require_canonical_url`](#article.util.require_canonical_url)(platform, canonical_url)   | Return `canonical_url` or raise — the SSOT link is never optional.      |
| [`run_sync`](#article.util.run_sync)(coro)                                   | Run an async coroutine to completion from sync code (CLI entry points). |
| [`utcnow_iso`](#article.util.utcnow_iso)(\*[, \_now])                          | Current UTC time as an ISO-8601 string (clock injectable for tests).    |

### Classes

| [`suppress_errors`](#article.util.suppress_errors)()   | A tiny `contextlib.suppress(Exception)` without the import churn.   |
|----------------------------------------------------------------------|---------------------------------------------------------------------|

### article.util.atomic_write_json(path, data, , indent=2)

Write `data` as JSON atomically (temp file + `os.replace`).

Creates parent directories as needed. The temp-then-replace dance means a
crashed write never leaves a half-written state file behind.

* **Return type:**
  [`None`](https://docs.python.org/3/builtins/constants.html#None)

### article.util.coalesce(\*values)

First non-`None` value, else `None` (SQL `COALESCE`).

* **Return type:**
  [`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`TypeVar`](https://docs.python.org/3/library/typing.html#typing.TypeVar)(`T`)]

```pycon
>>> coalesce(None, None, 3, 4)
3
>>> coalesce(None, None) is None
True
```

### article.util.get_logger(name='article')

Return the package logger, attaching a single stderr handler once.

Idempotent: repeated calls don’t stack handlers.

* **Return type:**
  [`Logger`](https://docs.python.org/3/library/logging.html#logging.Logger)

```pycon
>>> log = get_logger()
>>> log.name
'article'
>>> get_logger() is log
True
```

### *async* article.util.human_delay(min_seconds, max_seconds, \*, \_sleep=<function sleep>, \_rand=<bound method Random.uniform of <random.Random object>>)

Sleep a randomized, human-like interval; return the delay used.

Used between scripted browser actions so automation of one’s own account
paces like a person. The sleeper and RNG are injectable for deterministic
tests:

* **Return type:**
  [`float`](https://docs.python.org/3/builtins/functions.html#float)

```pycon
>>> import asyncio
>>> async def _no_sleep(_): pass
>>> asyncio.run(human_delay(0.5, 0.5, _sleep=_no_sleep))
0.5
```

### article.util.read_json(path, , default=None)

Read and parse a JSON file, returning `default` if it doesn’t exist.

* **Return type:**
  [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)

### article.util.require_canonical_url(platform, canonical_url)

Return `canonical_url` or raise — the SSOT link is never optional.

Every *secondary* adapter calls this first so a missing canonical link
fails loudly instead of silently emitting a self-canonical post.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

```pycon
>>> require_canonical_url("medium", "https://x.substack.com/p/y")
'https://x.substack.com/p/y'
>>> require_canonical_url("medium", None)
Traceback (most recent call last):
...
article.base.AdapterError: medium: canonical_url is required for syndication but was missing
```

### article.util.run_sync(coro)

Run an async coroutine to completion from sync code (CLI entry points).

A thin, named wrapper over [`asyncio.run()`](https://docs.python.org/3/library/asyncio-runner.html#asyncio.run) so the dispatch-to-interface
seam is obvious and easy to swap (e.g. for an existing event loop later).

* **Return type:**
  [`TypeVar`](https://docs.python.org/3/library/typing.html#typing.TypeVar)(`T`)

### *class* article.util.suppress_errors

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

A tiny `contextlib.suppress(Exception)` without the import churn.

### article.util.utcnow_iso(\*, \_now=<function <lambda>>)

Current UTC time as an ISO-8601 string (clock injectable for tests).

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

```pycon
>>> from datetime import datetime, timezone
>>> utcnow_iso(_now=lambda: datetime(2026, 6, 21, tzinfo=timezone.utc))
'2026-06-21T00:00:00+00:00'
```
