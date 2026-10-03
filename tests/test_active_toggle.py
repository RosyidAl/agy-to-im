"""Tests for per-chat active/inactive toggle feature."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from src.commands import handle_callback, handle_text_command
from src.config import AgyConfig, Config, TelegramConfig
from src.state import ChatState, State, load_state, save_state
from src.telegram import CallbackQuery


pytestmark = pytest.mark.asyncio


def _cfg() -> Config:
    return Config(
        telegram=TelegramConfig(bot_token="TOKEN", allowed_user_ids=[42]),
        agy=AgyConfig(default_workdir="/tmp", model="", mode="code"),
    )


def _state(chat_dir: str = "/tmp/chat") -> ChatState:
    return ChatState(chat_dir=chat_dir)


class _FakeMsg:
    def __init__(self, text: str, chat_id: int = 42, user_id: int = 42) -> None:
        self.text = text
        self.chat_id = chat_id
        self.user_id = user_id


# --- Command Tests ---


async def test_off_command_deactivates() -> None:
    cs = _state()
    assert cs.active is True
    reply = await handle_text_command(_FakeMsg("/off"), cs, _cfg())
    assert reply is not None
    assert cs.active is False
    assert "mati" in reply.text.lower() or "mengabaikan" in reply.text.lower()


async def test_on_command_activates() -> None:
    cs = _state()
    cs.active = False
    reply = await handle_text_command(_FakeMsg("/on"), cs, _cfg())
    assert reply is not None
    assert cs.active is True
    assert "aktif" in reply.text.lower() or "diaktifkan" in reply.text.lower()


async def test_commands_still_work_when_inactive() -> None:
    """Slash commands should always work even when bot is inactive."""
    cs = _state()
    cs.active = False

    # /status should still respond
    reply = await handle_text_command(_FakeMsg("/status"), cs, _cfg())
    assert reply is not None
    assert "Inactive" in reply.text or "mati" in reply.text.lower()

    # /help should still respond
    reply = await handle_text_command(_FakeMsg("/help"), cs, _cfg())
    assert reply is not None
    assert "Commands" in reply.text

    # /on should reactivate
    reply = await handle_text_command(_FakeMsg("/on"), cs, _cfg())
    assert reply is not None
    assert cs.active is True


async def test_non_command_returns_none_regardless_of_active() -> None:
    """Non-command text returns None (handled by daemon, not commands module)."""
    cs = _state()
    cs.active = False
    reply = await handle_text_command(_FakeMsg("hello world"), cs, _cfg())
    assert reply is None  # daemon is responsible for the active check


# --- Callback Tests ---


async def test_callback_power_toggle_deactivates() -> None:
    cs = _state()
    assert cs.active is True
    cq = CallbackQuery(
        update_id=1, callback_query_id="q", chat_id=42,
        user_id=42, message_id=1, data="power:toggle",
    )
    reply = handle_callback(cq, cs, _cfg())
    assert cs.active is False
    assert "mati" in reply.toast.lower()
    assert reply.keyboard is not None


async def test_callback_power_toggle_activates() -> None:
    cs = _state()
    cs.active = False
    cq = CallbackQuery(
        update_id=1, callback_query_id="q", chat_id=42,
        user_id=42, message_id=1, data="power:toggle",
    )
    reply = handle_callback(cq, cs, _cfg())
    assert cs.active is True
    assert "aktif" in reply.toast.lower()


# --- Status Display Tests ---


async def test_status_shows_active_indicator() -> None:
    cs = _state()
    cs.active = True
    reply = await handle_text_command(_FakeMsg("/status"), cs, _cfg())
    assert reply is not None
    assert "🟢" in reply.text
    assert "Active" in reply.text


async def test_status_shows_inactive_indicator() -> None:
    cs = _state()
    cs.active = False
    reply = await handle_text_command(_FakeMsg("/status"), cs, _cfg())
    assert reply is not None
    assert "🔴" in reply.text
    assert "Inactive" in reply.text or "mati" in reply.text.lower()


# --- Settings Keyboard Tests ---


async def test_settings_keyboard_shows_turn_off_when_active() -> None:
    cs = _state()
    cs.active = True
    reply = await handle_text_command(_FakeMsg("/settings"), cs, _cfg())
    assert reply is not None
    assert reply.keyboard is not None
    all_texts = [btn["text"] for row in reply.keyboard for btn in row]
    assert any("Turn Off" in t for t in all_texts)


async def test_settings_keyboard_shows_turn_on_when_inactive() -> None:
    cs = _state()
    cs.active = False
    reply = await handle_text_command(_FakeMsg("/settings"), cs, _cfg())
    assert reply is not None
    assert reply.keyboard is not None
    all_texts = [btn["text"] for row in reply.keyboard for btn in row]
    assert any("Turn On" in t for t in all_texts)


# --- State Persistence Tests ---


def test_active_field_persisted_in_state(tmp_path: Path) -> None:
    p = tmp_path / "state.json"
    chat_dir = str(tmp_path / "chats" / "123")
    cs = ChatState(chat_dir=chat_dir, active=False)
    original = State(last_update_id=10, chats={123: cs})
    save_state(p, original)

    loaded = load_state(p, tmp_path / "chats")
    assert 123 in loaded.chats
    assert loaded.chats[123].active is False


def test_active_defaults_to_true_when_missing(tmp_path: Path) -> None:
    """Old state files without 'active' field should default to True."""
    chat_dir = str(tmp_path / "chats" / "123")
    (tmp_path / "chats" / "123").mkdir(parents=True)
    p = tmp_path / "state.json"
    p.write_text(
        '{"last_update_id": 1, "chats": {'
        '"123": {"chat_dir": "' + chat_dir + '", "has_session": true}'
        '}}'
    )
    state = load_state(p, tmp_path / "chats")
    assert state.chats[123].active is True


# --- Daemon Integration Test ---


async def test_daemon_ignores_messages_when_inactive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When chat is inactive, daemon should NOT forward messages to agy."""
    from dataclasses import dataclass

    from src.agy_runner import AgyResult
    from src.daemon import DaemonInfo, run

    agy_called = []

    async def tracking_agy(tg: Any, chat_id: int, msg: Any, cs: Any, cfg: Any, agy_path: str) -> tuple[str, int]:
        agy_called.append(msg.text)
        return "echo", 0

    monkeypatch.setattr("src.daemon.execute_agy", tracking_agy)

    @dataclass
    class _FakeTelegram:
        updates_to_serve: list[list[dict[str, Any]]]
        sent_messages: list[tuple[int, str]]
        chat_actions: list[tuple[int, str]]

        async def __aenter__(self) -> "_FakeTelegram":
            return self

        async def __aexit__(self, *exc: object) -> None:
            return None

        async def get_updates(self, offset: int, timeout: int = 30) -> list[dict[str, Any]]:
            if self.updates_to_serve:
                return self.updates_to_serve.pop(0)
            await asyncio.sleep(0)
            return []

        async def send_message(self, chat_id: int, text: str, *, keyboard: Any = None) -> int | None:
            self.sent_messages.append((chat_id, text))
            return len(self.sent_messages) - 1

        async def edit_message_text(self, chat_id: int, message_id: int, text: str, *, keyboard: Any = None) -> None:
            pass

        async def answer_callback_query(self, callback_query_id: str, *, text: str = "") -> None:
            return None

        async def send_chat_action(self, chat_id: int, action: str = "typing") -> None:
            self.chat_actions.append((chat_id, action))

        async def set_my_commands(self, commands: list[dict[str, str]], *, scope: Any = None) -> dict[str, Any]:
            return {"ok": True}

        async def send_document(self, chat_id: int, file_path: Any, *, caption: str = "") -> int | None:
            return 1

    # Pre-set the chat state to inactive
    state_path = tmp_path / "state.json"
    chats_root = tmp_path / "chats"
    chat_dir = chats_root / "10"
    chat_dir.mkdir(parents=True)
    cs = ChatState(chat_dir=str(chat_dir), active=False)
    save_state(state_path, State(last_update_id=0, chats={10: cs}))

    def _msg(text: str, update_id: int) -> dict:
        return {
            "update_id": update_id,
            "message": {
                "message_id": update_id,
                "date": 0,
                "chat": {"id": 10, "type": "private"},
                "from": {"id": 42, "is_bot": False, "first_name": "T"},
                "text": text,
            },
        }

    tg = _FakeTelegram(
        updates_to_serve=[
            [_msg("hello world", 100)],    # should be ignored (inactive)
            [_msg("/on", 101)],            # should activate
            [_msg("now respond", 102)],    # should be forwarded to agy
        ],
        sent_messages=[],
        chat_actions=[],
    )

    stop = asyncio.Event()
    asyncio.get_running_loop().call_later(0.6, stop.set)

    cfg = Config(
        telegram=TelegramConfig(bot_token="TOKEN", allowed_user_ids=[42], allowed_chat_ids=[]),
        agy=AgyConfig(default_workdir="/tmp", model="", mode="code"),
    )

    await run(
        cfg=cfg,
        state_path=state_path,
        chats_root=chats_root,
        tg=tg,
        agy_path="/usr/bin/true",
        info=DaemonInfo(bot_username="@bot", started_at=0.0, agy_version="1.0"),
        stop_event=stop,
    )

    # "hello world" should NOT have been forwarded to agy
    assert "hello world" not in agy_called
    # But "now respond" should have been forwarded after /on activated the bot
    assert len(agy_called) >= 1
