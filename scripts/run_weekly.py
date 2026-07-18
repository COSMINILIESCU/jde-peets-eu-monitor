"""Weekly pipeline orchestrator.

Usage:
    python scripts/run_weekly.py                 full run (collect -> analyze -> export -> publish)
    python scripts/run_weekly.py --no-publish    everything except git push
    python scripts/run_weekly.py --no-analyze    collection + export only (no AI)
    python scripts/run_weekly.py --sample N      only the first N active sources (testing)
"""

import argparse
import json
import logging
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.analysis.brief import generate_brief  # noqa: E402
from src.analysis.engine import analyze_new_items  # noqa: E402
from src.collectors.collect import collect_all  # noqa: E402
from src.common import db  # noqa: E402
from src.common.config import ROOT, active_sources, settings  # noqa: E402
from src.publish.export_json import export_all  # noqa: E402
from src.publish.publish import publish  # noqa: E402

LOG_DIR = ROOT / "logs"


def setup_logging(stamp: str) -> Path:
    LOG_DIR.mkdir(exist_ok=True)
    logfile = LOG_DIR / f"run_{stamp}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(logfile, encoding="utf-8"),
                  logging.StreamHandler(sys.stdout)],
    )
    return logfile


def backup_db() -> None:
    if not db.DB_PATH.exists():
        return
    backup_dir = ROOT / "data" / "backup"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d")
    shutil.copy2(db.DB_PATH, backup_dir / f"monitor_{stamp}.db")
    keep = settings()["retention"]["backup_keep_last"]
    backups = sorted(backup_dir.glob("monitor_*.db"))
    for old in backups[:-keep]:
        old.unlink()


def write_report(stamp: str, report: dict) -> Path:
    path = LOG_DIR / f"report_{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-publish", action="store_true")
    parser.add_argument("--no-analyze", action="store_true")
    parser.add_argument("--sample", type=int, default=0)
    parser.add_argument("--since", default="", help="only keep items published on/after YYYY-MM-DD")
    parser.add_argument("--max-items", type=int, default=0, help="override max items per source")
    args = parser.parse_args()

    since = None
    if args.since:
        since = datetime.fromisoformat(args.since).replace(tzinfo=UTC)
    if args.max_items:
        settings()["collection"]["max_items_per_source_per_run"] = args.max_items

    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M")
    logfile = setup_logging(stamp)
    log = logging.getLogger("weekly")
    log.info("=== weekly run start (log: %s) ===", logfile)

    backup_db()
    conn = db.connect()
    run_id = db.start_run(conn, "weekly")
    db.audit(conn, "pipeline", "run_start", f"run_id={run_id}")
    report: dict = {"run_id": run_id, "started_at": db.now_iso()}

    try:
        sources = active_sources()
        if args.sample:
            sources = sources[:args.sample]
        log.info("collecting %d active sources%s", len(sources),
                 f" (since {args.since})" if since else "")
        collect_stats = collect_all(conn, sources, run_id, since=since)
        failed = [s for s in collect_stats if s["status"] != "ok"]
        report["collection"] = {
            "sources_total": len(sources),
            "sources_failed": len(failed),
            "new_items": sum(s["new"] for s in collect_stats),
            "duplicates": sum(s["duplicates"] for s in collect_stats),
            "skipped_old": sum(s.get("skipped_old", 0) for s in collect_stats),
            "since": args.since or None,
            "failed_sources": [{"id": s["source_id"], "status": s["status"], "error": s["error"]}
                               for s in failed],
        }
        log.info("collection done: %s new, %s failed sources",
                 report["collection"]["new_items"], len(failed))

        if not args.no_analyze:
            report["analysis"] = analyze_new_items(conn, run_id)
            log.info("analysis done: %s", report["analysis"])
            brief = generate_brief(conn)
            report["brief_generated"] = brief is not None
        else:
            brief = None
            report["analysis"] = {"skipped": True}

        export_stats = export_all(conn, run_stats=report, brief=brief)
        report["export"] = export_stats
        log.info("export done: %s", export_stats)

        published = False
        if not args.no_publish and settings()["publishing"]["auto_publish"]:
            week = datetime.now(UTC).isocalendar()
            published = publish(f"Weekly update {week[0]}-W{week[1]:02d} (run {run_id})")
        report["published"] = published

        spec_cfg = settings().get("specialist", {})
        if failed and spec_cfg.get("enabled") and not args.no_analyze:
            from run_specialist import failing_sources, run_for
            targets = failing_sources(conn, spec_cfg.get("max_sources_per_run", 5))
            if targets:
                log.info("invoking difficult-source-specialist for %d sources", len(targets))
                ok, _out = run_for(targets)
                report["specialist"] = {"invoked_for": [t["source_id"] for t in targets], "ok": ok}

        report["needs_human_review"] = [
            {"id": s["source_id"], "reason": s["error"]} for s in failed
        ]
        report["finished_at"] = db.now_iso()
        report["status"] = "ok" if not failed else "ok_with_source_errors"
        return 0
    except Exception as exc:
        log.exception("run failed")
        report["status"] = "failed"
        report["error"] = f"{type(exc).__name__}: {exc}"
        return 1
    finally:
        db.finish_run(conn, run_id, report)
        db.audit(conn, "pipeline", "run_finish", report.get("status", "?"))
        path = write_report(stamp, report)
        logging.getLogger("weekly").info("report: %s", path)
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
