import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.download_service import DownloadService


@pytest.fixture
def tmp_download(tmp_path):
    return str(tmp_path / "downloads")


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.download_media = AsyncMock(return_value="/fake/path/file.bin")
    return client


@pytest.fixture
def service(mock_client, tmp_download):
    return DownloadService(client=mock_client, download_path=tmp_download)


def test_init_creates_directory(tmp_download, mock_client):
    assert not os.path.exists(tmp_download)
    DownloadService(client=mock_client, download_path=tmp_download)
    assert os.path.isdir(tmp_download)


@pytest.mark.asyncio
async def test_push_to_queue_downloads_file(service, mock_client, tmp_download):
    msg = SimpleNamespace(
        id=123,
        file=SimpleNamespace(name="test.txt"),
        media=MagicMock(),
    )
    result = await service.push_to_queue(msg, sub_folder="chat1")
    expected = os.path.join(tmp_download, "chat1", "test.txt")
    mock_client.download_media.assert_awaited_once()
    call_args = mock_client.download_media.call_args
    assert call_args[1]["file"] == expected or call_args[0][1] == expected


@pytest.mark.asyncio
async def test_push_to_queue_skips_existing(service, mock_client, tmp_download):
    msg = SimpleNamespace(
        id=456,
        file=SimpleNamespace(name="existing.txt"),
        media=MagicMock(),
    )
    sub_dir = os.path.join(tmp_download, "chat1")
    os.makedirs(sub_dir, exist_ok=True)
    with open(os.path.join(sub_dir, "existing.txt"), "w") as f:
        f.write("already here")

    result = await service.push_to_queue(msg, sub_folder="chat1")
    mock_client.download_media.assert_not_awaited()
    assert result == os.path.join(sub_dir, "existing.txt")


@pytest.mark.asyncio
async def test_push_to_queue_path_traversal(service, mock_client, tmp_download):
    msg = SimpleNamespace(
        id=789,
        file=SimpleNamespace(name="../../etc/passwd"),
        media=MagicMock(),
    )
    result = await service.push_to_queue(msg, sub_folder="chat1")
    assert "etc" not in result or tmp_download in result
    assert ".." not in result


@pytest.mark.asyncio
async def test_shutdown(service):
    await service.shutdown()
