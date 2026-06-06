import os

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from web_admin.rss.api.endpoints import feed


def make_request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/media/1/file.txt",
            "headers": [(b"host", b"testserver")],
            "client": ("127.0.0.1", 12345),
            "scheme": "http",
        }
    )


def test_rss_public_base_url_ignores_request_host(monkeypatch):
    monkeypatch.setattr(feed, "RSS_MEDIA_BASE_URL", "")
    monkeypatch.setattr(feed.settings, "RSS_BASE_URL", None)
    monkeypatch.setattr(feed.settings, "RSS_HOST", "127.0.0.1")
    monkeypatch.setattr(feed.settings, "RSS_PORT", 8000)

    assert feed._get_rss_public_base_url() == "http://127.0.0.1:8000"


@pytest.mark.asyncio
async def test_get_media_serves_file_inside_rule_media_dir(tmp_path, monkeypatch):
    rule_dir = tmp_path / "media" / "1"
    rule_dir.mkdir(parents=True)
    media_file = rule_dir / "file.txt"
    media_file.write_text("ok", encoding="utf-8")

    monkeypatch.setattr(feed, "get_rule_media_dir", lambda rule_id: str(rule_dir))

    response = await feed.get_media(1, "file.txt", make_request())

    assert str(response.path) == str(media_file.resolve())


@pytest.mark.asyncio
async def test_get_media_rejects_path_traversal(tmp_path, monkeypatch):
    rule_dir = tmp_path / "media" / "1"
    rule_dir.mkdir(parents=True)

    monkeypatch.setattr(feed, "get_rule_media_dir", lambda rule_id: str(rule_dir))

    with pytest.raises(HTTPException) as exc:
        await feed.get_media(1, "../secret.txt", make_request())

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_get_media_rejects_symlink_escape(tmp_path, monkeypatch):
    if not hasattr(os, "symlink"):
        pytest.skip("symlink not supported")

    rule_dir = tmp_path / "media" / "1"
    rule_dir.mkdir(parents=True)
    secret_file = tmp_path / "secret.txt"
    secret_file.write_text("secret", encoding="utf-8")
    link_path = rule_dir / "link.txt"
    os.symlink(secret_file, link_path)

    monkeypatch.setattr(feed, "get_rule_media_dir", lambda rule_id: str(rule_dir))

    with pytest.raises(HTTPException) as exc:
        await feed.get_media(1, "link.txt", make_request())

    assert exc.value.status_code == 400
