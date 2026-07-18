# JDE Peet's EU/EEA Intelligence Monitor

**Live dashboard:** https://cosminiliescu.github.io/jde-peets-eu-monitor/

A weekly business-intelligence monitor covering JDE Peet's, its brands, Keurig Dr Pepper's impact
on Europe, competitors, the coffee/tea value chain, and EU/EEA legislation, regulation and case
law — aggregated from ~490 public sources in all EU/EEA languages, summarised in English, and
published as a static dashboard.

Provided by [Păcuraru Iliescu Măzăreanu, Societate Civilă de Avocați](https://www.pimasociates.ro/).

## How it works

```
Windows Task Scheduler (Monday 07:00)
  └─ scripts/run_weekly.py
       1. collect  — RSS/HTML/PDF collectors over sources/registry.yaml
                     (robots.txt respected, rate-limited, retries, conditional GETs)
       2. dedup    — canonical URL + content hash + fuzzy titles
       3. analyze  — Claude (headless) triage + classification + 1-2 ¶ English summary,
                     validated with pydantic; web text treated as untrusted data
       4. export   — docs/data/*.json (items, sources, meta, executive brief)
       5. publish  — git commit + push → GitHub Pages
       6. report   — logs/report_*.json (failures, counts, items needing review)
```

- Every item keeps: source link, publication date, access date, original language, confidence
  label (`confirmed_fact / company_statement / third_party_claim / analysis / inference /
  unconfirmed`).
- A monthly subagent (`monthly-source-scout`) proposes new sources — official bodies are
  auto-added, everything else awaits human approval. A second subagent
  (`difficult-source-specialist`) rescues sources the standard collector cannot read.
- Full local archive in SQLite (`data/monitor.db`, not published); the dashboard shows the last
  12 months.

## Commands

| Task | Command |
|---|---|
| Full weekly run | `python scripts/run_weekly.py` |
| Run without publishing | `python scripts/run_weekly.py --no-publish` |
| Run without AI | `python scripts/run_weekly.py --no-analyze` |
| Roll back the last publish | `python scripts/rollback.py` |
| Monthly source scout (force) | `python scripts/run_monthly_scout.py --force` |
| Rescue failing sources | `python scripts/run_specialist.py` |
| Tests / lint | `python -m pytest` · `python -m ruff check src scripts tests` |
| (Re)register schedulers | `powershell -ExecutionPolicy Bypass -File scripts/setup_scheduler.ps1` |

## Install (new machine)

1. Python 3.12+, Git, GitHub CLI (`gh auth login`), Claude Code CLI (`claude` + login).
2. `pip install -r requirements.txt`
3. Copy `.env.example` → `.env` (defaults are fine; no API keys needed).
4. `powershell -ExecutionPolicy Bypass -File scripts/setup_scheduler.ps1`

Or with Docker (collection/export only): `docker build -t jde-monitor . && docker run jde-monitor`

## Operations & troubleshooting

See [docs-internal/OPERATIONS.md](docs-internal/OPERATIONS.md) (Romanian, non-technical runbook)
and [docs-internal/ARCHITECTURE.md](docs-internal/ARCHITECTURE.md).

## Disclaimer

The dashboard aggregates publicly accessible information only, respects robots.txt/site terms,
and is not legal advice. Content of external sources belongs to their respective publishers.
