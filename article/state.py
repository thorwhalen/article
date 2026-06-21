"""Pipeline state store — a ``MutableMapping`` facade over a JSON backend.

The canonical URL produced in phase 1 is the SSOT that ties the two phases
together, and it lives here, keyed by article ``slug``. Exposing it as a
:class:`collections.abc.MutableMapping` means callers depend only on the
mapping interface — the JSON file can later be swapped for SQLite, Redis, S3
(e.g. any ``dol`` store), or a cloud KV with zero changes upstream
(open-closed). Each value is a JSON-serializable per-article record, e.g.::

    {
        "slug": "hello-world",
        "title": "Hello World",
        "canonical_url": "https://me.substack.com/p/hello-world",
        "primary": {...},          # phase-1 result record
        "syndication": {"medium": {...}, "dev_to": {...}},
        "updated_at": "2026-06-21T...",
    }
"""

from __future__ import annotations

from collections.abc import Iterator, MutableMapping
from typing import Any, Optional

from .util import PathLike, atomic_write_json, read_json, utcnow_iso

#: The state-record key holding the canonical SSOT URL.
CANONICAL_URL_KEY = "canonical_url"


class JsonStateStore(MutableMapping):
    """A whole-file JSON ``MutableMapping`` keyed by article slug.

    Reads parse the file fresh and writes replace it atomically, so the file on
    disk is always the source of truth (no in-memory drift) and never left
    half-written.

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
    """

    def __init__(self, path: PathLike):
        self.path = path

    # --- the four MutableMapping primitives ------------------------------- #

    def _load(self) -> dict[str, Any]:
        data = read_json(self.path, default={})
        return data if isinstance(data, dict) else {}

    def _dump(self, data: dict[str, Any]) -> None:
        atomic_write_json(self.path, data)

    def __getitem__(self, slug: str) -> dict[str, Any]:
        data = self._load()
        return data[slug]

    def __setitem__(self, slug: str, record: dict[str, Any]) -> None:
        data = self._load()
        data[slug] = dict(record)
        self._dump(data)

    def __delitem__(self, slug: str) -> None:
        data = self._load()
        del data[slug]
        self._dump(data)

    def __iter__(self) -> Iterator[str]:
        return iter(self._load())

    def __len__(self) -> int:
        return len(self._load())

    # --- thin conveniences on top of the mapping -------------------------- #

    def update_record(self, slug: str, **fields: Any) -> dict[str, Any]:
        """Merge ``fields`` into the record for ``slug`` (read-modify-write).

        Creates the record if absent and stamps ``updated_at``. Returns the
        merged record.

        >>> import tempfile, os
        >>> store = JsonStateStore(os.path.join(tempfile.mkdtemp(), "s.json"))
        >>> _ = store.update_record("x", title="T")
        >>> rec = store.update_record("x", canonical_url="c")
        >>> rec["title"], rec["canonical_url"]
        ('T', 'c')
        """
        record = dict(self.get(slug, {}))
        record["slug"] = slug
        record.update(fields)
        record["updated_at"] = utcnow_iso()
        self[slug] = record
        return record

    def get_canonical_url(self, slug: str) -> Optional[str]:
        """The recorded canonical URL for ``slug``, or ``None`` if not yet set."""
        return self.get(slug, {}).get(CANONICAL_URL_KEY)

    def set_canonical_url(self, slug: str, canonical_url: str) -> None:
        """Record ``canonical_url`` for ``slug`` (the phase-1 → phase-2 SSOT handoff)."""
        self.update_record(slug, **{CANONICAL_URL_KEY: canonical_url})


def default_state_store(state_path: PathLike) -> JsonStateStore:
    """Construct the default (JSON-file) state store at ``state_path``.

    A single seam to swap the backend implementation package-wide.
    """
    return JsonStateStore(state_path)
