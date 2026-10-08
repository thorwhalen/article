# article.state

Pipeline state store — a `MutableMapping` facade over a JSON backend.

The canonical URL produced in phase 1 is the SSOT that ties the two phases
together, and it lives here, keyed by article `slug`. Exposing it as a
[`collections.abc.MutableMapping`](https://docs.python.org/3/library/collections.abc.html#collections.abc.MutableMapping) means callers depend only on the
mapping interface — the JSON file can later be swapped for SQLite, Redis, S3
(e.g. any `dol` store), or a cloud KV with zero changes upstream
(open-closed). Each value is a JSON-serializable per-article record, e.g.:

```default
{
    "slug": "hello-world",
    "title": "Hello World",
    "canonical_url": "https://me.substack.com/p/hello-world",
    "primary": {...},          # phase-1 result record
    "syndication": {"medium": {...}, "dev_to": {...}},
    "updated_at": "2026-06-21T...",
}
```

### Module Attributes

| [`CANONICAL_URL_KEY`](#article.state.CANONICAL_URL_KEY)   | The state-record key holding the canonical SSOT URL.   |
|----------------------------------------------------------------------|--------------------------------------------------------|

### Functions

| [`default_state_store`](#article.state.default_state_store)(state_path)   | Construct the default (JSON-file) state store at `state_path`.   |
|------------------------------------------------------------------------------------|------------------------------------------------------------------|

### Classes

| [`JsonStateStore`](#article.state.JsonStateStore)(path)   | A whole-file JSON `MutableMapping` keyed by article slug.   |
|-------------------------------------------------------------------------|-------------------------------------------------------------|

### article.state.CANONICAL_URL_KEY *= 'canonical_url'*

The state-record key holding the canonical SSOT URL.

### *class* article.state.JsonStateStore(path)

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

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]

```pycon
>>> import tempfile, os
>>> store = JsonStateStore(os.path.join(tempfile.mkdtemp(), "s.json"))
>>> _ = store.update_record("x", title="T")
>>> rec = store.update_record("x", canonical_url="c")
>>> rec["title"], rec["canonical_url"]
('T', 'c')
```

### article.state.default_state_store(state_path)

Construct the default (JSON-file) state store at `state_path`.

A single seam to swap the backend implementation package-wide.

* **Return type:**
  [`JsonStateStore`](#article.state.JsonStateStore)
