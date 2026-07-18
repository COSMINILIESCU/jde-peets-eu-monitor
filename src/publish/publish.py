"""Publish the dashboard: commit docs/ changes and push to GitHub."""

import logging
import subprocess

from src.common.config import ROOT, settings

log = logging.getLogger("publish")


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")


def publish(message: str) -> bool:
    """Commit docs/ + registry and push. Returns True if something was published."""
    cfg = settings()["publishing"]
    _git("add", "docs", "sources")
    diff = _git("diff", "--cached", "--quiet")
    if diff.returncode == 0:
        log.info("nothing new to publish")
        return False
    commit = _git("commit", "-m", message)
    if commit.returncode != 0:
        raise RuntimeError(f"git commit failed: {commit.stderr[:300]}")
    push = _git("push", cfg["git_remote"], cfg["git_branch"])
    if push.returncode != 0:
        raise RuntimeError(f"git push failed: {push.stderr[:300]}")
    log.info("published to %s/%s", cfg["git_remote"], cfg["git_branch"])
    return True
