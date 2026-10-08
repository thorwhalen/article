"""Shared fixtures: an offline stand-in for python-substack's ``Api``."""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

PUBLICATION_URL = "https://tester.substack.com"

#: A valid 1x1 PNG, so "local image" fixtures are real image files.
PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


class FakeSubstackApi:
    """Records the calls the adapter makes; any other attribute is a test failure.

    Only the draft-creation calls exist here. ``publish_draft``,
    ``prepublish_draft`` and everything else raise, so a code path that tries to
    publish fails the test that reaches it.
    """

    publication_url = f"{PUBLICATION_URL}/api/v1"

    def __init__(self):
        self.uploaded: list[str] = []
        self.posted: list[dict] = []
        self.updates: list[tuple] = []
        self.tagged: list[tuple] = []

    def get_user_id(self):
        return 42

    def get_image(self, path):
        assert Path(path).is_file(), f"upload of a missing file: {path}"
        self.uploaded.append(str(Path(path).resolve()))
        return {"url": f"https://substackcdn.example/{Path(path).name}"}

    def post_draft(self, body):
        self.posted.append(body)
        return {"id": 1234}

    def put_draft(self, draft_id, **fields):
        self.updates.append((draft_id, fields))
        return {"id": draft_id, **fields}

    def add_tags_to_post(self, draft_id, tags):
        self.tagged.append((draft_id, tags))
        return {}

    def __getattr__(self, name):
        raise AssertionError(f"the adapter called Api.{name}, which it must never do")


@pytest.fixture
def fake_api():
    return FakeSubstackApi()


@pytest.fixture
def png_bytes():
    return PNG_BYTES
