"""Unit tests for src.commands — bridge command handlers."""
from __future__ import annotations

from src.commands import handle_callback, handle_text_command
from src.config import AgyConfig, Config, TelegramConfig
from src.state import ChatState
from src.telegram import CallbackQuery


def _cfg(model: str = "", mode: str = "code") -> Config:
    return Config(
        telegram=TelegramConfig(bot_token="t", allowed_user_ids=[42]),
        agy=AgyConfig(default_workdir="/tmp", model=model, mode=mode),
    )


def _state() -> ChatState:
    return ChatState(chat_dir="/tmp/chat")


class _FakeMsg:
    def __init__(self, text: str, chat_id: int = 42, user_id: int = 42) -> None:
        self.text = text
        self.chat_id = chat_id
        self.user_id = user_id


async def test_start_command() -> None:
    reply = await handle_text_command(_FakeMsg("/start"), _state(), _cfg())
    assert reply is not None
    assert "Welcome" in reply.text


async def test_help_command() -> None:
    reply = await handle_text_command(_FakeMsg("/help"), _state(), _cfg())
    assert reply is not None
    assert "Commands" in reply.text


async def test_info_shows_default_model() -> None:
    reply = await handle_text_command(_FakeMsg("/info"), _state(), _cfg(model="gemini-2.5-pro"))
    assert reply is not None
    assert "gemini-2.5-pro" in reply.text


async def test_info_no_session() -> None:
    reply = await handle_text_command(_FakeMsg("/info"), _state(), _cfg())
    assert reply is not None
    assert "fresh" in reply.text.lower()


async def test_thinking_not_available() -> None:
    reply = await handle_text_command(_FakeMsg("/thinking on"), _state(), _cfg())
    assert reply is not None
    assert "not available" in reply.text.lower()


async def test_model_picker() -> None:
    reply = await handle_text_command(_FakeMsg("/model"), _state(), _cfg(model="gemini-2.5-pro"))
    assert reply is not None
    assert reply.keyboard is not None


async def test_model_set() -> None:
    cs = _state()
    reply = await handle_text_command(_FakeMsg("/model gemini-2.5-pro"), cs, _cfg())
    assert reply is not None
    assert cs.model == "gemini-2.5-pro"


async def test_reset_clears_session() -> None:
    cs = _state()
    cs.has_session = True
    reply = await handle_text_command(_FakeMsg("/reset"), cs, _cfg())
    assert reply is not None
    assert cs.has_session is False


async def test_unknown_returns_none() -> None:
    reply = await handle_text_command(_FakeMsg("hello world"), _state(), _cfg())
    assert reply is None


async def test_callback_nav_settings() -> None:
    cq = CallbackQuery(update_id=1, callback_query_id="q", chat_id=42, user_id=42, message_id=1, data="nav:settings")
    reply = handle_callback(cq, _state(), _cfg())
    assert reply.keyboard is not None


async def test_callback_model_choice() -> None:
    cs = _state()
    cq = CallbackQuery(update_id=1, callback_query_id="q", chat_id=42, user_id=42, message_id=1, data="m:gemini-2.5-pro")
    reply = handle_callback(cq, cs, _cfg())
    assert cs.model == "gemini-2.5-pro"
    assert "gemini-2.5-pro" in reply.toast


async def test_callback_reset() -> None:
    cs = _state()
    cs.has_session = True
    cq = CallbackQuery(update_id=1, callback_query_id="q", chat_id=42, user_id=42, message_id=1, data="R")
    reply = handle_callback(cq, cs, _cfg())
    assert cs.has_session is False
    assert "reset" in reply.toast.lower()


async def test_callback_mode_choice() -> None:
    cs = _state()
    cq = CallbackQuery(update_id=1, callback_query_id="q", chat_id=42, user_id=42, message_id=1, data="M:plan")
    reply = handle_callback(cq, cs, _cfg())
    assert cs.mode == "plan"
    assert "plan" in reply.toast.lower()


async def test_pwd_command() -> None:
    cs = _state()
    reply = await handle_text_command(_FakeMsg("/pwd"), cs, _cfg())
    assert reply is not None
    assert "/tmp/chat" in reply.text


async def test_cd_valid_dir(tmp_path: Path) -> None:
    cs = _state()
    cs.has_session = True
    target = tmp_path / "my_project"
    target.mkdir()
    reply = await handle_text_command(_FakeMsg(f"/cd {target}"), cs, _cfg())
    assert reply is not None
    assert "Switched working directory" in reply.text
    assert cs.chat_dir == str(target.resolve())
    assert cs.has_session is False


async def test_cd_invalid_dir() -> None:
    cs = _state()
    reply = await handle_text_command(_FakeMsg("/cd /nonexistent/dir/xyz"), cs, _cfg())
    assert reply is not None
    assert "not found" in reply.text.lower()


async def test_cd_default_fallback(tmp_path: Path) -> None:
    cs = _state()
    default_dir = tmp_path / "default_dir"
    default_dir.mkdir()
    cfg = Config(
        telegram=TelegramConfig(bot_token="t", allowed_user_ids=[42]),
        agy=AgyConfig(default_workdir=str(default_dir)),
    )
    reply = await handle_text_command(_FakeMsg("/cd"), cs, cfg)
    assert reply is not None
    assert "Switched working directory" in reply.text
    assert cs.chat_dir == str(default_dir.resolve())


async def test_effort_command() -> None:
    cs = _state()
    reply = await handle_text_command(_FakeMsg("/effort"), cs, _cfg())
    assert reply is not None
    assert "effort" in reply.text.lower()

    reply = await handle_text_command(_FakeMsg("/effort high"), cs, _cfg())
    assert reply is not None
    assert "high" in reply.text
    assert cs.effort == "high"

    reply = await handle_text_command(_FakeMsg("/effort invalid"), cs, _cfg())
    assert reply is not None
    assert "unsupported" in reply.text.lower()


async def test_callback_effort_choice() -> None:
    cs = _state()
    cq = CallbackQuery(update_id=1, callback_query_id="q", chat_id=42, user_id=42, message_id=1, data="e:medium")
    reply = handle_callback(cq, cs, _cfg())
    assert cs.effort == "medium"
    assert "medium" in reply.toast.lower()

    cq_reset = CallbackQuery(update_id=2, callback_query_id="q", chat_id=42, user_id=42, message_id=1, data="e:_DEFAULT")
    reply_reset = handle_callback(cq_reset, cs, _cfg())
    assert cs.effort == ""
    assert "default" in reply_reset.toast.lower()


async def test_stop_command() -> None:
    cs = _state()
    reply = await handle_text_command(_FakeMsg("/stop"), cs, _cfg())
    assert reply is not None
    assert "no active agy process" in reply.text.lower()


