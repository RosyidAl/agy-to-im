"""Tests for the async TelegramClient HTTP wrapper."""
from __future__ import annotations

import pytest
from pytest_httpx import HTTPXMock

from src.telegram import TelegramClient


pytestmark = pytest.mark.asyncio


async def test_get_updates_long_polls_with_offset_and_timeout(
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_response(
        url="https://api.telegram.org/botTOKEN/getUpdates?offset=42&timeout=30&allowed_updates=%5B%22message%22%2C%22callback_query%22%5D",
        method="GET",
        json={"ok": True, "result": [{"update_id": 50}]},
    )
    async with TelegramClient("TOKEN") as tg:
        updates = await tg.get_updates(offset=42, timeout=30)
    assert updates == [{"update_id": 50}]


async def test_get_updates_raises_on_telegram_error(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://api.telegram.org/botTOKEN/getUpdates?offset=1&timeout=30&allowed_updates=%5B%22message%22%2C%22callback_query%22%5D",
        method="GET",
        json={"ok": False, "description": "Unauthorized"},
        status_code=401,
    )
    async with TelegramClient("TOKEN") as tg:
        with pytest.raises(RuntimeError, match="Unauthorized"):
            await tg.get_updates(offset=1)


async def test_send_message_splits_long_text(httpx_mock: HTTPXMock) -> None:
    body = "x" * 9000
    for _ in range(3):
        httpx_mock.add_response(
            url="https://api.telegram.org/botTOKEN/sendMessage",
            method="POST",
            json={"ok": True, "result": {}},
        )
    async with TelegramClient("TOKEN") as tg:
        await tg.send_message(chat_id=10, text=body)
    requests = httpx_mock.get_requests()
    assert len(requests) == 3
    for r in requests:
        assert r.method == "POST"
        assert r.url.path == "/botTOKEN/sendMessage"


async def test_send_message_skips_empty_text(httpx_mock: HTTPXMock) -> None:
    async with TelegramClient("TOKEN") as tg:
        await tg.send_message(chat_id=10, text="")
    assert httpx_mock.get_requests() == []


async def test_send_chat_action_posts_typing(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://api.telegram.org/botTOKEN/sendChatAction",
        method="POST",
        json={"ok": True, "result": True},
    )
    async with TelegramClient("TOKEN") as tg:
        await tg.send_chat_action(chat_id=10, action="typing")
    req = httpx_mock.get_requests()[0]
    assert req.method == "POST"
    body = req.read().decode()
    assert "typing" in body
    assert "10" in body


async def test_set_my_commands(httpx_mock: HTTPXMock) -> None:
    import json
    httpx_mock.add_response(
        url="https://api.telegram.org/botTOKEN/setMyCommands",
        method="POST",
        json={"ok": True, "result": True},
    )
    cmds = [{"command": "help", "description": "Show help"}]
    async with TelegramClient("TOKEN") as tg:
        res = await tg.set_my_commands(cmds)
    assert res == {"ok": True, "result": True}
    req = httpx_mock.get_requests()[0]
    assert req.method == "POST"
    data = json.loads(req.read().decode())
    assert data == {"commands": cmds}


async def test_set_my_commands_with_scope(httpx_mock: HTTPXMock) -> None:
    import json
    httpx_mock.add_response(
        url="https://api.telegram.org/botTOKEN/setMyCommands",
        method="POST",
        json={"ok": True, "result": True},
    )
    cmds = [{"command": "start", "description": "Start bot"}]
    scope = {"type": "default"}
    async with TelegramClient("TOKEN") as tg:
        res = await tg.set_my_commands(cmds, scope=scope)
    assert res == {"ok": True, "result": True}
    req = httpx_mock.get_requests()[0]
    assert req.method == "POST"
    data = json.loads(req.read().decode())
    assert data == {"commands": cmds, "scope": scope}


async def test_send_message_uses_html_mode_when_html_tags_present(httpx_mock: HTTPXMock) -> None:
    import json
    httpx_mock.add_response(
        url="https://api.telegram.org/botTOKEN/sendMessage",
        method="POST",
        json={"ok": True, "result": {"message_id": 123}},
    )
    async with TelegramClient("TOKEN") as tg:
        await tg.send_message(chat_id=10, text="<b>Bold</b> and <i>italic</i>")
    req = httpx_mock.get_requests()[0]
    data = json.loads(req.read().decode())
    assert data["parse_mode"] == "HTML"
    assert data["text"] == "<b>Bold</b> and <i>italic</i>"


async def test_send_document_posts_multipart(httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    doc_path = tmp_path / "sample.pdf"
    doc_path.write_bytes(b"%PDF-1.4 sample content")

    httpx_mock.add_response(
        url="https://api.telegram.org/botTOKEN/sendDocument",
        method="POST",
        json={"ok": True, "result": {"message_id": 999}},
    )
    async with TelegramClient("TOKEN") as tg:
        mid = await tg.send_document(chat_id=42, file_path=doc_path, caption="Here is sample.pdf")
    assert mid == 999
    req = httpx_mock.get_requests()[0]
    assert req.method == "POST"
    assert b"sample.pdf" in req.read()


async def test_send_document_file_not_found() -> None:
    async with TelegramClient("TOKEN") as tg:
        with pytest.raises(FileNotFoundError):
            await tg.send_document(chat_id=42, file_path="/nonexistent/sample.pdf")



async def test_send_message_parse_error_falls_back_to_plain_text(httpx_mock: HTTPXMock) -> None:
    import json
    httpx_mock.add_response(
        url="https://api.telegram.org/botTOKEN/sendMessage",
        method="POST",
        json={"ok": False, "description": "Bad Request: can't parse entities: unexpected end tag"},
        status_code=400,
    )
    httpx_mock.add_response(
        url="https://api.telegram.org/botTOKEN/sendMessage",
        method="POST",
        json={"ok": True, "result": {"message_id": 7}},
    )
    async with TelegramClient("TOKEN") as tg:
        mid = await tg.send_message(chat_id=10, text="**Halo** & `x<y`")
    assert mid == 7
    retry = json.loads(httpx_mock.get_requests()[1].read().decode())
    assert "parse_mode" not in retry
    assert retry["text"] == "Halo & x<y"


async def test_edit_message_parse_error_falls_back_to_plain_text(httpx_mock: HTTPXMock) -> None:
    import json
    httpx_mock.add_response(
        url="https://api.telegram.org/botTOKEN/editMessageText",
        method="POST",
        json={"ok": False, "description": "Bad Request: can't parse entities"},
        status_code=400,
    )
    httpx_mock.add_response(
        url="https://api.telegram.org/botTOKEN/editMessageText",
        method="POST",
        json={"ok": True, "result": {}},
    )
    async with TelegramClient("TOKEN") as tg:
        await tg.edit_message_text(10, 5, "**Halo**")
    retry = json.loads(httpx_mock.get_requests()[1].read().decode())
    assert "parse_mode" not in retry
    assert retry["text"] == "Halo"


async def test_edit_message_too_long_edits_first_chunk_and_sends_rest(httpx_mock: HTTPXMock) -> None:
    import json
    httpx_mock.add_response(
        url="https://api.telegram.org/botTOKEN/editMessageText",
        method="POST",
        json={"ok": True, "result": {}},
    )
    httpx_mock.add_response(
        url="https://api.telegram.org/botTOKEN/sendMessage",
        method="POST",
        json={"ok": True, "result": {"message_id": 8}},
    )
    body = ("baris panjang\n" * 400).strip()  # ~5600 chars
    async with TelegramClient("TOKEN") as tg:
        await tg.edit_message_text(10, 5, body)
    reqs = httpx_mock.get_requests()
    assert [r.url.path.rsplit("/", 1)[-1] for r in reqs] == ["editMessageText", "sendMessage"]
    for r in reqs:
        assert len(json.loads(r.read().decode())["text"]) <= 4096
