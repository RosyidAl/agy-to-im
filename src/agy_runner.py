"""Spawn the Antigravity CLI (`agy`) and capture its plain-text output.

agy print mode uses Go-style flags:
  agy -p "<prompt>" [--model <id>] [--continue | --new-project]
      [--dangerously-skip-permissions] [--sandbox]
      [--print-timeout <duration>]

Output is plain text/markdown on stdout; there is no stream-json mode.
"""
from __future__ import annotations

import asyncio
import gc
import os
import subprocess
from dataclasses import dataclass

# Safety cap on stdout capture — prevents unbounded memory growth from
# runaway agy output. 1MB is generous (typical replies are 1–5KB).
_STDOUT_CAP_BYTES = 524_288  # 512 KiB

# Reap any defunct child processes left by prior subprocess invocations
# (bwrap sandbox can leave orphaned grand-children).
def _reap_zombies() -> None:
    try:
        while True:
            pid, _status = os.waitpid(-1, os.WNOHANG)
            if pid == 0:
                break
    except (ChildProcessError, OSError):
        pass


@dataclass(frozen=True)
class AgyResult:
    text: str
    exit_code: int
    stderr: str


_ACTIVE_PROC: dict[str, subprocess.Popen] = {}


def abort_turn(chat_dir: str) -> bool:
    """Abort an actively running agy process in chat_dir."""
    proc = _ACTIVE_PROC.get(chat_dir)
    if proc is not None:
        try:
            proc.kill()
            return True
        except Exception:
            pass
    return False


def _build_args(
    *,
    agy_path: str,
    prompt: str,
    has_session: bool,
    model: str,
    mode: str,
    print_timeout: str,
    chat_dir: str = "",
    effort: str = "",
) -> list[str]:
    import shutil
    resolved_agy = shutil.which(agy_path) or agy_path
    args = [resolved_agy, "-p", prompt]

    if has_session:
        args.append("--continue")
    else:
        args.append("--new-project")

    if effort:
        if model:
            args.extend(["--model", model])
        args.extend(["--effort", effort])
    elif model:
        # If model is a base model without explicit effort suffix, supply --effort high
        if any(model.startswith(prefix) for prefix in ("gemini-3.8", "gemini-3.7", "gemini-3.6", "gemini-3.5", "gemini-3.1")) and not any(model.endswith(sfx) for sfx in ("-low", "-medium", "-high")):
            args.extend(["--model", model, "--effort", "high"])
        else:
            args.extend(["--model", model])

    args.append("--dangerously-skip-permissions")

    if mode == "plan":
        args.extend(["--mode", "plan", "--sandbox"])
    elif mode == "code":
        args.extend(["--mode", "accept-edits"])

    args.extend(["--print-timeout", print_timeout])
    return args


def _run_sync(
    args: list[str],
    cwd: str,
    timeout: float | None = None,
) -> AgyResult:
    """Synchronous worker for subprocess invocation. Called via asyncio.to_thread."""
    _reap_zombies()
    proc = None
    try:
        proc = subprocess.Popen(
            args,
            cwd=cwd,
            env=os.environ.copy(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        _ACTIVE_PROC[cwd] = proc
        stdout_bytes, stderr_bytes = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        if proc:
            proc.kill()
            stdout_bytes, stderr_bytes = proc.communicate()
        else:
            stdout_bytes, stderr_bytes = b"", b""
        message = f"agy timed out after {timeout}s"
        partial_stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
        stderr = f"{partial_stderr}\n{message}".strip() if partial_stderr else message
        gc.collect()
        return AgyResult(text="", exit_code=124, stderr=stderr)
    except Exception as exc:
        gc.collect()
        return AgyResult(text="", exit_code=1, stderr=str(exc))
    finally:
        _ACTIVE_PROC.pop(cwd, None)

    exit_code = proc.returncode if proc else 0
    if exit_code in (-9, -15, 137, 143):
        gc.collect()
        return AgyResult(text="🛑 agy execution was aborted.", exit_code=exit_code, stderr="Aborted")

    stdout = stdout_bytes
    # Cap at safety limit; mark truncation if hit
    truncated = False
    if len(stdout) > _STDOUT_CAP_BYTES:
        stdout = stdout[:_STDOUT_CAP_BYTES]
        truncated = True

    text = stdout.decode("utf-8", errors="replace")
    if truncated:
        text += "\n\n[output truncated at 1MiB]"

    stderr_out = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
    gc.collect()
    return AgyResult(
        text=text,
        exit_code=exit_code,
        stderr=stderr_out,
    )


async def run_agy(
    prompt: str,
    *,
    chat_dir: str,
    has_session: bool,
    model: str,
    mode: str,
    agy_path: str,
    effort: str = "",
    timeout: float | None = None,
    print_timeout: str = "15m",
) -> AgyResult:
    """Run agy in print mode. Returns when the turn ends."""
    args = _build_args(
        agy_path=agy_path,
        prompt=prompt,
        has_session=has_session,
        model=model,
        mode=mode,
        effort=effort,
        print_timeout=print_timeout,
        chat_dir=chat_dir,
    )
    return await asyncio.to_thread(_run_sync, args, chat_dir, timeout)
