"""Monthly source scout runner (scheduled every Monday 08:00; exits unless first Monday).

Usage: python scripts/run_monthly_scout.py [--force]
"""

import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.common import db  # noqa: E402
from src.common.config import ROOT  # noqa: E402
from src.common.headless import run_agent  # noqa: E402

PROMPT = (
    "Invoke the monthly-source-scout subagent to perform this month's source-registry "
    "maintenance for the JDE Peet's EU/EEA monitor, following its instructions exactly. "
    "Then report its summary."
)


def is_first_monday(now: datetime) -> bool:
    return now.weekday() == 0 and now.day <= 7


def main() -> int:
    force = "--force" in sys.argv
    now = datetime.now(UTC)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    log = logging.getLogger("scout")
    if not force and not is_first_monday(now):
        log.info("not the first Monday of the month - exiting (use --force to override)")
        return 0
    conn = db.connect()
    db.audit(conn, "scout", "scout_start")
    ok, output = run_agent(PROMPT, "WebSearch,WebFetch,Read,Edit,Grep,Glob", timeout=5400)
    stamp = now.strftime("%Y%m%d_%H%M")
    logfile = ROOT / "logs" / f"scout_{stamp}.log"
    logfile.parent.mkdir(exist_ok=True)
    logfile.write_text(output, encoding="utf-8")
    db.audit(conn, "scout", "scout_finish", "ok" if ok else f"failed: {output[:200]}")
    conn.close()
    log.info("scout %s - output: %s", "finished" if ok else "FAILED", logfile)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
