"""Invoke Claude Code headless with a project subagent (scout / specialist)."""

import logging
import subprocess

from src.common.config import ROOT, settings

log = logging.getLogger("headless")


def run_agent(prompt: str, allowed_tools: str, timeout: int = 3600,
              model: str = "", effort: str = "") -> tuple[bool, str]:
    """Run `claude -p` in the project root so .claude/agents/ are available.

    Returns (ok, output_text)."""
    cmd = [
        settings()["analysis"].get("claude_cmd", "claude"), "-p",
        "--permission-mode", "acceptEdits",
        "--allowedTools", allowed_tools,
    ]
    if model:
        cmd += ["--model", model]
    if effort:
        cmd += ["--effort", effort]
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                              encoding="utf-8", timeout=timeout, cwd=ROOT, shell=False)
    except FileNotFoundError:
        return False, "Claude Code CLI not found"
    except subprocess.TimeoutExpired:
        return False, f"timed out after {timeout}s"
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout)[:1000]
    return True, proc.stdout
