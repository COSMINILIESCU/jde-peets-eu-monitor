/* The JDE Peet's Gazette — command desk + dynamically paginated newspaper.
   Vanilla JS, no dependencies. Reads docs/data/*.json (the real data contract). */
"use strict";

/* ---- taxonomy ---- */
const CONF_LABELS = {
  confirmed_fact: "Confirmed fact", company_statement: "Company statement",
  third_party_claim: "Third-party claim", analysis: "Analysis",
  inference: "Inference", unconfirmed: "Unconfirmed",
};
const IMPACT_LABEL = { high: "High impact", medium: "Medium impact", low: "Low impact" };
const PERIODS = [
  ["7", "Last 7 days"], ["31", "Last month"], ["92", "Last 3 months"],
  ["365", "Last 12 months"], ["all", "All time"],
];
const DEFAULT_PERIOD = "7";

/* Editorial groups: each item lands in exactly ONE thematic group (by category).
   'alerts' (cover teasers) and 'press' are cross-cutting selections referencing thematic items. */
const GROUPS = [
  { key: "companies", kicker: "JDE Peet's & Brands · Keurig Dr Pepper → EU", short: "Companies & Market",
    cats: ["jde_peets", "kdp_impact"] },
  { key: "competition", kicker: "Direct Competitors · Adjacent & Disruptors", short: "Competitors & Disruptors",
    cats: ["competitors_direct", "competitors_adjacent"] },
  { key: "legal", kicker: "Legislation · Draft Acts · Case Law · EU Communications", short: "Legal & Case Law",
    cats: ["legislation", "draft_legislation", "case_law_investigations", "eu_communications"] },
  { key: "regulation", kicker: "Sustainability & EUDR · Consumers & Competition · Tech, Data & AI", short: "Sector Regulation",
    cats: ["sustainability", "consumers_marketing_competition", "tech_data_ai"] },
  { key: "supply", kicker: "Supply Chain & Commodities", short: "Supply Chain",
    cats: ["supply_chain"] },
  { key: "other", kicker: "Other EU/EEA Developments", short: "Other Developments", cats: [] },
];

const state = { q: "", period: DEFAULT_PERIOD, from: "", to: "", country: "", lang: "", entity: "", brand: "", impact: "", confidence: "" };
let ITEMS = [], SOURCES = [], META = {}, BRIEF = null, INDEX = new Map();
let faces = [], itemFace = new Map(), flipped = 0, TOTAL = 0;

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmtDate = (iso) => { if (!iso) return "n/a"; const d = new Date(iso); return isNaN(d) ? "n/a" : d.toISOString().slice(0, 10); };

async function loadJSON(path, fb) {
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const r = await fetch(path, { cache: "no-store" });
      if (!r.ok) throw new Error(r.status);
      return await r.json();
    } catch {
      await new Promise((res) => setTimeout(res, 250 * (attempt + 1)));
    }
  }
  return fb;
}

/* ---- full-text index ---- */
const tokenize = (s) => (s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").match(/[a-z0-9]{2,}/g) || [];
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
  let res = null;
  for (const t of terms) {
    const m = new Set();
    for (const [w, ids] of INDEX) if (w.startsWith(t)) for (const id of ids) m.add(id);
    res = res === null ? m : new Set([...res].filter((x) => m.has(x)));
    if (!res.size) break;
  }
  return res;
}

/* ---- filtering ---- */
function passesFilters(it) {
  const d = Date.parse(it.published_at || it.fetched_at);
  if (state.from || state.to) {
    // custom calendar range overrides the period dropdown; "to" is inclusive of the whole day
    if (isNaN(d)) return false;
    if (state.from && d < Date.parse(state.from)) return false;
    if (state.to && d > Date.parse(state.to) + 864e5) return false;
  } else {
    const days = state.period === "all" ? Infinity : +state.period;
    if (isFinite(days) && (isNaN(d) || Date.now() - d > days * 864e5)) return false;
  }
  if (state.country && !(it.countries || []).includes(state.country)) return false;
  if (state.lang && it.lang !== state.lang) return false;
  if (state.entity && !(it.entities || []).includes(state.entity)) return false;
  if (state.brand && !(it.brands || []).includes(state.brand)) return false;
  if (state.impact && it.impact !== state.impact) return false;
  if (state.confidence && it.confidence !== state.confidence) return false;
  return true;
}
function pool() { return ITEMS.filter(passesFilters); }
function groupOf(it) {
  // primary category decides the section; fall back to secondary categories, then "other"
  const primary = GROUPS.find((g) => g.key !== "other" && g.cats.includes(it.category));
  if (primary) return primary.key;
  for (const c of it.categories || []) {
    const g = GROUPS.find((g) => g.key !== "other" && g.cats.includes(c));
    if (g) return g.key;
  }
  return "other";
}

/* ---- item rendering (newspaper entry) ---- */
function confChip(it) {
  const weak = it.confidence === "inference" || it.confidence === "unconfirmed";
  return `<span class="conf ${weak ? "red" : ""}">${esc(CONF_LABELS[it.confidence] || it.confidence)}</span>`;
}
function impChip(it) {
  if (it.impact === "low") return "";
  return `<span class="conf imp ${it.impact}">${esc(IMPACT_LABEL[it.impact])}</span>`;
}
function feedbackLink(it) {
  if (!META.repo_url) return "";
  const t = encodeURIComponent(`[feedback] item #${it.id}: ${(it.title_en || it.title).slice(0, 70)}`);
  const b = encodeURIComponent(`Item: ${it.url}\nIssue (relevance / category / summary / other):\n\n`);
  return `<a class="feedback" href="${META.repo_url}/issues/new?title=${t}&body=${b}" target="_blank" rel="noopener">✎ Feedback</a>`;
}
function entryHTML(it, sectionName) {
  const tags = [
    ...(it.countries || []).slice(0, 5).map((c) => `<span class="chip">${esc(c)}</span>`),
    ...(it.entities || []).slice(0, 2).map((e) => `<span class="chip">${esc(e)}</span>`),
    ...(it.brands || []).slice(0, 3).map((b) => `<span class="chip">${esc(b)}</span>`),
    it.lang && it.lang !== "en" ? `<span class="chip">orig: ${esc(it.lang.toUpperCase())}</span>` : "",
  ].join("");
  return `<article class="entry">
    <h3 class="headline h-md"><a href="${esc(it.url)}" target="_blank" rel="noopener">${esc(it.title_en || it.title)}</a></h3>
    <div class="byline"><b>${esc(sectionName)}</b> · ${fmtDate(it.published_at)} · source: <b>${esc(it.source_name)}</b> ${impChip(it)} ${confChip(it)} ${feedbackLink(it)}</div>
    ${it.summary_en ? `<div class="summary bodytext"><p>${esc(it.summary_en)}</p></div>` : ""}
    <div class="tags">${tags}</div>
  </article>`;
}

/* ---- pagination: pack items into fixed-size newspaper pages ---- */
function estHeight(it) {
  const s = (it.summary_en || "").length;
  return 70 + Math.min(7, Math.ceil(s / 60)) * 18 + 14;
}
function packPages(items, firstBudget, budget) {
  const pages = [];
  let cur = [], h = 0, lim = firstBudget;
  for (const it of items) {
    const eh = estHeight(it);
    if (cur.length && h + eh > lim) { pages.push(cur); cur = []; h = 0; lim = budget; }
    cur.push(it); h += eh;
  }
  if (cur.length) pages.push(cur);
  return pages.length ? pages : [[]];
}

/* ---- build the edition (faces + item→face map + side/cover TOC) ---- */
const byRel = (a, b) => (b.relevance || 0) - (a.relevance || 0);
const AL_PER = 9, PR_PER = 9;
function teaserPages(items, per) {
  const p = []; for (let i = 0; i < items.length; i += per) p.push(items.slice(i, i + per));
  return p;
}
function teaserHTML(it) {
  const f = itemFace.get(it.id);
  const link = f != null
    ? `<a data-goto="${gotoFor(f)}">${esc(it.title_en || it.title)}</a>`
    : `<a href="${esc(it.url)}" target="_blank" rel="noopener">${esc(it.title_en || it.title)}</a>`;
  return `<div class="teaser">${link}<div class="tl">${esc(it.source_name)} · ${fmtDate(it.published_at)} · ${esc(CONF_LABELS[it.confidence] || it.confidence)}${f != null ? " · p." + pageNo(f) : ""}</div></div>`;
}

function buildEdition() {
  const items = pool();
  faces = []; itemFace = new Map();

  const high = items.filter((it) => it.impact === "high").sort(byRel);
  const press = items.filter((it) => ["press", "trade_press"].includes(it.source_type)).sort(byRel).slice(0, 30);
  const alertPages = high.length ? teaserPages(high, AL_PER) : [];
  const pressPages = press.length ? teaserPages(press, PR_PER) : [];

  // face-index bookkeeping so cross-cutting teasers can link to thematic pages
  const alertsStart = 1;
  const thematicStart = alertsStart + alertPages.length;

  // 1) thematic faces (register item -> face)
  const thematic = [];
  const tocEntries = [];
  if (alertPages.length) tocEntries.push({ short: "High-Impact Alerts", faceIndex: alertsStart, count: high.length });
  for (const g of GROUPS) {
    const gi = items.filter((it) => groupOf(it) === g.key);
    if (!gi.length) continue;
    gi.sort(byRel);
    const pages = packPages(gi, 450, 520);
    tocEntries.push({ short: g.short, faceIndex: thematicStart + thematic.length, count: gi.length });
    pages.forEach((chunk, idx) => {
      const faceIndex = thematicStart + thematic.length;
      chunk.forEach((it) => itemFace.set(it.id, faceIndex));
      const body = chunk.map((it) => entryHTML(it, g.short)).join('<hr class="rule-h">');
      thematic.push({
        kind: "content",
        html: `<div class="kicker">${esc(g.short)}<span>${esc(g.kicker)}${pages.length > 1 ? ` · ${idx + 1}/${pages.length}` : ""}</span></div>${body}`,
        folio: g.short,
      });
    });
  }
  const pressStart = thematicStart + thematic.length;
  if (pressPages.length) tocEntries.push({ short: "Press Review", faceIndex: pressStart, count: press.length });

  // 2) assemble faces in display order
  faces.push({ kind: "cover", html: "" });                                   // 0 (filled below)
  alertPages.forEach((chunk, idx) => faces.push({
    kind: "content", folio: "High-Impact Alerts",
    html: `<div class="kicker">High-Impact Alerts<span>items flagged high impact${alertPages.length > 1 ? ` · ${idx + 1}/${alertPages.length}` : ""}</span></div>${chunk.map(teaserHTML).join("")}`,
  }));
  thematic.forEach((f) => faces.push(f));
  pressPages.forEach((chunk, idx) => faces.push({
    kind: "content", folio: "Press Review",
    html: `<div class="kicker">Press Review<span>selected trade &amp; general press${pressPages.length > 1 ? ` · ${idx + 1}/${pressPages.length}` : ""}</span></div>${chunk.map(teaserHTML).join("")}`,
  }));
  faces.push({ kind: "sources", html: sourcesHTML(items), folio: "Sources & Masthead" });

  faces[0].html = coverHTML(items, tocEntries);
  if (faces.length % 2 === 1) faces.push({ kind: "blank", html: "", folio: "" });

  renderBook();
  renderSideTOC(tocEntries);
  flipped = 0;
  render();
  return items;
}

function pageNo(faceIndex) { return faceIndex + 1; }
function gotoFor(faceIndex) { return Math.ceil(faceIndex / 2); }

function coverHTML(items, tocEntries) {
  const toc = tocEntries.map((t) =>
    `<li data-goto="${gotoFor(t.faceIndex)}"><span class="toc-name">${esc(t.short)}</span><span class="dots"></span><span class="pg">p. ${pageNo(t.faceIndex)}</span></li>`).join("");

  const cnt = countsFor(items);
  const wk = (BRIEF && BRIEF.week) || META.week || "";
  let bt = BRIEF && BRIEF.text ? String(BRIEF.text).trim() : "";
  let truncated = false;
  if (bt.length > 640) { bt = bt.slice(0, 640).replace(/\s+\S*$/, ""); truncated = true; }
  const briefText = bt
    ? `<div class="bodytext cols-2"><p class="lead">${esc(bt).replace(/\n\n+/g, "</p><p>")}</p>${truncated ? '<p style="font-style:italic;color:#7D745E">— the full brief and all items follow in the edition.</p>' : ""}</div>`
    : `<div class="empty-note">The weekly executive brief is generated automatically after each run.</div>`;

  return `
    <div class="masthead">
      <div class="ears"><span>EU/EEA Edition · Week ${esc(wk)}</span><span>Provided by Păcuraru Iliescu Măzăreanu SCA</span></div>
      <h1>THE <span class="red">JDE PEET'S</span> GAZETTE</h1>
      <div class="tagline">Weekly business, legal &amp; regulatory monitor — European Union &amp; European Economic Area</div>
      <div class="dateline"><span>${esc(fmtDate(META.generated_at))}</span><span>Week ${esc(wk)}</span><span>Updated ${esc((META.generated_at || "").slice(11, 16))} UTC</span></div>
    </div>
    <div class="byline">Executive Brief · <b>The week in summary</b></div>
    ${briefText}
    <div class="stats-row">
      <div><div class="n">${cnt.total}</div><div class="l">items · edition</div></div>
      <div><div class="n">${cnt.week}</div><div class="l">new · 7 days</div></div>
      <div><div class="n red">${cnt.high}</div><div class="l">high impact</div></div>
      <div><div class="n">${cnt.countries}</div><div class="l">countries</div></div>
    </div>
    <div class="box"><span class="box-t">Contents</span><ul class="toc">${toc}</ul></div>
    <div class="folio"><span>The JDE Peet's Gazette</span><span>Page 1</span></div>
    <div class="corner" data-corner="next"></div>`;
}

function sourcesHTML(items) {
  const active = SOURCES.filter((s) => s.status === "active");
  const failing = SOURCES.filter((s) => s.fail_count > 0);
  const review = SOURCES.filter((s) => s.status === "review" || s.status === "pending_approval");
  const langs = [...new Set(items.map((it) => it.lang).filter(Boolean))].map((l) => l.toUpperCase()).sort().join(" · ");
  const next = META.last_run && META.last_run.finished_at ? "next Monday 07:00" : "next Monday 07:00";
  const shown = failing.slice(0, 40).map((s) =>
    `<div class="s-item"><span class="dot fail"></span>${esc(s.name)} <span style="color:#7D745E">(${esc(s.last_error || "").slice(0, 40)})</span></div>`).join("");
  return `
    <div class="kicker">Sources &amp; Status<span>state of the monitoring system</span></div>
    <table class="status-tbl">
      <tr><td>Registered sources</td><td>${SOURCES.length}</td></tr>
      <tr><td>Active &amp; monitored</td><td class="ok">${active.length} · operational</td></tr>
      <tr><td>With recent fetch errors</td><td class="warn">${failing.length} · retrying</td></tr>
      <tr><td>Awaiting editorial review</td><td>${review.length}</td></tr>
      <tr><td>Last full run</td><td>${esc(fmtDate(META.generated_at))} ${esc((META.generated_at || "").slice(11, 16))} UTC</td></tr>
      <tr><td>Next scheduled run</td><td>${esc(next)}</td></tr>
      <tr><td>Language coverage</td><td>${esc(langs || "—")}</td></tr>
    </table>
    ${failing.length ? `<div class="box"><span class="box-t">Sources retrying</span><div class="src-list">${shown}</div></div>` : ""}
    <hr class="rule-double">
    <div class="kicker" style="border-bottom-width:1.5px">Masthead &amp; Notice</div>
    <p class="smallprint"><b>Notice.</b> This internal publication aggregates publicly available information and machine-generated
    summaries for monitoring purposes only. It is not legal advice. Each item is labelled by confidence level —
    confirmed fact, company statement, third-party claim, analysis, inference, unconfirmed. Always verify against the
    original source via the link on each item title. Content of external sources belongs to their respective publishers.</p>
    <p class="smallprint" style="margin-top:8px"><b>Provided by Păcuraru Iliescu Măzăreanu, Societate Civilă de Avocați</b>
    · <a href="https://www.pimasociates.ro/" target="_blank" rel="noopener" style="color:var(--red)">pimasociates.ro</a>
    · Edition generated automatically · The gazette is refreshed after each weekly run.</p>
    <div class="folio"><span>Sources &amp; Masthead</span><span>End of edition</span></div>`;
}

function countsFor(items) {
  const now = Date.now();
  return {
    total: items.length,
    week: items.filter((it) => now - Date.parse(it.published_at || it.fetched_at) < 7 * 864e5).length,
    high: items.filter((it) => it.impact === "high").length,
    countries: new Set(items.flatMap((it) => it.countries || [])).size,
  };
}

/* ---- render the flip-book from `faces` ---- */
function renderBook() {
  const book = $("book");
  let html = "";
  for (let i = 0; i < faces.length; i += 2) {
    const front = faces[i], back = faces[i + 1] || { html: "", folio: "" };
    html += `<div class="sheet">
      <div class="face front"><div class="face-inner">${front.html || folioOnly(front)}</div></div>
      <div class="face back"><div class="face-inner">${back.html || folioOnly(back)}</div></div>
    </div>`;
  }
  book.innerHTML = html;
  TOTAL = book.querySelectorAll(".sheet").length;
  // corners + internal goto links
  book.querySelectorAll(".corner").forEach((c) => c.addEventListener("click", (e) => {
    e.stopPropagation(); if (flipped < TOTAL) { flipped++; render(); }
  }));
  book.querySelectorAll("[data-goto]").forEach((el) =>
    el.addEventListener("click", () => goTo(+el.dataset.goto)));
}
function folioOnly(f) { return f && f.folio ? `<div class="folio"><span>${esc(f.folio)}</span><span></span></div>` : ""; }

function renderSideTOC(tocEntries) {
  const cover = `<li data-goto="0"><span class="pg">p. 1</span><span class="toc-nm">Cover · Executive Brief</span></li>`;
  const items = tocEntries.map((t) =>
    `<li data-goto="${gotoFor(t.faceIndex)}"><span class="pg">p. ${pageNo(t.faceIndex)}</span><span class="toc-nm">${esc(t.short)}</span><span class="cnt">${t.count}</span></li>`).join("");
  const srcFace = faces.findIndex((f) => f.kind === "sources");
  const src = srcFace >= 0 ? `<li data-goto="${gotoFor(srcFace)}"><span class="pg">p. ${pageNo(srcFace)}</span><span class="toc-nm">Sources &amp; Status</span></li>` : "";
  $("tocSide").innerHTML = cover + items + src;
  $("tocSide").querySelectorAll("li").forEach((li) => li.addEventListener("click", () => goTo(+li.dataset.goto)));
}

/* ---- flip mechanics ---- */
function render() {
  const sheets = [...$("book").querySelectorAll(".sheet")];
  sheets.forEach((s, i) => {
    s.classList.toggle("flipped", i < flipped);
    s.style.zIndex = i < flipped ? 10 + i : 40 - i;
  });
  $("prev").disabled = flipped === 0;
  $("next").disabled = flipped >= TOTAL;
  const totalPages = faces.length;
  $("pos").textContent = flipped === 0 ? "Cover · p. 1"
    : flipped >= TOTAL ? `Last page · p. ${totalPages}`
    : `Pages ${flipped * 2}–${flipped * 2 + 1}`;
  document.querySelectorAll("#tocSide li").forEach((li) => li.classList.toggle("on", +li.dataset.goto === flipped));
}
function goTo(target) {
  target = Math.min(Math.max(target, 0), TOTAL);
  const step = () => {
    if (flipped < target) { flipped++; render(); setTimeout(step, 240); }
    else if (flipped > target) { flipped--; render(); setTimeout(step, 240); }
  };
  step();
}

/* ---- filters UI ---- */
function fillSelect(id, label, values, sel) {
  $(id).innerHTML = `<option value="">${esc(label)}</option>` +
    values.map(([v, l]) => `<option value="${esc(v)}"${v === sel ? " selected" : ""}>${esc(l)}</option>`).join("");
}
function counts(get) {
  const m = new Map();
  for (const it of ITEMS) for (const v of [].concat(get(it) || [])) if (v) m.set(v, (m.get(v) || 0) + 1);
  return [...m.entries()].sort((a, b) => b[1] - a[1]);
}
function initFilters() {
  fillSelect("f-period", "Period", PERIODS.map(([v, l]) => [v, l]), state.period);
  fillSelect("f-country", "All countries", counts((i) => i.countries).map(([v, n]) => [v, `${v} (${n})`]));
  fillSelect("f-lang", "All languages", counts((i) => i.lang).map(([v, n]) => [v, `${v.toUpperCase()} (${n})`]));
  fillSelect("f-entity", "All entities", counts((i) => i.entities).slice(0, 60).map(([v, n]) => [v, `${v} (${n})`]));
  fillSelect("f-brand", "All brands", counts((i) => i.brands).slice(0, 40).map(([v, n]) => [v, `${v} (${n})`]));
  fillSelect("f-impact", "All impact levels", [["high", "High"], ["medium", "Medium"], ["low", "Low"]]);
  fillSelect("f-confidence", "All confidence levels", Object.entries(CONF_LABELS));
}
function syncFcount() {
  const n = ["country", "lang", "entity", "brand", "impact", "confidence"].filter((k) => state[k]).length
    + (state.period !== DEFAULT_PERIOD ? 1 : 0)
    + ((state.from || state.to) ? 1 : 0);
  $("fcount").textContent = `${n} active`;
}
function readFilters() {
  state.period = $("f-period").value || DEFAULT_PERIOD;
  state.from = $("f-from").value;
  state.to = $("f-to").value;
  state.country = $("f-country").value;
  state.lang = $("f-lang").value;
  state.entity = $("f-entity").value;
  state.brand = $("f-brand").value;
  state.impact = $("f-impact").value;
  state.confidence = $("f-confidence").value;
}

/* ---- chrome meta + side stats ---- */
function renderChrome(items) {
  const c = countsFor(items);
  $("chrome-meta").innerHTML = [
    META.generated_at ? `Updated <b>${esc(META.generated_at.replace("T", " ").slice(0, 16))} UTC</b>` : "No data yet",
    META.week ? `Week <b>${esc(META.week)}</b>` : "",
  ].filter(Boolean).map((s) => `<span>${s}</span>`).join("");
  $("chrome-stats").innerHTML = [
    [c.total, "items"], [c.week, "new · 7d"], [c.high, "high impact", true], [c.countries, "countries"],
  ].map(([v, l, hot]) => `<div class="stat-chip${hot ? " red" : ""}"><b>${v}</b><span>${esc(l)}</span></div>`).join("");
}

/* ---- search ---- */
function runSearch() {
  const q = $("q").value.trim();
  const sr = $("sr");
  if (!q) { sr.classList.remove("open"); return; }
  const ids = searchIds(q);
  const inWindow = new Set(pool().map((it) => it.id));
  const hits = ids === null ? [] : [...ids].map((i) => ITEMS[i])
    .sort((a, b) => (b.relevance || 0) - (a.relevance || 0));
  const visible = hits.filter((it) => inWindow.has(it.id));
  $("sr-hd").textContent = `${hits.length} result(s) for “${q}” — ${visible.length} in the current edition`;
  if (!hits.length) {
    $("sr-list").innerHTML = `<li>No matches. Try broadening the period filter to search the full 12-month archive.</li>`;
  } else {
    $("sr-list").innerHTML = hits.slice(0, 40).map((it) => {
      const f = itemFace.get(it.id);
      const jump = inWindow.has(it.id) && f != null
        ? `<a data-goto="${gotoFor(f)}">${esc(it.title_en || it.title)}</a>`
        : `<a href="${esc(it.url)}" target="_blank" rel="noopener">${esc(it.title_en || it.title)}</a>`;
      const loc = inWindow.has(it.id) && f != null ? `jump to p.${pageNo(f)}` : "outside current filters — opens source";
      return `<li>${jump}<div class="sr-meta">${esc(it.source_name)} · ${fmtDate(it.published_at)} · ${loc}</div></li>`;
    }).join("");
  }
  sr.classList.add("open");
  $("sr-list").querySelectorAll("[data-goto]").forEach((a) =>
    a.addEventListener("click", () => { goTo(+a.dataset.goto); sr.classList.remove("open"); }));
}

/* ---- PDF export: build a clean, paginated print view of the current filtered edition,
   then open the browser print dialog (the reader chooses "Save as PDF"). Vector text,
   clickable source links, zero dependencies. ---- */
function rangeLabel() {
  if (state.from || state.to) return `${state.from || "start"} to ${state.to || "today"}`;
  const p = PERIODS.find((x) => x[0] === state.period);
  return p ? p[1] : "current selection";
}
function activeFilterLabel() {
  const bits = [];
  for (const [k, lab] of [["country", "Country"], ["lang", "Language"], ["entity", "Entity"],
    ["brand", "Brand"], ["impact", "Impact"], ["confidence", "Confidence"]]) {
    if (state[k]) bits.push(`${lab}: ${state[k]}`);
  }
  return bits.join(" · ");
}
function printItemHTML(it, section) {
  const tags = [...(it.countries || []).slice(0, 5), ...(it.brands || []).slice(0, 3),
    it.lang && it.lang !== "en" ? "orig: " + it.lang.toUpperCase() : ""].filter(Boolean)
    .map((x) => `<span class="p-chip">${esc(x)}</span>`).join("");
  return `<article class="p-item">
    <h3><a href="${esc(it.url)}">${esc(it.title_en || it.title)}</a></h3>
    <div class="p-by"><b>${esc(section)}</b> · ${fmtDate(it.published_at)} · ${esc(it.source_name)}
      · ${esc(IMPACT_LABEL[it.impact] || it.impact)} · ${esc(CONF_LABELS[it.confidence] || it.confidence)}</div>
    ${it.summary_en ? `<p class="p-sum">${esc(it.summary_en)}</p>` : ""}
    <div class="p-tags">${tags}</div>
    <div class="p-src">Source: ${esc(it.url)}</div>
  </article>`;
}
function printSection(title, items, section) {
  if (!items.length) return "";
  return `<section class="p-section"><h2 class="p-h2">${esc(title)}</h2>${
    items.map((it) => printItemHTML(it, section || title)).join("")}</section>`;
}
function printTeaserHTML(it) {
  return `<div class="p-teaser"><a href="${esc(it.url)}"><b>${esc(it.title_en || it.title)}</b></a>
    <span class="p-teaser-m"> — ${esc(it.source_name)} · ${fmtDate(it.published_at)} · ${esc(CONF_LABELS[it.confidence] || it.confidence)}</span></div>`;
}
function printCompactSection(title, items) {
  if (!items.length) return "";
  return `<section class="p-section"><h2 class="p-h2">${esc(title)}</h2>${
    items.map(printTeaserHTML).join("")}</section>`;
}
function buildPrintView(items) {
  const wk = (BRIEF && BRIEF.week) || META.week || "";
  let html = `<div class="p-masthead">
      <div class="p-ears"><span>EU/EEA Edition · Week ${esc(wk)}</span>
        <span>Provided by <span class="p-firm">Păcuraru Iliescu Măzăreanu</span>, Attorneys at Law</span></div>
      <h1>THE <span class="p-red">JDE PEET'S</span> GAZETTE</h1>
      <div class="p-tag">Weekly business, legal &amp; regulatory monitor — European Union &amp; European Economic Area</div>
      <div class="p-dateline">Generated ${esc(fmtDate(META.generated_at))} · Edition period: ${esc(rangeLabel())}
        · ${items.length} item(s)${activeFilterLabel() ? " · " + esc(activeFilterLabel()) : ""}</div>
    </div>`;
  if (BRIEF && BRIEF.text) {
    html += `<section class="p-section p-brief"><h2 class="p-h2">Executive Brief</h2>
      <p>${esc(BRIEF.text).replace(/\n\n+/g, "</p><p>")}</p></section>`;
  }
  // High-Impact Alerts + Press Review are compact reference lists (items appear in full once,
  // under their thematic section) — mirrors the on-screen edition and avoids duplication.
  html += printCompactSection("High-Impact Alerts", items.filter((it) => it.impact === "high").sort(byRel));
  for (const g of GROUPS) {
    const gi = items.filter((it) => groupOf(it) === g.key).sort(byRel);
    html += printSection(g.short, gi, g.short);
  }
  html += printCompactSection("Press Review",
    items.filter((it) => ["press", "trade_press"].includes(it.source_type)).sort(byRel));
  html += `<div class="p-foot"><b>Provided by <span class="p-firm">Păcuraru Iliescu Măzăreanu</span>,
      Societate Civilă de Avocați</b> · www.pimasociates.ro<br>
    This publication aggregates publicly available information and machine-generated summaries for
    monitoring purposes only. It is not legal advice. Each item is labelled by confidence level;
    always verify against the original source. Content of external sources belongs to their publishers.</div>`;
  $("print-view").innerHTML = html;
}
function printPDF() {
  buildPrintView(pool());
  window.print();
}

/* ---- init ---- */
function bind() {
  $("next").addEventListener("click", () => { if (flipped < TOTAL) { flipped++; render(); } });
  $("prev").addEventListener("click", () => { if (flipped > 0) { flipped--; render(); } });
  document.addEventListener("keydown", (e) => {
    if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT") return;
    if (e.key === "ArrowRight") $("next").click();
    if (e.key === "ArrowLeft") $("prev").click();
  });
  $("btn-search").addEventListener("click", runSearch);
  $("q").addEventListener("keydown", (e) => { if (e.key === "Enter") runSearch(); });
  $("sr-close").addEventListener("click", () => $("sr").classList.remove("open"));
  $("f-apply").addEventListener("click", () => { readFilters(); syncFcount(); const items = buildEdition(); renderChrome(items); });
  $("f-reset").addEventListener("click", () => {
    Object.assign(state, { q: "", period: DEFAULT_PERIOD, from: "", to: "", country: "", lang: "", entity: "", brand: "", impact: "", confidence: "" });
    $("q").value = ""; $("f-from").value = ""; $("f-to").value = "";
    initFilters(); syncFcount(); const items = buildEdition(); renderChrome(items);
  });
  $("btn-pdf").addEventListener("click", printPDF);
  $("toggle-side").addEventListener("click", () => {
    const collapsed = document.querySelector(".layout").classList.toggle("side-collapsed");
    $("toggle-side").innerHTML = collapsed ? "▨ Show filters" : "◀ Hide filters";
    $("toggle-side").setAttribute("aria-expanded", String(!collapsed));
    fit();
    setTimeout(fit, 60);
  });
}
function fit() {
  const wrap = document.querySelector(".stage-wrap");
  const stage = document.querySelector(".stage");
  const sc = $("scaler");
  // width from the actual column; height from where the book area starts (below the topbar)
  const availW = wrap.clientWidth - 12;
  const availH = window.innerHeight - stage.getBoundingClientRect().top - 72;  // room for the pager
  // fill the available space by width AND height; allow the spread to grow up to 1.85x for readability
  const s = Math.max(0.2, Math.min(availW / 1000, availH / 680, 1.85));
  sc.style.transform = `scale(${s})`;
  sc.style.width = (1000 * s) + "px";
  sc.style.height = (680 * s + 6) + "px";
}

async function main() {
  [ITEMS, SOURCES, META, BRIEF] = await Promise.all([
    loadJSON("data/items.json", []), loadJSON("data/sources.json", []),
    loadJSON("data/meta.json", {}), loadJSON("data/brief.json", null),
  ]);
  buildIndex();
  initFilters(); syncFcount(); bind();
  const items = buildEdition();
  renderChrome(items);
  fit();
  setTimeout(fit, 250);   // re-fit once fonts/layout settle
  window.addEventListener("resize", fit);
}
main();
