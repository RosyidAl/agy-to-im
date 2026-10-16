"""Tests for the pure helpers in src.telegram."""
from __future__ import annotations

import pytest

from src.config import TelegramConfig
from src.telegram import InboundMessage, chunk_message, is_authorized, parse_update


# --- parse_update ----------------------------------------------------

def _msg(text: str = "hi", user_id: int = 99999999, chat_id: int = 99999999) -> dict:
    return {
        "update_id": 100,
        "message": {
            "message_id": 1,
            "date": 0,
            "chat": {"id": chat_id, "type": "private"},
            "from": {"id": user_id, "is_bot": False, "first_name": "Test"},
            "text": text,
        },
    }


def test_parse_update_extracts_text() -> None:
    msg = parse_update(_msg(text="hello kimi"))
    assert msg == InboundMessage(
        update_id=100, chat_id=99999999, user_id=99999999, text="hello kimi"
    )


def test_parse_update_returns_none_when_no_message() -> None:
    assert parse_update({"update_id": 100}) is None


def test_parse_update_returns_message_for_photo() -> None:
    upd = _msg()
    del upd["message"]["text"]
    upd["message"]["photo"] = [{"file_id": "abc"}]
    result = parse_update(upd)
    assert result is not None
    assert result.photo == [{"file_id": "abc"}]


def test_parse_update_returns_none_for_edited_message() -> None:
    upd = _msg()
    upd["edited_message"] = upd.pop("message")
    assert parse_update(upd) is None


# --- is_authorized ---------------------------------------------------

def _cfg(user_ids: list[int], chat_ids: list[int] | None = None) -> TelegramConfig:
    return TelegramConfig(
        bot_token="x",
        allowed_user_ids=user_ids,
        allowed_chat_ids=chat_ids or [],
    )


def test_is_authorized_allows_listed_user() -> None:
    msg = InboundMessage(update_id=1, chat_id=10, user_id=42, text="hi")
    assert is_authorized(msg, _cfg([42])) is True


def test_is_authorized_blocks_unlisted_user() -> None:
    msg = InboundMessage(update_id=1, chat_id=10, user_id=999, text="hi")
    assert is_authorized(msg, _cfg([42])) is False


def test_is_authorized_with_chat_whitelist_blocks_other_chats() -> None:
    msg = InboundMessage(update_id=1, chat_id=20, user_id=42, text="hi")
    assert is_authorized(msg, _cfg([42], chat_ids=[10])) is False


def test_is_authorized_with_chat_whitelist_allows_listed_chat() -> None:
    msg = InboundMessage(update_id=1, chat_id=10, user_id=42, text="hi")
    assert is_authorized(msg, _cfg([42], chat_ids=[10])) is True


# --- chunk_message ---------------------------------------------------

def test_chunk_short_message_returned_as_single_chunk() -> None:
    assert chunk_message("hello", max_len=4096) == ["hello"]


def test_chunk_empty_message_returned_as_empty_list() -> None:
    assert chunk_message("", max_len=4096) == []


def test_chunk_long_message_splits_on_newlines() -> None:
    body = ("line\n" * 1000).rstrip("\n")
    chunks = chunk_message(body, max_len=100)
    assert all(len(c) <= 100 for c in chunks)
    assert "".join(c if c.endswith("\n") else c + "\n" for c in chunks).rstrip("\n") == body


def test_chunk_long_unbroken_text_hard_splits() -> None:
    body = "a" * 9000
    chunks = chunk_message(body, max_len=4096)
    assert all(len(c) <= 4096 for c in chunks)
    assert "".join(chunks) == body


def test_chunk_default_max_is_4096() -> None:
    body = "x" * 5000
    chunks = chunk_message(body)
    assert all(len(c) <= 4096 for c in chunks)


def test_detect_parse_mode() -> None:
    from src.telegram import detect_parse_mode

    assert detect_parse_mode("Hello world") == "Markdown"
    assert detect_parse_mode("<b>Hello</b> world") == "HTML"
    assert detect_parse_mode("<blockquote>quote</blockquote>") == "HTML"
    assert detect_parse_mode("<pre><code class=\"language-python\">x=1</code></pre>") == "HTML"
    assert detect_parse_mode("<i>italic</i> and <u>underline</u>") == "HTML"
    assert detect_parse_mode("<tg-spoiler>secret</tg-spoiler>") == "HTML"


def test_markdown_to_telegram_html_formatting() -> None:
    from src.telegram import markdown_to_telegram_html

    sample = (
        "### **Title Header**\n"
        "Document **Format_Laprak_2.docx** contains `sum = 0`.\n"
        "* **Mata Kuliah:** Metode Numerik\n"
        "* Item 2: *italic word*\n"
        "```python\ndef run():\n    return 42\n```\n"
        "> Quote here\n"
        "[Link](https://example.com)\n"
        "---"
    )
    html_out = markdown_to_telegram_html(sample)
    assert "<b>Title Header</b>" in html_out
    assert "<b>Format_Laprak_2.docx</b>" in html_out
    assert "<code>sum = 0</code>" in html_out
    assert "<b>Mata Kuliah:</b>" in html_out
    assert "<i>italic word</i>" in html_out
    assert '<pre><code class="language-python">def run():\n    return 42</code></pre>' in html_out
    assert "<blockquote>Quote here</blockquote>" in html_out
    assert '<a href="https://example.com">Link</a>' in html_out
    assert "────────────────" in html_out


def test_balance_html_chunks() -> None:
    from src.telegram import balance_html_chunks

    chunks = ["<b>Hello world ", "this is continuing</b>"]
    balanced = balance_html_chunks(chunks)
    assert balanced[0] == "<b>Hello world </b>"
    assert balanced[1] == "<b>this is continuing</b>"

