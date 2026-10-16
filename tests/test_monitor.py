"""Unit tests for src.monitor — real-time activity tracking & monitoring."""
from __future__ import annotations

import asyncio
from typing import Any
import pytest

from src.monitor import TurnMonitor, format_tool_action, _clean_path


class _MockTelegram:
    def __init__(self) -> None:
        self.edits: list[tuple[int, int, str]] = []

    async def edit_message_text(
        self, chat_id: int, message_id: int, text: str, *, parse_mode: str = "HTML"
    ) -> None:
        self.edits.append((chat_id, message_id, text))


def test_clean_path() -> None:
    assert _clean_path("") == ""
    assert _clean_path("/etc/os-release") == "/etc/os-release"
    assert _clean_path("/home/user/chat/sub/file.txt", chat_dir="/home/user/chat") == "sub/file.txt"


def test_format_tool_action() -> None:
    # write_to_file
    icon, act = format_tool_action("write_to_file", {"TargetFile": "/tmp/test.txt"})
    assert icon == "✍️"
    assert "test.txt" in act

    # replace_file_content
    icon, act = format_tool_action("replace_file_content", {"TargetFile": "/tmp/test.py"})
    assert icon == "📝"
    assert "test.py" in act

    # view_file
    icon, act = format_tool_action("view_file", {"AbsolutePath": "/etc/hosts"})
    assert icon == "📖"
    assert "/etc/hosts" in act

    # run_command
    icon, act = format_tool_action("run_command", {"CommandLine": "octave script.m"})
    assert icon == "⚡"
    assert "octave script.m" in act

    # call_mcp_tool - octave
    icon, act = format_tool_action("call_mcp_tool", {"ServerName": "gnu-octave", "ToolName": "execute_octave"})
    assert icon == "🔢"
    assert "Octave" in act

    # call_mcp_tool - custom
    icon, act = format_tool_action("call_mcp_tool", {"ServerName": "n8n", "ToolName": "trigger_workflow"})
    assert icon == "🔌"
    assert "n8n" in act

    # search_web
    icon, act = format_tool_action("search_web", {"query": "python asyncio"})
    assert icon == "🌐"
    assert "python asyncio" in act

    # list_dir
    icon, act = format_tool_action("list_dir", {"DirectoryPath": "/tmp"})
    assert icon == "📁"

    # grep_search
    icon, act = format_tool_action("grep_search", {"query": "def main"})
    assert icon == "🔎"


@pytest.mark.asyncio
async def test_turn_monitor_lifecycle() -> None:
    tg = _MockTelegram()
    monitor = TurnMonitor(tg, chat_id=123, message_id=456, chat_dir="/tmp")

    assert monitor.has_tools() is False

    # Simulate tool start
    monitor.on_stream_event({
        "event": "step_update",
        "step_update": {
            "step_index": 1,
            "step_type": "tool",
            "tool_name": "view_file",
            "state": "ACTIVE",
            "tool_info": {"parameters": {"AbsolutePath": "/tmp/input.docx"}},
        },
    })
    assert monitor.has_tools() is True
    assert len(monitor.steps) == 1
    assert monitor.steps[0].status == "active"

    # Simulate tool done
    monitor.on_stream_event({
        "event": "step_update",
        "step_update": {
            "step_index": 1,
            "step_type": "tool",
            "tool_name": "view_file",
            "state": "DONE",
            "duration_seconds": 0.25,
            "tool_info": {"parameters": {"AbsolutePath": "/tmp/input.docx"}},
        },
    })
    assert monitor.steps[0].status == "done"
    assert monitor.steps[0].duration == 0.25

    # Check live rendering
    live_text = monitor.render_live()
    assert "Antigravity sedang bekerja" in live_text
    assert "input.docx" in live_text
    assert "/stop" in live_text

    # Finalize
    await monitor.finish(success=True)
    assert len(tg.edits) > 0
    final_text = tg.edits[-1][2]
    assert "Pekerjaan Selesai" in final_text
    assert "input.docx" in final_text
    assert "/stop" not in final_text  # Clean summary without stop hint


@pytest.mark.asyncio
async def test_turn_monitor_no_tools_finish() -> None:
    tg = _MockTelegram()
    monitor = TurnMonitor(tg, chat_id=123, message_id=456, chat_dir="/tmp")

    # Only thinking, no tools
    monitor.on_stream_event({
        "event": "step_update",
        "step_update": {
            "step_index": 1,
            "step_type": "agent_response",
            "state": "ACTIVE",
        },
    })
    assert monitor.has_tools() is False

    # finish should not edit message when there are no tools
    await monitor.finish(success=True)
    assert len(tg.edits) == 0
