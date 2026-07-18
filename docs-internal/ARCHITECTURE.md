# Architecture & data model

## Components
- **sources/registry.yaml** — versioned source registry (494 entries). Fields: id, name, url, type,
  country, language[], access{method,rss,notes}, monitoring_focus, categories[], trust_tier,
  status (active | review | pending_approval | unresolved | excluded | rejected), exclusion_reason,
  origin (pdf_inventar | pdf_catalog | scout | specialist | manual).
- **src/collectors** — `fetcher.py` (politeness: robots.txt, per-domain delay, retries/backoff,
  timeouts, conditional GET, truststore SSL), `discovery.py` (feed autodiscovery), `rss.py`,
  `html_page.py` (listing→article extraction), `pdf_doc.py`, `collect.py` (per-source state machine).
- **src/processing** — `normalize.py` (canonical URL, clean text, content hash, langdetect),
  `dedup.py` (URL / hash / fuzzy-title against last 500 items).
- **src/analysis** — `schemas.py` (pydantic contracts), `prompt.py` (untrusted-content wrapping),
  `engine.py` (headless `claude -p`, JSON extraction, validation, one retry, batching, cost caps),
  `brief.py` (weekly executive brief).
- **src/publish** — `export_json.py` (docs/data/*.json), `publish.py` (git commit+push).
- **src/common** — `config.py`, `db.py` (SQLite schema below), `headless.py` (subagent invocation).
- **scripts** — `run_weekly.py` (orchestrator), `run_monthly_scout.py`, `run_specialist.py`,
  `rollback.py`, `setup_scheduler.ps1`, `merge_registry.py` (stage-2 provenance),
  `make_demo_data.py` (layout preview only).
- **docs/** — static dashboard (GitHub Pages): index.html + assets (vanilla JS, self-contained
  search index, no external dependencies) + data/*.json.
- **.claude/agents** — `monthly-source-scout`, `difficult-source-specialist` (isolated contexts,
  minimal tools, never call each other; orchestration only from scripts).

## SQLite (data/monitor.db)
- `items(id, source_id, url, canonical_url UNIQUE, title, content_text, content_hash, lang,
  published_at, fetched_at, status, relevance, analysis_json, run_id)`
  status flow: new → analyzed | triaged_out | duplicate; analyzed → (export) → archived by retention.
  On engine failure items REMAIN 'new' (retried next run).
- `source_state(source_id PK, method, feed_url, etag, last_modified, last_run_at, last_ok_at,
  fail_count, last_error)` — incremental & idempotent collection; registry access overrides
  (set by the specialist) take precedence over cached state.
- `runs(id, kind, started_at, finished_at, stats_json)` — every run's full report.
- `audit_log(at, actor, action, detail)` — pipeline/scout/specialist/human actions.

## Guarantees
- **Idempotency**: re-running never duplicates items (canonical_url UNIQUE + hash dedup).
- **Prompt-injection defence**: web text only ever appears between UNTRUSTED markers; headless
  analysis runs with no tools; outputs must validate against pydantic schemas or are retried/dropped.
- **Cost control**: batch size, relevance threshold, max published per run, max items per source —
  all in `config/settings.yaml`.
- **Model swap**: `analysis.model` / `analysis.engine` in settings; no code changes needed.
- **Confidence labels** are part of the schema and rendered on every card; inference is never
  presented as fact.
- **Retention**: dashboard 12 months; SQLite unlimited; weekly DB backups (keep 8).

## Publishing
GitHub Pages serves `docs/` from `main` (repo COSMINILIESCU/jde-peets-eu-monitor, public).
`rollback.py` reverts the last publish commit (git revert, history preserved) and pushes.
