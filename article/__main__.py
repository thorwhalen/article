# PYTHON_ARGCOMPLETE_OK
"""Command-line entry point for the ``article`` publishing pipeline.

Two commands mirror the two phases, and a third is the everyday shortcut for
phase 1 — all thin wrappers over the very same :mod:`article.engine` and
adapter functions the Python API exposes (dispatch-to-interface: one
implementation, many front-ends)::

    python -m article publish-primary      article.json
    python -m article syndicate-secondary  article.json
    python -m article draft-substack       essay.md      # unpublished draft
    python -m article draft-substack       essay.md --dry-run   # no credentials

Common options: ``--env-file`` (where to read secrets), ``--state-path``
(the SSOT state file), ``--json-out`` (machine-readable summary). Phase 2 also
takes ``--platforms medium,dev_to`` to syndicate a subset.
"""

from __future__ import annotations

import argparse
import json
from typing import Optional

import cw

from .adapters import substack as _substack
from .base import SUBSTACK, ArticleError, RunSummary
from .config import SubstackConfig, load_article, load_settings
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
        raise cw.CommandError(str(e)) from e
    store = JsonStateStore(settings.state_path)
    return settings, article, store


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
        raise cw.CommandError(str(e)) from e
    return _render(summary, json_out=json_out)


def _render_dry_run(report: dict) -> str:
    counts = ", ".join(f"{n} {k}" for k, n in report["counts"].items()) or "empty"
    lines = [
        f"Dry run (nothing sent): {report['title']!r} -> slug {report['slug']}",
        f"  converts to: {counts}",
        *(f"  warning: {w}" for w in report["warnings"]),
    ]
    return "\n".join(lines)


def draft_substack(
    article_path: str,
    *,
    env_file: Optional[str] = None,
    state_path: Optional[str] = None,
    tables: Optional[str] = None,
    dry_run: bool = False,
    json_out: bool = False,
):
    """Create an UNPUBLISHED Substack draft from a Markdown file; never publishes."""
    settings, article, store = _prepare(
        article_path, env_file=env_file, state_path=state_path
    )
    config = article.platforms.substack or SubstackConfig()
    if tables is not None:
        config = config.model_copy(update={"tables": tables})
    try:
        if dry_run:
            report = _substack.dry_run(article, config=config)
            return json.dumps(report, indent=2) if json_out else _render_dry_run(report)
        platforms = article.platforms.model_copy(update={SUBSTACK: config})
        article = article.model_copy(update={"platforms": platforms})
        summary = run_sync(_publish_primary(article, settings=settings, store=store))
    except ArticleError as e:
        raise cw.CommandError(str(e)) from e
    if not summary.ok:
        raise cw.CommandError(summary.failures[0].error)
    if json_out:
        return _render(summary, json_out=True)
    detail = summary.by_platform[SUBSTACK].detail
    return f"{summary.render()}\nEdit the draft: {detail.get('edit_url')}"


#: SSOT list of dispatchable commands (``cw`` maps ``_`` in names to ``-``).
_dispatch_funcs = [publish_primary, syndicate_secondary, draft_substack]

#: Per-parameter ``add_argument`` particulars the signature cannot carry -- here, the
#: one ``help`` string that used to ride on an ``@argh.arg`` decorator. ``cw`` reads
#: ``config``, never decorator metadata, so this is where such declarations live now.
_dispatch_config = {
    command: {"article_path": {"help": "Path to the article JSON file"}}
    for command in ("publish-primary", "syndicate-secondary")
}
_dispatch_config["draft-substack"] = {
    "article_path": {"help": "Path to the essay Markdown file (or article JSON)"},
    "tables": {
        "choices": ["error", "code"],
        "help": "Markdown tables: refuse (error, the default) or keep as code blocks",
    },
    "dry_run": {"help": "Check and convert only; no credentials, nothing sent"},
}


def mk_parser() -> argparse.ArgumentParser:
    """Build the CLI parser -- a plain :class:`argparse.ArgumentParser`, no I/O.

    The single place the command list and its per-parameter declarations meet, so a
    test that inspects the grammar inspects the very parser :func:`main` dispatches.
    """
    return cw.mk_parser(_dispatch_funcs, config=_dispatch_config)


def main() -> int:
    """Dispatch a CLI command and return its exit code.

    ``cw.run`` offers the parser to ``argcomplete`` itself (the
    ``# PYTHON_ARGCOMPLETE_OK`` marker on line 1 is what the shell hook looks for),
    so there is no hand-written completion block to keep in step.
    """
    return cw.run(mk_parser())


if __name__ == "__main__":
    raise SystemExit(main())
