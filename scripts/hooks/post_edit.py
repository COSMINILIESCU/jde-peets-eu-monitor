"""Claude Code PostToolUse hook: auto-lint (ruff --fix) any edited Python file."""

import json
import subprocess
import sys


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    path = (payload.get("tool_input") or {}).get("file_path", "")
    if path.endswith(".py"):
        subprocess.run([sys.executable, "-m", "ruff", "check", "--fix", "--quiet", path],
                       capture_output=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
