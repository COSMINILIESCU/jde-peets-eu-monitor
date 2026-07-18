/* JDE Peet's EU/EEA Intelligence Monitor — vanilla JS, no dependencies. */
"use strict";

const TABS = [
  { id: "brief", label: "Executive Brief" },
  { id: "high_impact", label: "High-Impact Alerts" },
  { id: "jde_peets", label: "JDE Peet's & Brands" },
  { id: "kdp_impact", label: "Keurig Dr Pepper → EU" },
  { id: "competitors_direct", label: "Direct Competitors" },
  { id: "competitors_adjacent", label: "Adjacent & Disruptors" },
  { id: "legislation", label: "Legislation" },
  { id: "draft_legislation", label: "Draft Acts" },
  { id: "case_law_investigations", label: "Case Law & Investigations" },
  { id: "eu_communications", label: "EU Communications" },
  { id: "supply_chain", label: "Supply Chain & Commodities" },
  { id: "sustainability", label: "Sustainability & EUDR" },
  { id: "consumers_marketing_competition", label: "Consumers & Competition" },
  { id: "tech_data_ai", label: "Tech, Data & AI" },
  { id: "press", label: "Press Review" },
  { id: "sources", label: "Sources & Status" },
  { id: "all", label: "All Items" },
];

const CONF_LABELS = {
  confirmed_fact: "Confirmed fact", company_statement: "Company statement",
  third_party_claim: "Third-party claim", analysis: "Analysis",
  inference: "Inference", unconfirmed: "Unconfirmed",
};
const PERIODS = [
  { id: "7", label: "Last 7 days" }, { id: "31", label: "Last month" },
  { id: "92", label: "Last 3 months" }, { id: "365", label: "Last 12 months" },
  { id: "all", label: "All time" },
];
const PAGE = 40;

const DEFAULT_PERIOD = "92";
const state = { tab: "brief", q: "", period: DEFAULT_PERIOD, country: "", lang: "", entity: "", brand: "", impact: "", confidence: "", shown: PAGE };
let ITEMS = [], SOURCES = [], META = {}, BRIEF = null, INDEX = new Map();

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function loadJSON(path, fallback) {
  try { const r = await fetch(path); if (!r.ok) throw new Error(r.status); return await r.json(); }
  catch { return fallback; }
}

/* --- tiny full-text index: word -> Set(itemIdx) --- */
function tokenize(s) { return (s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").match(/[a-z0-9]{2,}/g) || []; }
function buildIndex() {
  INDEX = new Map();
  ITEMS.forEach((it, i) => {
    const words = new Set(tokenize([it.title, it.title_en, it.summary_en, (it.keywords || []).join(" "),
      (it.entities || []).join(" "), (it.brands || []).join(" "), it.source_name].join(" ")));
    for (const w of words) { if (!INDEX.has(w)) INDEX.set(w, new Set()); INDEX.get(w).add(i); }
  });
}
function searchIds(q) {
  const terms = tokenize(q);
  if (!terms.length) return null;
  let result = null;
  for (const t of terms) {
    const matches = new Set();
    for (const [w, ids] of INDEX) if (w.startsWith(t)) for (const id of ids) matches.add(id);
    result = result === null ? matches : new Set([...result].filter((x) => matches.has(x)));
    if (!result.size) break;
  }
  return result;
}

/* --- filtering --- */
function visibleItems() {
  const ids = searchIds(state.q);
  const now = Date.now(), days = state.period === "all" ? Infinity : +state.period;
  return ITEMS.filter((it, i) => {
    if (ids !== null && !ids.has(i)) return false;
    const d = Date.parse(it.published_at || it.fetched_at);
    if (isFinite(days) && (isNaN(d) || now - d > days * 864e5)) return false;
    if (state.tab === "high_impact" && it.impact !== "high") return false;
    if (state.tab === "press" && !["press", "trade_press"].includes(it.source_type)) return false;
    if (!["brief", "high_impact", "press", "sources", "all"].includes(state.tab)) {
      if (it.category !== state.tab && !(it.categories || []).includes(state.tab)) return false;
    }
    if (state.country && !(it.countries || []).includes(state.country)) return false;
    if (state.lang && it.lang !== state.lang) return false;
    if (state.entity && !(it.entities || []).includes(state.entity)) return false;
    if (state.brand && !(it.brands || []).includes(state.brand)) return false;
    if (state.impact && it.impact !== state.impact) return false;
    if (state.confidence && it.confidence !== state.confidence) return false;
    return true;
  });
}

/* --- rendering --- */
function fmtDate(iso) { if (!iso) return "n/a"; const d = new Date(iso); return isNaN(d) ? "n/a" : d.toISOString().slice(0, 10); }

function feedbackLink(it) {
  if (!META.repo_url) return "";
  const title = encodeURIComponent(`[feedback] item #${it.id}: ${(it.title_en || it.title).slice(0, 80)}`);
  const body = encodeURIComponent(`Item: ${it.url}\nProblem (wrong relevance / category / summary / other):\n\n`);
  return `${META.repo_url}/issues/new?title=${title}&body=${body}`;
}

function cardHTML(it) {
  const badges = [
    `<span class="badge impact-${esc(it.impact)}">${esc(it.impact)} impact</span>`,
    `<span class="badge conf">${esc(CONF_LABELS[it.confidence] || it.confidence)}</span>`,
    ...(it.countries || []).slice(0, 4).map((c) => `<span class="badge">${esc(c)}</span>`),
    ...(it.brands || []).slice(0, 3).map((b) => `<span class="badge">${esc(b)}</span>`),
    it.lang && it.lang !== "en" ? `<span class="badge">original: ${esc(it.lang.toUpperCase())}</span>` : "",
  ].join("");
  const fb = feedbackLink(it);
  return `<article class="card impact-${esc(it.impact)}">
    <h3><a href="${esc(it.url)}" target="_blank" rel="noopener">${esc(it.title_en || it.title)}</a></h3>
    ${it.summary_en ? `<p class="summary">${esc(it.summary_en)}</p>` : ""}
    <div class="badges">${badges}</div>
    <div class="src-line">
      <span>Source: <a href="${esc(it.url)}" target="_blank" rel="noopener">${esc(it.source_name)}</a></span>
      <span>Published: ${fmtDate(it.published_at)}</span>
      <span>Accessed: ${fmtDate(it.fetched_at)}</span>
      ${fb ? `<a class="feedback" href="${fb}" target="_blank" rel="noopener" title="Report wrong classification or summary">✎ Feedback</a>` : ""}
    </div>
  </article>`;
}

function renderKPIs(list) {
  const week = list.filter((it) => Date.now() - Date.parse(it.published_at || it.fetched_at) < 7 * 864e5);
  const high = list.filter((it) => it.impact === "high");
  const countries = new Set(list.flatMap((it) => it.countries || []));
  $("kpi-row").innerHTML = [
    { v: list.length, l: "items in current view" },
    { v: week.length, l: "new in last 7 days" },
    { v: high.length, l: "high-impact items", hot: high.length > 0 },
    { v: countries.size, l: "countries covered" },
  ].map((k) => `<div class="kpi${k.hot ? " hot" : ""}"><div class="v">${k.v}</div><div class="l">${esc(k.l)}</div></div>`).join("");
}

function renderItems() {
  const list = visibleItems();
  renderKPIs(list);
  $("result-count").textContent = `${list.length} item(s)` + (state.q ? ` for "${state.q}"` : "");
  $("cards").innerHTML = list.slice(0, state.shown).map(cardHTML).join("") ||
    `<div class="notice">No items match the current filters. The dashboard fills up after the first weekly run.</div>`;
  $("btn-more").hidden = list.length <= state.shown;
}

function renderBrief() {
  const el = $("view-brief");
  const high = ITEMS.filter((it) => it.impact === "high").slice(0, 8);
  const alerts = high.map((it) =>
    `<div class="alert-item"><a href="${esc(it.url)}" target="_blank" rel="noopener">${esc(it.title_en || it.title)}</a>
     <div class="badges" style="margin-top:6px"><span class="badge conf">${esc(CONF_LABELS[it.confidence] || it.confidence)}</span>
     <span class="badge">${esc(it.source_name)}</span><span class="badge">${fmtDate(it.published_at)}</span></div></div>`).join("");
  el.innerHTML = `<div class="brief">
      <h2>Executive Brief</h2>
      <div class="brief-week">${BRIEF ? `Week ${esc(BRIEF.week || "")} · generated ${fmtDate(BRIEF.generated_at)}` : ""}</div>
      ${BRIEF && BRIEF.text ? `<div class="brief-text">${esc(BRIEF.text)}</div>` :
        `<div class="notice">The executive brief is generated automatically after each weekly run.</div>`}
      ${high.length ? `<h2 style="font-size:18px">High-impact alerts</h2><div class="alert-list">${alerts}</div>` : ""}
    </div>`;
}

function sourceRow(s) {
  const dot = s.fail_count > 0 ? "fail" : (s.last_ok_at ? "ok" : "idle");
  const st = s.status !== "active" ? ` <span class="badge">${esc(s.status)}</span>` : "";
  return `<tr><td><span class="dot ${dot}"></span><a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.name)}</a>${st}</td>
    <td>${esc(s.type)}</td><td>${esc(s.country)}</td><td>${esc((s.language || []).join(", "))}</td>
    <td>${esc(s.method || "—")}</td><td>${s.last_ok_at ? fmtDate(s.last_ok_at) : "—"}</td>
    <td>${s.fail_count ? esc(String(s.fail_count)) + " × " + esc(s.last_error || s.exclusion_reason || "") : esc(s.exclusion_reason || "")}</td></tr>`;
}

function renderSources() {
  const groups = {};
  for (const s of SOURCES) (groups[s.status] ||= []).push(s);
  const order = ["active", "review", "pending_approval", "unresolved", "excluded", "rejected"];
  const rows = order.flatMap((k) => groups[k] || []).map(sourceRow).join("");
  $("view-sources").innerHTML = `
    <div class="kpi-row">
      <div class="kpi"><div class="v">${SOURCES.length}</div><div class="l">registered sources</div></div>
      <div class="kpi"><div class="v">${(groups.active || []).length}</div><div class="l">active</div></div>
      <div class="kpi"><div class="v">${SOURCES.filter((s) => s.fail_count > 0).length}</div><div class="l">with recent errors</div></div>
      <div class="kpi"><div class="v">${(groups.review || []).length + (groups.pending_approval || []).length}</div><div class="l">awaiting review</div></div>
    </div>
    <div class="sources-table-wrap"><table class="sources">
      <thead><tr><th>Source</th><th>Type</th><th>Country</th><th>Lang</th><th>Method</th><th>Last OK</th><th>Notes / errors</th></tr></thead>
      <tbody>${rows}</tbody></table></div>`;
}

function render() {
  const isBrief = state.tab === "brief", isSources = state.tab === "sources";
  $("view-brief").hidden = !isBrief;
  $("view-sources").hidden = !isSources;
  $("view-items").hidden = isBrief || isSources;
  $("toolbar").style.display = isBrief || isSources ? "none" : "flex";
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === state.tab));
  if (isBrief) renderBrief(); else if (isSources) renderSources(); else renderItems();
}

/* --- filters & toolbar --- */
function fillSelect(id, label, values) {
  const el = $(id);
  el.innerHTML = `<option value="">${esc(label)}</option>` +
    values.map(([v, l]) => `<option value="${esc(v)}">${esc(l)}</option>`).join("");
}
function counts(list, get) {
  const m = new Map();
  for (const it of list) for (const v of [].concat(get(it) || [])) if (v) m.set(v, (m.get(v) || 0) + 1);
  return [...m.entries()].sort((a, b) => b[1] - a[1]);
}
function initFilters() {
  fillSelect("f-period", "Period", PERIODS.map((p) => [p.id, p.label]));
  $("f-period").value = state.period;
  fillSelect("f-country", "Country", counts(ITEMS, (i) => i.countries).map(([v, n]) => [v, `${v} (${n})`]));
  fillSelect("f-lang", "Source language", counts(ITEMS, (i) => i.lang).map(([v, n]) => [v, `${v.toUpperCase()} (${n})`]));
  fillSelect("f-entity", "Entity", counts(ITEMS, (i) => i.entities).slice(0, 60).map(([v, n]) => [v, `${v} (${n})`]));
  fillSelect("f-brand", "Brand", counts(ITEMS, (i) => i.brands).slice(0, 40).map(([v, n]) => [v, `${v} (${n})`]));
  fillSelect("f-impact", "Impact", [["high", "High"], ["medium", "Medium"], ["low", "Low"]]);
  fillSelect("f-confidence", "Confidence", Object.entries(CONF_LABELS));
}

function download(name, text, type) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type }));
  a.download = name; a.click(); URL.revokeObjectURL(a.href);
}
function exportCSV() {
  const cols = ["title_en", "summary_en", "url", "source_name", "category", "countries", "impact", "confidence", "published_at", "lang"];
  const lines = [cols.join(",")].concat(visibleItems().map((it) =>
    cols.map((c) => `"${String(Array.isArray(it[c]) ? it[c].join("; ") : it[c] ?? "").replace(/"/g, '""').replace(/\n/g, " ")}"`).join(",")));
  download("jde-monitor-export.csv", "﻿" + lines.join("\r\n"), "text/csv;charset=utf-8");
}

/* --- init --- */
function bind() {
  $("tabs").addEventListener("click", (e) => {
    const t = e.target.closest(".tab"); if (!t) return;
    state.tab = t.dataset.tab; state.shown = PAGE; render();
  });
  $("search").addEventListener("input", (e) => { state.q = e.target.value; state.shown = PAGE; render(); });
  for (const [id, key] of [["f-period", "period"], ["f-country", "country"], ["f-lang", "lang"],
    ["f-entity", "entity"], ["f-brand", "brand"], ["f-impact", "impact"], ["f-confidence", "confidence"]]) {
    $(id).addEventListener("change", (e) => { state[key] = e.target.value; state.shown = PAGE; render(); });
  }
  $("btn-reset").addEventListener("click", () => {
    Object.assign(state, { q: "", period: DEFAULT_PERIOD, country: "", lang: "", entity: "", brand: "", impact: "", confidence: "", shown: PAGE });
    $("search").value = ""; initFilters(); render();
  });
  $("btn-more").addEventListener("click", () => { state.shown += PAGE; renderItems(); });
  $("btn-export-csv").addEventListener("click", exportCSV);
  $("btn-export-json").addEventListener("click", () =>
    download("jde-monitor-export.json", JSON.stringify(visibleItems(), null, 1), "application/json"));
}

function tabCounts() {
  const n = (pred) => ITEMS.filter(pred).length;
  return {
    high_impact: n((i) => i.impact === "high"),
    press: n((i) => ["press", "trade_press"].includes(i.source_type)),
    all: ITEMS.length,
    ...Object.fromEntries(TABS.filter((t) => !["brief", "high_impact", "press", "sources", "all"].includes(t.id))
      .map((t) => [t.id, n((i) => i.category === t.id || (i.categories || []).includes(t.id))])),
  };
}

async function main() {
  [ITEMS, SOURCES, META, BRIEF] = await Promise.all([
    loadJSON("data/items.json", []), loadJSON("data/sources.json", []),
    loadJSON("data/meta.json", {}), loadJSON("data/brief.json", null),
  ]);
  buildIndex();
  const tc = tabCounts();
  $("tabs").innerHTML = TABS.map((t) =>
    `<button class="tab" type="button" data-tab="${t.id}">${esc(t.label)}${tc[t.id] ? `<span class="n">${tc[t.id]}</span>` : ""}</button>`).join("");
  $("meta-line").textContent = META.generated_at
    ? `Last updated ${META.generated_at.replace("T", " ").slice(0, 16)} UTC · ${ITEMS.length} items in the last 12 months · week ${META.week || ""}`
    : "No data published yet — the first weekly run will populate this dashboard.";
  $("footer-generated").textContent = META.generated_at ? `Generated ${META.generated_at.slice(0, 10)}` : "";
  initFilters(); bind(); render();
}
main();
