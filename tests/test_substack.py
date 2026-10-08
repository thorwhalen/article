"""Offline tests for the Substack draft path (python-substack's client is faked).

The Markdown conversion is python-substack's real one; only the HTTP client is
replaced, by :class:`conftest.FakeSubstackApi`, which fails any test that
reaches a publish call. What these pin: footnotes, captions and uploaded images
survive into the posted draft; tables, inline images, missing images and raw
HTML are refused before anything is uploaded; the tool never publishes.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys

import pytest

pytest.importorskip("substack", reason="needs the substack extra")

from article import AdapterError, load_article  # noqa: E402
from article.adapters.substack import (  # noqa: E402
    create_substack_draft,
    dry_run,
    make_substack_api,
    preflight,
)
from article.base import MEDIUM, PublishState  # noqa: E402
from article.config import SubstackConfig  # noqa: E402
from article.registry import get_adapter  # noqa: E402

from conftest import PUBLICATION_URL  # noqa: E402

ESSAY = """\
---
subtitle: What survives the trip
tags: [agile, ai]
description: A test essay.
---
# The Agile Religion

A claim.[^1] Another, with $x^2$ in it.[^dfw]

![A figure](images/fig%201.png "Figure 1: the caption")

[^1]: First note.
[^dfw]: A second note, *with emphasis*.
"""


@pytest.fixture
def essay_dir(tmp_path, png_bytes):
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "fig 1.png").write_bytes(png_bytes)
    (tmp_path / "essay.md").write_text(ESSAY, encoding="utf-8")
    return tmp_path


def _body(api):
    (draft,) = api.posted
    return json.loads(draft["draft_body"])["content"]


def _of_type(nodes, type_):
    found = []
    for node in nodes:
        if node.get("type") == type_:
            found.append(node)
        found += _of_type(node.get("content") or [], type_)
    return found


def _text(node):
    return "".join(t.get("text", "") for t in _of_type([node], "text"))


# --------------------------------------------------------------------------- the draft


def test_essay_becomes_a_draft_with_footnotes_captions_and_uploaded_images(
    essay_dir, fake_api, monkeypatch
):
    monkeypatch.chdir(essay_dir.parent)  # images resolve against the file, not the cwd
    art = load_article(str(essay_dir / "essay.md"))
    result = create_substack_draft(art, api=fake_api)

    body = _body(fake_api)
    footnotes = _of_type(body, "footnote")
    assert len(_of_type(body, "footnoteAnchor")) == 2
    assert [_text(f) for f in footnotes] == [
        "First note.",
        "A second note, with emphasis.",
    ]

    (image,) = _of_type(body, "captionedImage")
    assert (
        image["content"][0]["attrs"]["src"] == "https://substackcdn.example/fig 1.png"
    )
    assert _text(_of_type([image], "caption")[0]) == "Figure 1: the caption"
    assert fake_api.uploaded == [str((essay_dir / "images" / "fig 1.png").resolve())]
    assert _of_type(body, "latex")

    (draft,) = fake_api.posted
    assert (draft["draft_title"], draft["draft_subtitle"]) == (
        "The Agile Religion",
        "What survives the trip",
    )
    assert not _of_type(body, "heading")  # the H1 is the title, not body text
    assert fake_api.updates == [
        (
            1234,
            {
                "slug": "the-agile-religion",
                "search_engine_description": "A test essay.",
            },
        )
    ]
    assert fake_api.tagged == [(1234, ["agile", "ai"])]

    assert result.ok and result.status == "draft"
    assert result.url == f"{PUBLICATION_URL}/p/the-agile-religion"
    assert result.detail["edit_url"] == f"{PUBLICATION_URL}/publish/post/1234"
    assert result.detail["counts"]["footnotes"] == 2
    assert os.getcwd() == str(essay_dir.parent)  # the cwd is restored


def test_the_registered_adapter_creates_a_draft_too(essay_dir, fake_api):
    art = load_article(str(essay_dir / "essay.md"))
    result = asyncio.run(
        get_adapter("substack")(
            art, canonical_url=None, config=SubstackConfig(), secrets={}, api=fake_api
        )
    )
    assert result.ok and result.status == "draft" and len(fake_api.posted) == 1


def test_publishing_is_refused(essay_dir, fake_api):
    art = load_article(str(essay_dir / "essay.md"))
    with pytest.raises(AdapterError, match="only creates drafts"):
        create_substack_draft(
            art, config=SubstackConfig(publish_as_draft=False), api=fake_api
        )
    assert fake_api.posted == []


def test_missing_credentials_say_how_to_configure_them():
    with pytest.raises(AdapterError, match="SUBSTACK_COOKIES"):
        make_substack_api({})


# --------------------------------------------------------- what is refused, and when


TABLE = "| a | b |\n|---|---|\n| 1 | 2 |\n"


def test_a_table_is_refused_by_default_before_anything_is_sent(tmp_path, fake_api):
    art = load_article(
        {"title": "T", "slug": "t", "content_markdown": f"Intro.\n\n{TABLE}"}
    )
    with pytest.raises(AdapterError, match=r'body line 3 \("\| a \| b \|"\): a table'):
        create_substack_draft(art, api=fake_api)
    assert fake_api.posted == [] and fake_api.uploaded == []


def test_tables_code_keeps_the_table_as_a_code_block(fake_api):
    art = load_article({"title": "T", "slug": "t", "content_markdown": TABLE})
    create_substack_draft(art, api=fake_api, tables="code")
    (block,) = _of_type(_body(fake_api), "codeBlock")
    assert _text(block) == TABLE.rstrip()


def test_a_table_renderer_can_replace_a_table_with_an_image(
    tmp_path, png_bytes, fake_api
):
    (tmp_path / "table.png").write_bytes(png_bytes)
    art = load_article(
        {
            "title": "T",
            "slug": "t",
            "content_markdown": TABLE,
            "assets_dir": str(tmp_path),
        }
    )
    create_substack_draft(
        art, api=fake_api, tables=lambda md: '![table](table.png "Table 1")\n'
    )
    (image,) = _of_type(_body(fake_api), "captionedImage")
    assert _text(image) == "Table 1"
    assert len(fake_api.uploaded) == 1


def test_every_problem_is_listed_at_once(tmp_path):
    md = (
        "![fig](here.png)\n*Figure 1: a caption on the next line*\n\n"
        "![gone](missing.png)\n\n"
        "<table><tr><td>x</td></tr></table>\n\n" + TABLE
    )
    (tmp_path / "here.png").write_bytes(b"x")
    with pytest.raises(AdapterError) as info:
        preflight(md, assets_dir=str(tmp_path))
    message = str(info.value)
    assert "4 problem(s)" in message
    assert "an image shares its paragraph" in message
    assert "image file not found: missing.png" in message
    assert "a raw HTML block" in message
    assert "a table" in message


def test_html_comments_pass_and_inline_html_is_a_warning():
    md, warnings = preflight("<!-- a note -->\n\nText<br>more.\n")
    assert warnings == ['body line 3 ("Text<br>more."): inline HTML <br> is dropped']


# ------------------------------------------------------------------------- dry run


def test_dry_run_needs_no_credentials_and_reports_what_survives(essay_dir):
    report = dry_run(load_article(str(essay_dir / "essay.md")))
    assert report["slug"] == "the-agile-religion"
    assert report["counts"] == {
        "footnote_refs": 2,
        "footnotes": 2,
        "images": 1,
        "captions": 1,
        "latex_inline": 1,
        "paragraphs": 3,
    }


def _run(*argv, cwd, env_file):
    env = {k: v for k, v in os.environ.items() if not k.startswith("SUBSTACK_")}
    return subprocess.run(
        [sys.executable, "-m", "article", *argv, "--env-file", str(env_file)],
        capture_output=True,
        text=True,
        cwd=cwd,
        env=env,
    )


def test_cli_dry_run(essay_dir):
    (essay_dir / "empty.env").write_text("")
    done = _run(
        "draft-substack", "essay.md", "--dry-run", cwd=essay_dir, env_file="empty.env"
    )
    assert done.returncode == 0, done.stderr
    assert "2 footnotes" in done.stdout and "1 captions" in done.stdout


def test_cli_without_credentials_is_one_line_exit_one(essay_dir):
    (essay_dir / "empty.env").write_text("")
    done = _run("draft-substack", "essay.md", cwd=essay_dir, env_file="empty.env")
    assert done.returncode == 1
    # The engine logs to stderr first; the error itself is the one last line.
    assert done.stderr.splitlines()[-1].startswith(
        "CommandError: substack: no credentials"
    )
    assert "Traceback" not in done.stderr


# ------------------------------------------------------------------- markdown source


def test_markdown_title_slug_and_assets_dir(essay_dir):
    art = load_article(str(essay_dir / "essay.md"))
    assert (art.title, art.slug, art.tags) == (
        "The Agile Religion",
        "the-agile-religion",
        ["agile", "ai"],
    )
    assert art.assets_dir == str(essay_dir.resolve())
    assert not art.content_markdown.startswith("#")


def test_markdown_without_a_title_is_a_clear_error(tmp_path):
    (tmp_path / "x.md").write_text("Just text.\n")
    with pytest.raises(Exception, match="No title"):
        load_article(str(tmp_path / "x.md"))


# --------------------------------------------------------------------------- medium


def test_medium_is_an_honest_manual_import_step():
    art = load_article({"title": "T", "slug": "t", "content_markdown": "x"})
    result = asyncio.run(
        get_adapter(MEDIUM)(
            art, canonical_url="https://me.substack.com/p/t", config=None, secrets={}
        )
    )
    assert result.state is PublishState.MANUAL and not result.ok
    assert result.url is None  # nothing was posted anywhere
    assert "https://medium.com/p/import" in result.detail["next_step"]


# ------------------------------------------------------------- review regressions


@pytest.mark.parametrize(
    "md, expected",
    [
        (
            "One[^1]\n\n[^1]: see[^2]\n\n[^2]: two\n",
            "referenced inside another footnote",
        ),
        ("Body[^9]\n", "[^9] has no definition"),
        ("x\n\n[^u]: unused\n", "[^u] is defined but never referenced"),
        ("![a](data:image/png;base64,AAAA)\n", "data: image cannot be uploaded"),
    ],
)
def test_footnote_and_data_uri_losses_are_refused(md, expected):
    with pytest.raises(AdapterError, match=re.escape(expected)):
        preflight(md)


def test_a_slug_substack_changes_is_the_one_recorded(fake_api):
    fake_api.put_draft = lambda draft_id, **f: {"id": draft_id, "slug": "t-2"}
    art = load_article({"title": "T", "slug": "t", "content_markdown": "x"})
    result = create_substack_draft(art, api=fake_api)
    assert result.url == f"{PUBLICATION_URL}/p/t-2"
    assert "changed the slug" in result.detail["warnings"][0]


def test_a_publication_url_without_scheme_gets_https(fake_api):
    art = load_article({"title": "T", "slug": "t", "content_markdown": "x"})
    result = create_substack_draft(
        art, api=fake_api, secrets={"publication_url": "me.substack.com/"}
    )
    assert result.url == "https://me.substack.com/p/t"


def test_front_matter_survives_a_byte_order_mark(tmp_path):
    (tmp_path / "x.md").write_text(
        "\ufeff---\nsubtitle: S\n---\n# T\n\nx\n", encoding="utf-8"
    )
    assert load_article(str(tmp_path / "x.md")).subtitle == "S"


@pytest.mark.parametrize(
    "md, title",
    [
        ("# C# and F#\n\nx\n", "C# and F#"),
        ("~~~\n```\n# not a title\n~~~\n# Real\n\nx\n", "Real"),
        ("> A preface.\n\n# The One Title\n\n## Section\n\nx\n", "The One Title"),
    ],
)
def test_title_heading_edge_cases(tmp_path, md, title):
    (tmp_path / "x.md").write_text(md)
    assert load_article(str(tmp_path / "x.md")).title == title


def test_several_h1s_after_other_content_are_ambiguous(tmp_path):
    (tmp_path / "x.md").write_text("Intro.\n\n# One\n\n# Two\n")
    with pytest.raises(Exception, match="Ambiguous title"):
        load_article(str(tmp_path / "x.md"))


def test_a_title_without_ascii_asks_for_a_slug(tmp_path):
    (tmp_path / "x.md").write_text("# 日本語\n\nx\n", encoding="utf-8")
    with pytest.raises(Exception, match="add a 'slug:'"):
        load_article(str(tmp_path / "x.md"))
