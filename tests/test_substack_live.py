"""Live smoke test: create a real Substack draft, check it, then delete it.

Skipped unless Substack credentials are in the environment (``SUBSTACK_COOKIES``,
``SUBSTACK_COOKIES_PATH``, or ``SUBSTACK_EMAIL`` + ``SUBSTACK_PASSWORD``; set
``SUBSTACK_PUBLICATION_URL`` too if you have several publications). It creates
one draft and deletes it again; it never publishes.
"""

from __future__ import annotations

import os

import pytest

pytest.importorskip("substack", reason="needs the substack extra")

from article import load_article  # noqa: E402
from article.adapters.substack import create_substack_draft, make_substack_api  # noqa: E402
from article.config import Settings  # noqa: E402

_CONFIGURED = bool(
    os.environ.get("SUBSTACK_COOKIES")
    or os.environ.get("SUBSTACK_COOKIES_PATH")
    or (os.environ.get("SUBSTACK_EMAIL") and os.environ.get("SUBSTACK_PASSWORD"))
)

pytestmark = pytest.mark.skipif(
    not _CONFIGURED, reason="no Substack credentials in the environment"
)


def test_a_real_draft_keeps_footnotes_and_captions(tmp_path, png_bytes):
    (tmp_path / "fig.png").write_bytes(png_bytes)
    (tmp_path / "smoke.md").write_text(
        "# article smoke test (delete me)\n\n"
        "A claim.[^1]\n\n"
        '![a pixel](fig.png "A caption")\n\n'
        "[^1]: A footnote.\n"
    )
    secrets = Settings(_env_file=None).secrets_for("substack")
    api = make_substack_api(secrets, publication_url=secrets["publication_url"])
    result = create_substack_draft(
        load_article(str(tmp_path / "smoke.md")), secrets=secrets, api=api
    )
    try:
        assert result.ok and result.status == "draft"
        draft = api.get_draft(result.detail["draft_id"])
        assert not draft.get("is_published")
        body = str(draft.get("draft_body"))
        assert "footnote" in body and "A caption" in body and "substackcdn" in body
    finally:
        api.delete_draft(result.detail["draft_id"])
