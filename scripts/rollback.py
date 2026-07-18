"""Roll back the published dashboard to the state before the last publish commit.

Usage: python scripts/rollback.py            (revert last publish commit)
       python scripts/rollback.py <sha>      (revert a specific commit)

Creates a *new* revert commit (history stays intact) and pushes it.
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.common.config import ROOT, settings  # noqa: E402


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")


def main() -> None:
    target = sys.argv[1] if len(sys.argv) > 1 else None
    if not target:
        log = _git("log", "--oneline", "-15", "--", "docs/data")
        lines = [line for line in log.stdout.splitlines() if line.strip()]
        if not lines:
            print("No publish commits found (docs/data has no history).")
            return
        target = lines[0].split()[0]
        print("Reverting last publish commit:", lines[0])
    revert = _git("revert", "--no-edit", target)
    if revert.returncode != 0:
        print("Revert failed:", revert.stderr[:500])
        print("Resolve manually or run: git revert --abort")
        sys.exit(1)
    cfg = settings()["publishing"]
    push = _git("push", cfg["git_remote"], cfg["git_branch"])
    if push.returncode != 0:
        print("Push failed:", push.stderr[:500])
        sys.exit(1)
    print("Rollback published. The dashboard will refresh in ~1 minute (GitHub Pages).")


if __name__ == "__main__":
    main()
