"use strict";

const MONTHS_NO = ["jan", "feb", "mar", "apr", "mai", "jun", "jul", "aug", "sep", "okt", "nov", "des"];
const RANGES = [["1y", "1 år", 12], ["2y", "2 år", 24], ["5y", "5 år", 60], ["10y", "10 år", 120], ["all", "Alt", Infinity]];
const COUNTRIES = { "United States": "USA", Canada: "Canada" };
const DRILL = [["Oil", "Olje"], ["Gas", "Gass"], ["Miscellaneous", "Annet"]];
const LOC = [["Land", "Land"], ["Offshore", "Offshore"], ["Inland Waters", "Innlandsvann"]];

const state = { data: null, country: "United States", range: "10y" };
const $ = (id) => document.getElementById(id);
const fmt = (v, d = 0) => (v == null ? "–" : v.toLocaleString("nb-NO", { maximumFractionDigits: d, minimumFractionDigits: d }));
const label = (d) => { const [y, m] = d.split("-"); return `${MONTHS_NO[+m - 1]} ${y}`; };
const signed = (d, digits = 0) => (d == null ? "–" : (d > 0 ? "+" : d < 0 ? "−" : "±") + fmt(Math.abs(d), digits));

fetch("data/worldwide.json", { cache: "no-cache" })
  .then((r) => (r.ok ? r.json() : null)).catch(() => null)
  .then((data) => {
    if (!data || !data.detail || !Object.keys(data.detail).length) { $("empty").hidden = false; return; }
    state.data = data;
    if (!data.detail[state.country]) state.country = Object.keys(data.detail)[0];
    $("app").hidden = false;
    renderControls();
    render();
    let t; window.addEventListener("resize", () => { clearTimeout(t); t = setTimeout(renderCharts, 120); });
  });

function det() { return state.data.detail[state.country]; }
function lastIndex(a) { for (let i = a.length - 1; i >= 0; i--) if (a[i]) return i; return -1; }

function renderControls() {
  const seg = (el, items, key) => {
    el.innerHTML = "";
    for (const [val, text] of items) {
      const b = document.createElement("button");
      b.type = "button"; b.textContent = text;
      b.setAttribute("aria-pressed", String(state[key] === val));
      b.onclick = () => { state[key] = val; renderControls(); render(); };
      el.appendChild(b);
    }
  };
  seg($("country-ctl"), Object.keys(state.data.detail).map((c) => [c, COUNTRIES[c] || c]), "country");
  const len = state.data.dates.length;
  seg($("range-ctl"), RANGES.filter((r) => r[2] < len || r[0] === "all").map(([k, t]) => [k, t]), "range");
}

function render() {
  const name = COUNTRIES[state.country] || state.country;
  $("title").textContent = `${name} Rig Count`;
  document.title = `${name} Rig Count`;
  renderTiles();
  renderCharts();
  renderTable();
  const m = state.data.meta || {};
  $("foot").textContent = `Data ${label(m.first)} – ${label(m.last)} · Kilde: Baker Hughes Worldwide Rig Count (månedlige snitt, derfor desimaler) · ` +
    "Ukentlige tall per delstat/basseng krever Baker Hughes' North America-fil.";
}

// ------------------------------------------------------------- nøkkeltall
function renderTiles() {
  const d = det(), dates = state.data.dates, i = lastIndex(d.total);
  const off = (d.location.Offshore || []).map((v, k) => v + ((d.location["Inland Waters"] || [])[k] || 0));
  const tiles = [
    ["Totalt", d.total],
    ["Olje", d.drill_for.Oil || []],
    ["Gass", d.drill_for.Gas || []],
    [d.location["Inland Waters"] ? "Offshore + innlandsvann" : "Offshore", off],
  ];
  $("tiles").innerHTML = tiles.map(([n, a]) => {
    const share = n !== "Totalt" && d.total[i] ? ` · ${fmt((a[i] / d.total[i]) * 100)} % av totalt` : "";
    const dm = i >= 1 ? a[i] - a[i - 1] : null, dy = i >= 12 ? a[i] - a[i - 12] : null;
    const cls = (x) => (x > 0 ? "up" : x < 0 ? "down" : "");
    return `<div class="tile"><div class="label">${n} · ${label(dates[i])}</div>
      <div class="value">${fmt(a[i])}</div>
      <div class="delta"><span class="${cls(dm)}">${signed(dm)}</span> m/m &nbsp; <span class="${cls(dy)}">${signed(dy)}</span> å/å</div>
      ${share ? `<div class="share">${share.slice(3)}</div>` : ""}</div>`;
  }).join("");
}

// ------------------------------------------------------------- grafer
function windowed() {
  const d = det(), all = state.data.dates;
  const end = lastIndex(d.total);
  const n = RANGES.find((r) => r[0] === state.range)[2];
  const start = Math.max(0, end + 1 - n);
  return { start, end, dates: all.slice(start, end + 1), cut: (a) => (a || []).slice(start, end + 1) };
}

function renderCharts() {
  const d = det(), w = windowed();
  const drill = DRILL.filter(([k]) => d.drill_for[k]).map(([k, n], j) => ({ name: n, color: `var(--s${j + 1})`, values: w.cut(d.drill_for[k]) }));
  $("legend-drill").innerHTML = legend(drill);
  chart($("chart-drill"), w.dates, drill, { stack: true, total: true, height: 320 });

  const oil = w.cut(d.drill_for.Oil), tot = w.cut(d.total);
  const share = [{ name: "Andel olje", color: "var(--s1)", values: oil.map((v, k) => (tot[k] ? (v / tot[k]) * 100 : null)) }];
  chart($("chart-share"), w.dates, share, { height: 220, unit: " %", yMax: 100, digits: 0 });

  const offs = LOC.filter(([k]) => k !== "Land" && d.location[k]).map(([k, n], j) => ({ name: n, color: `var(--s${j + 2})`, values: w.cut(d.location[k]) }));
  $("off-title").textContent = offs.length > 1 ? "Offshore og innlandsvann" : "Offshore";
  $("legend-off").innerHTML = offs.length > 1 ? legend(offs) : "";
  chart($("chart-off"), w.dates, offs, { height: 220, digits: 1 });
}

function legend(series) {
  return series.map((s) => `<li><span class="sw" style="background:${s.color}"></span>${s.name}</li>`).join("");
}

/** Enkel SVG-graf: stablet areal (stack) eller linjer, med krysshår og verktøytips. */
function chart(wrap, dates, series, opt = {}) {
  const W = Math.max(300, wrap.clientWidth), H = W < 520 ? Math.min(opt.height || 260, 240) : (opt.height || 260);
  const m = { t: 8, r: 10, b: 26, l: 42 };
  const iw = W - m.l - m.r, ih = H - m.t - m.b;
  const n = dates.length;

  let layers = series.map((s) => ({ ...s, lo: s.values.map(() => 0), hi: s.values.map((v) => v || 0) }));
  if (opt.stack) {
    let acc = dates.map(() => 0);
    layers = series.map((s) => { const lo = acc; const hi = acc.map((a, i) => a + (s.values[i] || 0)); acc = hi; return { ...s, lo, hi }; });
  }
  const top = Math.max(1, ...layers.flatMap((l) => l.hi.filter((v) => v != null)));
  const raw = opt.yMax || top * 1.05;
  const p10 = Math.pow(10, Math.floor(Math.log10(raw / 4)));
  const step = [1, 2, 2.5, 5, 10].map((f) => f * p10).find((s) => s * 4 >= raw) || 10 * p10;
  const ymax = opt.yMax || step * Math.ceil(raw / step);
  const x = (i) => m.l + (n < 2 ? 0 : (i / (n - 1)) * iw);
  const y = (v) => m.t + ih - (v / ymax) * ih;
  const tStep = opt.yMax ? opt.yMax / 4 : step;
  const ticks = []; for (let t = 0; t <= ymax + 1e-9; t += tStep) ticks.push(t);

  const short = n <= 36;
  const cand = dates.map((d, i) => [d, i]).filter(([d]) => (short ? /-(01|04|07|10)$/ : /-01$/).test(d));
  const every = Math.ceil(cand.length / Math.max(2, Math.floor(iw / (short ? 64 : 48))));
  const xt = cand.filter((_, k) => k % every === 0);
  const anchor = (i) => (x(i) > W - 36 ? "end" : x(i) < m.l + 16 ? "start" : "middle");

  const pts = (a) => a.map((v, i) => (v == null ? null : `${x(i).toFixed(1)},${y(v).toFixed(1)}`));
  const marks = layers.map((l) => {
    if (opt.stack) {
      const up = pts(l.hi).join(" L"), dn = pts(l.lo).reverse().join(" L");
      return `<path d="M${up} L${dn} Z" fill="${l.color}" stroke="var(--surface-1)" stroke-width="2" stroke-linejoin="round"/>`;
    }
    const segs = []; let cur = [];
    pts(l.values).forEach((p) => { if (p) cur.push(p); else if (cur.length) { segs.push(cur); cur = []; } });
    if (cur.length) segs.push(cur);
    return segs.map((s) => `<path d="M${s.join(" L")}" fill="none" stroke="${l.color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>`).join("");
  }).join("");

  const unit = opt.unit || "", dg = opt.digits ?? 0;
  wrap.innerHTML = `
  <svg viewBox="0 0 ${W} ${H}" role="img">
    <g class="grid">${ticks.map((t) => `<line x1="${m.l}" x2="${W - m.r}" y1="${y(t)}" y2="${y(t)}"/>`).join("")}</g>
    <g class="axis">
      ${ticks.map((t) => `<text x="${m.l - 6}" y="${y(t) + 4}" text-anchor="end">${fmt(t, ymax < 10 ? 1 : 0)}${unit.trim()}</text>`).join("")}
      ${xt.map(([d, i]) => `<text x="${x(i)}" y="${H - 6}" text-anchor="${anchor(i)}">${short ? label(d) : d.slice(0, 4)}</text>`).join("")}
    </g>
    ${marks}
    <line class="baseline" x1="${m.l}" x2="${W - m.r}" y1="${y(0)}" y2="${y(0)}"/>
    <line class="crosshair" y1="${m.t}" y2="${m.t + ih}" visibility="hidden"/>
    <g class="dots"></g>
    <rect x="${m.l}" y="${m.t}" width="${iw}" height="${ih}" fill="transparent"/>
  </svg>`;

  const svg = wrap.querySelector("svg"), xh = svg.querySelector(".crosshair"), dots = svg.querySelector(".dots");
  const tip = wrap.parentElement.querySelector(".tooltip"), hit = svg.querySelector("rect");
  const move = (ev) => {
    const box = svg.getBoundingClientRect();
    const px = ((ev.clientX - box.left) / box.width) * W;
    const i = Math.max(0, Math.min(n - 1, Math.round(((px - m.l) / iw) * (n - 1))));
    xh.setAttribute("x1", x(i)); xh.setAttribute("x2", x(i)); xh.setAttribute("visibility", "visible");
    dots.innerHTML = opt.stack ? "" : layers.filter((l) => l.values[i] != null)
      .map((l) => `<circle cx="${x(i)}" cy="${y(l.values[i])}" r="4" fill="${l.color}" stroke="var(--surface-1)" stroke-width="2"/>`).join("");
    const rows = [...layers].reverse().map((l) =>
      `<div class="row"><span><span style="display:inline-block;width:8px;height:8px;border-radius:2px;background:${l.color}"></span>${l.name}</span><b>${fmt(l.values[i], dg)}${unit}</b></div>`).join("");
    const sum = opt.total ? `<div class="row total"><span>Sum</span><b>${fmt(layers.reduce((a, l) => a + (l.values[i] || 0), 0))}</b></div>` : "";
    tip.innerHTML = `<div class="t-head">${label(dates[i])}</div>${rows}${sum}`;
    tip.hidden = false;
    const card = wrap.parentElement.getBoundingClientRect();
    const sx = (x(i) / W) * box.width + box.left - card.left;
    const left = sx + 14 + tip.offsetWidth > card.width ? sx - 14 - tip.offsetWidth : sx + 14;
    tip.style.left = `${Math.max(4, left)}px`;
    tip.style.top = `${box.top - card.top + 8}px`;
  };
  hit.addEventListener("pointermove", move);
  hit.addEventListener("pointerdown", move);
  hit.addEventListener("pointerleave", () => { tip.hidden = true; xh.setAttribute("visibility", "hidden"); dots.innerHTML = ""; });
}

// ------------------------------------------------------------- tabell
function renderTable() {
  const d = det(), dates = state.data.dates, end = lastIndex(d.total);
  const cols = [
    ...DRILL.filter(([k]) => d.drill_for[k]).map(([k, n]) => [n, d.drill_for[k]]),
    ...LOC.filter(([k]) => d.location[k]).map(([k, n]) => [n, d.location[k]]),
    ["Totalt", d.total],
  ];
  $("table").querySelector("thead").innerHTML =
    `<tr><th>Måned</th>${cols.map(([n]) => `<th class="num">${n}</th>`).join("")}<th class="num">Totalt å/å</th></tr>`;
  const rows = [];
  for (let i = end; i >= Math.max(0, end - 23); i--) {
    const yy = i >= 12 ? d.total[i] - d.total[i - 12] : null;
    rows.push(`<tr><td>${label(dates[i])}</td>${cols.map(([, a]) => `<td class="num">${fmt(a[i], 1)}</td>`).join("")}` +
      `<td class="num ${yy > 0 ? "up" : yy < 0 ? "down" : ""}">${signed(yy, 1)}</td></tr>`);
  }
  $("table").querySelector("tbody").innerHTML = rows.join("");
}
