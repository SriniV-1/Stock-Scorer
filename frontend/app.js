"use strict";

const form = document.getElementById("search-form");
const input = document.getElementById("ticker-input");
const loading = document.getElementById("loading");
const loadingText = document.getElementById("loading-text");
const errorBox = document.getElementById("error");
const errorText = document.getElementById("error-text");
const report = document.getElementById("report");

const LOADING_LINES = [
  "Pulling fundamentals and assembling peer set…",
  "Computing peer-relative percentiles…",
  "Scoring metrics and aggregating categories…",
  "Applying contextual adjustments…",
];

let loadingTimer = null;

function show(el) { el.classList.remove("hidden"); }
function hide(el) { el.classList.add("hidden"); }

function scoreColor(s) {
  if (s == null) return "var(--ink-faint)";
  if (s >= 70) return "var(--good)";
  if (s >= 45) return "var(--mid)";
  return "var(--bad)";
}

function fmtValue(name, v) {
  if (v == null || Number.isNaN(v)) return "—";
  // Ratios that come through as fractions read better as percentages.
  const pctMetrics = [
    "revenue_growth", "eps_growth", "roe",
    "operating_margin", "net_margin",
  ];
  if (pctMetrics.includes(name)) return (v * 100).toFixed(1) + "%";
  return Number(v).toFixed(2);
}

function fmtPercentile(p) {
  if (p == null) return "—";
  const r = Math.round(p);
  const suffix =
    r % 10 === 1 && r % 100 !== 11 ? "st" :
    r % 10 === 2 && r % 100 !== 12 ? "nd" :
    r % 10 === 3 && r % 100 !== 13 ? "rd" : "th";
  return r + suffix;
}

function startLoading() {
  hide(errorBox); hide(report); show(loading);
  let i = 0;
  loadingText.textContent = LOADING_LINES[0];
  loadingTimer = setInterval(() => {
    i = (i + 1) % LOADING_LINES.length;
    loadingText.textContent = LOADING_LINES[i];
  }, 2200);
}

function stopLoading() {
  hide(loading);
  if (loadingTimer) { clearInterval(loadingTimer); loadingTimer = null; }
}

function countUp(el, target) {
  const dur = 900, t0 = performance.now();
  function frame(now) {
    const p = Math.min((now - t0) / dur, 1);
    const eased = 1 - Math.pow(1 - p, 3);
    el.textContent = (target * eased).toFixed(1);
    if (p < 1) requestAnimationFrame(frame);
    else el.textContent = target.toFixed(1);
  }
  requestAnimationFrame(frame);
}

function render(data, scroll = true) {
  // Header
  document.getElementById("r-ticker").textContent = data.ticker;
  const nameEl = document.getElementById("r-name");
  if (data.name) { nameEl.textContent = data.name; nameEl.classList.remove("hidden"); }
  else { nameEl.classList.add("hidden"); }
  document.getElementById("r-summary").textContent = data.summary;
  const when = new Date(data.timestamp);
  document.getElementById("r-meta").textContent =
    `${data.peer_count} peers · scored ${when.toLocaleString()}` +
    (data.cached ? " · cached" : "");

  // Score box
  countUp(document.getElementById("r-score"), data.final_score);
  const rating = document.getElementById("r-rating");
  rating.textContent = data.rating;
  rating.style.color = scoreColor(data.final_score);
  document.querySelector(".scorebox-num").style.color = scoreColor(data.final_score);

  // Verdict
  document.getElementById("r-action").textContent = data.action;

  // Warnings
  const warnWrap = document.getElementById("r-warnings");
  const warnList = document.getElementById("r-warnings-list");
  warnList.innerHTML = "";
  if (data.warnings && data.warnings.length) {
    data.warnings.forEach((w) => {
      const li = document.createElement("li");
      li.textContent = w;
      warnList.appendChild(li);
    });
    show(warnWrap);
  } else {
    hide(warnWrap);
  }

  // Categories
  const cats = document.getElementById("r-categories");
  cats.innerHTML = "";
  data.categories.forEach((c, idx) => {
    const row = document.createElement("div");
    row.className = "cat";
    row.style.animationDelay = `${idx * 80}ms`;
    row.innerHTML = `
      <div>
        <div class="cat-name">${c.name}</div>
        <div class="cat-weight">weight ${(c.weight * 100).toFixed(0)}% · +${c.contribution} pts</div>
      </div>
      <div class="cat-track"><div class="cat-fill"></div></div>
      <div class="cat-score">${c.score.toFixed(1)}</div>`;
    cats.appendChild(row);
    const fill = row.querySelector(".cat-fill");
    fill.style.background = scoreColor(c.score);
    requestAnimationFrame(() => { fill.style.width = `${c.score}%`; });
  });

  // Metric tables
  const wrap = document.getElementById("r-metrics");
  wrap.innerHTML = "";
  data.categories.forEach((c) => {
    const group = document.createElement("div");
    group.className = "mt-group";
    const rows = c.metrics.map((m) => `
      <tr>
        <td>
          <div class="metric-name">${m.display_name}</div>
          <div class="metric-desc">${m.description}${m.lower_is_better ? " · lower is better" : ""}</div>
        </td>
        <td class="num">${fmtValue(m.name, m.raw_value)}</td>
        <td class="num">${fmtPercentile(m.percentile)}</td>
        <td class="num">
          <span class="score-pill" style="background:${scoreColor(m.score)}">
            ${m.score == null ? "—" : m.score.toFixed(0)}
          </span>
        </td>
      </tr>`).join("");
    group.innerHTML = `
      <h4>${c.name}</h4>
      <table class="mt">
        <thead>
          <tr>
            <th>Metric</th>
            <th class="num">Value</th>
            <th class="num">Pctile</th>
            <th class="num">Score</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>`;
    wrap.appendChild(group);
  });

  show(report);
  if (scroll) report.scrollIntoView({ behavior: "smooth", block: "start" });
  refreshLeaderboard();
  loadReportNews(data.ticker);
}

async function loadReportNews(ticker) {
  const wrap = document.getElementById("r-news");
  const label = document.getElementById("r-news-label");
  wrap.innerHTML = ""; label.classList.add("hidden");
  try {
    const res = await fetch(`/api/news/${encodeURIComponent(ticker)}?n=6`);
    if (!res.ok) return;
    const { articles } = await res.json();
    if (!articles || !articles.length) return;
    articles.forEach((a) => {
      const el = document.createElement(a.link ? "a" : "div");
      el.className = "news-item";
      if (a.link) { el.href = a.link; el.target = "_blank"; el.rel = "noopener"; }
      const when = a.published ? new Date(a.published) : null;
      const meta = [a.publisher, when && !isNaN(when) ? when.toLocaleDateString() : null]
        .filter(Boolean).join(" · ");
      el.innerHTML =
        `<span class="news-title">${a.title}</span>` +
        (meta ? `<span class="news-meta">${meta}</span>` : "");
      wrap.appendChild(el);
    });
    label.classList.remove("hidden");
  } catch (_) { /* ignore */ }
}

async function analyze(ticker, opts = {}) {
  const { scroll = true } = opts;
  ticker = (ticker || "").trim().toUpperCase();
  if (!ticker) return;
  startLoading();
  try {
    const res = await fetch(`/api/score/${encodeURIComponent(ticker)}`);
    stopLoading();
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      errorText.textContent =
        body.detail || `Could not score ${ticker}. Please try another symbol.`;
      show(errorBox);
      return;
    }
    const data = await res.json();
    render(data, scroll);
  } catch (e) {
    stopLoading();
    errorText.textContent =
      "Network error reaching the scoring service. Is the API running?";
    show(errorBox);
  }
}

// ---- Top-scored leaderboard (right rail) ----
const lbItems = document.getElementById("lb-items");

async function refreshLeaderboard() {
  try {
    const res = await fetch("/api/leaderboard?n=10");
    if (!res.ok) return;
    const { top, total } = await res.json();
    const totalEl = document.getElementById("lb-total");
    if (totalEl) totalEl.textContent = total ? `${total} analyzed` : "";
    if (!top || !top.length) { lbItems.innerHTML = '<div class="rail-empty">Scoring universe…</div>'; return; }
    lbItems.innerHTML = "";
    top.forEach((s, i) => {
      const el = document.createElement("div");
      el.className = "rail-item";
      el.setAttribute("role", "button");
      el.style.setProperty("--c", scoreColor(s.final_score));
      el.innerHTML =
        `<div class="rail-row1">` +
          `<span class="rail-rank">${i + 1}</span>` +
          `<span class="rail-ticker">${s.ticker}</span>` +
          `<span class="rail-score">${s.final_score.toFixed(1)}</span>` +
        `</div>` +
        `<div class="rail-bar"><span style="width:${s.final_score}%"></span></div>`;
      el.title = `${s.name ? s.name + " — " : ""}${s.rating} (${s.final_score.toFixed(1)}/100)`;
      el.addEventListener("click", () => { input.value = s.ticker; analyze(s.ticker); });
      lbItems.appendChild(el);
      loadRailHeadline(s.ticker, el);  // every ranked stock gets a headline
    });
  } catch (_) { /* ignore */ }
}

const railHeadlineCache = new Map();  // ticker -> headline {title, link}
async function loadRailHeadline(ticker, itemEl) {
  let head = railHeadlineCache.get(ticker);
  if (head === undefined) {
    try {
      const res = await fetch(`/api/news/${encodeURIComponent(ticker)}?n=1`);
      const { articles } = res.ok ? await res.json() : { articles: [] };
      head = (articles && articles[0]) || null;
    } catch (_) { head = null; }
    railHeadlineCache.set(ticker, head);
  }
  if (!head || !itemEl.isConnected) return;
  const a = document.createElement(head.link ? "a" : "div");
  a.className = "rail-news";
  if (head.link) { a.href = head.link; a.target = "_blank"; a.rel = "noopener"; }
  a.textContent = head.title;
  a.title = head.title;
  a.addEventListener("click", (e) => e.stopPropagation());  // don't trigger analyze
  itemEl.appendChild(a);
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  analyze(input.value);
});

document.querySelectorAll(".chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    input.value = chip.dataset.ticker;
    analyze(chip.dataset.ticker);
  });
});

input.focus();

// On arrival, show a featured report (top-ranked stock, else AAPL) so the page
// isn't empty — without scrolling the user away from the hero/methodology.
async function init() {
  await refreshLeaderboard();
  let featured = "AAPL";
  try {
    const r = await fetch("/api/leaderboard?n=1");
    if (r.ok) { const { top } = await r.json(); if (top && top[0]) featured = top[0].ticker; }
  } catch (_) { /* ignore */ }
  analyze(featured, { scroll: false });
}
init();

// Poll the leaderboard while the server seeds the universe in the background.
let lbPolls = 0;
const lbTimer = setInterval(() => {
  refreshLeaderboard();
  if (++lbPolls >= 24) clearInterval(lbTimer);  // ~2 min of warm-up polling
}, 5000);
