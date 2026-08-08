"""Catch-up guard: if no weekly run finished successfully in the last N days, run one now.

Registered to run shortly after logon, so an interrupted or missed Monday run
(PC off, laptop unplugged, session closed mid-run) is recovered automatically.
The pipeline itself is idempotent: already-collected items keep their state and
are picked up where they were left.

Usage:
    python scripts/catchup.py            # run the weekly pipeline if the last one is stale
    python scripts/catchup.py --status   # only report, never launch
    python scripts/catchup.py --days 6   # staleness threshold (default 6)
"""

import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.common import db  # noqa: E402

STALE_DAYS_DEFAULT = 6


def last_successful_run(conn) -> tuple[datetime | None, str]:
    """Most recent weekly run that finished and actually published/exported."""
    rows = conn.execute(
        "SELECT finished_at, stats_json FROM runs "
        "WHERE kind='weekly' AND finished_at IS NOT NULL ORDER BY id DESC LIMIT 20"
    ).fetchall()
    for r in rows:
        try:
            stats = json.loads(r["stats_json"] or "{}")
        except json.JSONDecodeError:
            continue
        if stats.get("status", "").startswith("ok"):
            return datetime.fromisoformat(r["finished_at"]), stats.get("status", "ok")
    return None, "none found"


def main() -> int:
    args = sys.argv[1:]
    status_only = "--status" in args
    days = STALE_DAYS_DEFAULT
    if "--days" in args:
        days = int(args[args.index("--days") + 1])

    conn = db.connect()
    last, status = last_successful_run(conn)
    conn.close()

    now = datetime.now(UTC)
    if last is None:
        age_txt, stale = "never", True
    else:
        age = now - last
        age_txt = f"{age.days}d {age.seconds // 3600}h ago ({last:%Y-%m-%d %H:%M} UTC, {status})"
        stale = age > timedelta(days=days)

    print(f"last successful weekly run: {age_txt}")
    print(f"threshold: {days} days -> {'STALE, catching up' if stale else 'fresh, nothing to do'}")
    if status_only or not stale:
        return 0

    cmd = [sys.executable, str(ROOT / "scripts" / "run_weekly.py")]
    print("launching:", " ".join(cmd))
    return subprocess.run(cmd, cwd=ROOT).returncode


if __name__ == "__main__":
    sys.exit(main())
