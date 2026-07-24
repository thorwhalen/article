# PYTHON_ARGCOMPLETE_OK
"""Command-line entry point for the ``article`` publishing pipeline.

Two commands, mirroring the two phases — both thin wrappers over the very same
:mod:`article.engine` functions the Python API exposes (dispatch-to-interface:
one implementation, many front-ends)::

    python -m article publish-primary      article.json
    python -m article syndicate-secondary  article.json

Common options: ``--env-file`` (where to read secrets), ``--state-path``
(the SSOT state file), ``--json-out`` (machine-readable summary). Phase 2 also
takes ``--platforms medium,dev_to`` to syndicate a subset.
"""

from __future__ import annotations

import json
from typing import Optional

import argh

from .base import ArticleError, RunSummary
from .config import load_article, load_settings
from .engine import publish_primary as _publish_primary
from .engine import syndicate_secondary as _syndicate_secondary
from .state import JsonStateStore
from .util import run_sync


def _render(summary: RunSummary, *, json_out: bool) -> str:
    return json.dumps(summary.as_record(), indent=2) if json_out else summary.render()


def _prepare(article_path: str, *, env_file: Optional[str], state_path: Optional[str]):
    """Shared setup: load settings + article + state store (with friendly errors)."""
    try:
        overrides = {"state_path": state_path} if state_path else {}
        settings = load_settings(env_file=env_file, **overrides)
        article = load_article(article_path)
    except ArticleError as e:
        raise argh.CommandError(str(e)) from e
    store = JsonStateStore(settings.state_path)
    return settings, article, store


@argh.arg("article_path", help="Path to the article JSON file")
def publish_primary(
    article_path: str,
    *,
    env_file: Optional[str] = None,
    state_path: Optional[str] = None,
    json_out: bool = False,
):
    """Phase 1 — publish to the primary platform (Substack) and record canonical_url."""
    settings, article, store = _prepare(
        article_path, env_file=env_file, state_path=state_path
    )
    summary = run_sync(_publish_primary(article, settings=settings, store=store))
    return _render(summary, json_out=json_out)


@argh.arg("article_path", help="Path to the article JSON file")
def syndicate_secondary(
    article_path: str,
    *,
    env_file: Optional[str] = None,
    state_path: Optional[str] = None,
    platforms: Optional[str] = None,
    json_out: bool = False,
):
    """Phase 2 — syndicate to secondary platforms, injecting canonical_url for SEO."""
    settings, article, store = _prepare(
        article_path, env_file=env_file, state_path=state_path
    )
    selected = [p.strip() for p in platforms.split(",")] if platforms else None
    try:
        summary = run_sync(
            _syndicate_secondary(
                article, settings=settings, store=store, platforms=selected
            )
        )
    except ArticleError as e:
        raise argh.CommandError(str(e)) from e
    return _render(summary, json_out=json_out)


#: SSOT list of dispatchable commands (argh maps ``_`` in names to ``-``).
_dispatch_funcs = [publish_primary, syndicate_secondary]


def main() -> None:
    """Assemble the argh parser and dispatch (with optional tab completion)."""
    parser = argh.ArghParser()
    parser.add_commands(_dispatch_funcs)
    try:
        import argcomplete

        argcomplete.autocomplete(parser)
    except ImportError:
        pass
    parser.dispatch()


if __name__ == "__main__":
    main()
