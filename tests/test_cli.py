"""Characterization tests pinning the ``article`` command-line grammar.

Recorded from the pre-migration ``argh`` implementation and replayed against
:mod:`cw`. Three things here would not be caught by any other test:

* the ``article-path`` **help string**, which used to ride on an ``@argh.arg``
  decorator. ``cw`` reads ``config``, never decorator metadata, so deleting the
  decorator without moving the declaration drops the help silently — no error, just a
  quietly poorer ``--help``;
* the ``CommandError`` contract — one line to stderr, no traceback, **exit 1**;
* the exit code itself, which ``cw.dispatch`` *returns* where argh raised it, so
  ``__main__`` must ``raise SystemExit(main())``.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

import pytest

from article.__main__ import _dispatch_funcs, main, mk_parser

COMMANDS = ("publish-primary", "syndicate-secondary")


@pytest.fixture(scope="module")
def parser():
    """The very parser :func:`article.__main__.main` dispatches, built without I/O.

    Built through ``mk_parser`` rather than reassembled here, so a declaration that
    stops reaching the real parser cannot keep passing these tests. ``sys.argv[0]`` is
    pinned because argparse derives ``prog`` from it at construction time.
    """
    argv = sys.argv
    sys.argv = ["article"]
    try:
        return mk_parser()
    finally:
        sys.argv = argv


@pytest.fixture(scope="module")
def subparsers(parser):
    action = next(
        a for a in parser._actions if isinstance(a, argparse._SubParsersAction)
    )
    return action.choices


def _run(*argv, cwd=None):
    """Run ``python -m article ARGV`` end to end."""
    env = {k: v for k, v in os.environ.items() if k != "COLUMNS"}
    return subprocess.run(
        [sys.executable, "-m", "article", *argv],
        capture_output=True,
        text=True,
        cwd=cwd,
        env={"COLUMNS": "80", **env},
    )


# --------------------------------------------------------------------------- grammar


def test_the_two_phases_are_the_two_commands(parser, subparsers):
    assert [f.__name__ for f in _dispatch_funcs] == [
        "publish_primary",
        "syndicate_secondary",
    ]
    assert tuple(subparsers) == COMMANDS
    assert parser.format_usage() == (
        "usage: article [-h] {publish-primary,syndicate-secondary} ...\n"
    )


@pytest.mark.parametrize(
    "command, usage",
    [
        (
            "publish-primary",
            "usage: article publish-primary [-h] [-e ENV_FILE] [-s STATE_PATH] [-j]"
            " article-path",
        ),
        (
            "syndicate-secondary",
            "usage: article syndicate-secondary [-h] [-e ENV_FILE] [-s STATE_PATH]"
            " [-p PLATFORMS] [-j] article-path",
        ),
    ],
)
def test_each_command_keeps_its_recorded_usage_line(subparsers, command, usage):
    """Flag spellings and short options, exactly as argh rendered them.

    Line wrapping is normalised away — it depends on the terminal width the test
    happens to run under.
    """
    assert " ".join(subparsers[command].format_usage().split()) == usage


@pytest.mark.parametrize("command", COMMANDS)
def test_the_positional_keeps_the_help_that_used_to_be_an_argh_arg(
    subparsers, command
):
    """The migrated ``@argh.arg(help=...)`` declaration.

    ``cw`` does **not** read argh's decorator metadata, so dropping
    ``_dispatch_config`` would leave this help string at the ``-`` placeholder with no
    error anywhere. This test is the only thing that would notice.
    """
    positional = next(
        a for a in subparsers[command]._actions if not a.option_strings
    )
    assert positional.dest == "article-path"  # argh hyphenates positionals
    assert positional.help == "Path to the article JSON file"


@pytest.mark.parametrize("command", COMMANDS)
def test_defaults_match_the_function_signatures(subparsers, command):
    namespace = subparsers[command].parse_args(["a.json"])
    assert getattr(namespace, "article-path") == "a.json"
    assert namespace.env_file is None
    assert namespace.state_path is None
    assert namespace.json_out is False


def test_platforms_is_only_on_phase_two(subparsers):
    def usage(command):
        return " ".join(subparsers[command].format_usage().split())

    assert "-p PLATFORMS" in usage("syndicate-secondary")
    assert "-p PLATFORMS" not in usage("publish-primary")


# ------------------------------------------------------------------------ exit codes


def test_no_arguments_prints_usage_to_stdout_and_exits_zero():
    """argh's behaviour, which bare argparse does not reproduce. Pinned deliberately."""
    done = _run()
    assert done.returncode == 0
    assert done.stdout.startswith("usage: ")
    assert done.stderr == ""


@pytest.mark.parametrize(
    "argv",
    [
        ("no-such-command",),
        ("publish-primary",),  # missing required positional
        ("syndicate-secondary",),  # missing required positional
        ("publish-primary", "--env-file"),  # option missing its value
    ],
)
def test_bad_invocations_exit_two(argv):
    done = _run(*argv)
    assert done.returncode == 2
    assert done.stdout == ""
    assert done.stderr.startswith("usage: ")


@pytest.mark.parametrize("command", COMMANDS)
def test_an_unreadable_article_is_a_command_error_not_a_traceback(command, tmp_path):
    """``CommandError``: one line to stderr, **exit 1**, and no traceback."""
    done = _run(command, "no_such_article.json", cwd=tmp_path)
    assert done.returncode == 1
    assert done.stdout == ""
    assert done.stderr.startswith("CommandError: Could not read article from ")
    assert "Traceback" not in done.stderr


def test_main_returns_the_exit_code_rather_than_swallowing_it(monkeypatch, tmp_path):
    """The in-process half: ``main()`` yields an int, not ``None``.

    This is what makes ``raise SystemExit(main())`` in ``__main__`` — and the console
    script's own ``sys.exit(main())`` — report the failure instead of success.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["article", "no-such-command"])
    assert main() == 2
    monkeypatch.setattr(
        sys, "argv", ["article", "publish-primary", "no_such_article.json"]
    )
    assert main() == 1
