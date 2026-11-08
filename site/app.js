"use strict";

// Fast rekkefølge -> fast farge. Fargen følger regionen, aldri rangeringen.
const REGION_ORDER = ["United States", "Canada", "Latin America", "Europe", "Africa", "Middle East", "Asia Pacific"];
const MONTHS_NO = ["jan", "feb", "mar", "apr", "mai", "jun", "jul", "aug", "sep", "okt", "nov", "des"];
const RANGES = [["5y", "5 år", 60], ["10y", "10 år", 120], ["all", "Alt", Infinity]];
const NA = ["United States", "Canada"];

const state = { data: null, section: null, range: "10y", region: "" };
const $ = (id) => document.getElementById(id);
const fmt = (v) => (v == null ? "–" : Math.round(v).toLocaleString("nb-NO"));
const label = (d) => { const [y, m] = d.split("-"); return `${MONTHS_NO[+m - 1]} ${y}`; };

function colorVar(region) {
  const i = REGION_ORDER.indexOf(region);
  return i >= 0 ? `var(--s${i + 1})` : "var(--s8)";
}

fetch("data/worldwide.json", { cache: "no-cache" })
  .then((r) => (r.ok ? r.json() : null))
  .catch(() => null)
  .then((data) => {
    if (!data || !Object.keys(data.sections || {}).length) { $("empty").hidden = false; return; }
    synthTotal(data);
    state.data = data;
    const secs = Object.keys(data.sections);
    state.section = secs.includes("Total") ? "Total" : secs[0];
    $("app").hidden = false;
    renderControls();
    render();
    window.addEventListener("resize", () => renderChart());
  });

// Hvis filen bare har Land og Offshore, lag en Total-seksjon av summen.
function synthTotal(data) {
  const s = data.sections;
  if (s.Total || !s.Land || !s.Offshore) return;
  const dates = [...new Set([...s.Land.dates, ...s.Offshore.dates])].sort();
  const pick = (sec, arr) => (d) => { const i = sec.dates.indexOf(d); return i < 0 ? null : arr[i]; };
  const add = (a, b) => (a == null && b == null ? null : (a || 0) + (b || 0));
  const regions = {};
  for (const r of new Set([...Object.keys(s.Land.regions), ...Object.keys(s.Offshore.regions)])) {
    const l = pick(s.Land, s.Land.regions[r] || []), o = pick(s.Offshore, s.Offshore.regions[r] || []);
    regions[r] = dates.map((d) => add(l(d), o(d)));
  }
  const countries = {};
  for (const sec of [s.Land, s.Offshore]) for (const c of sec.countries) {
    const k = c.region + "|" + c.name;
    const p = pick(sec, c.values);
    const cur = countries[k] || { name: c.name, region: c.region, values: dates.map(() => null) };
    cur.values = cur.values.map((v, i) => add(v, p(dates[i])));
    countries[k] = cur;
  }
  const wl = s.Land.world && pick(s.Land, s.Land.world), wo = s.Offshore.world && pick(s.Offshore, s.Offshore.world);
  s.Total = { dates, regions, countries: Object.values(countries),
              world: wl && wo ? dates.map((d) => add(wl(d), wo(d))) : null };
}

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
  const secs = Object.keys(state.data.sections);
  const order = ["Total", "Land", "Offshore"];
  secs.sort((a, b) => order.indexOf(a) - order.indexOf(b));
  const names = { Total: "Totalt", Land: "Land", Offshore: "Offshore" };
  $("section-ctl").hidden = secs.length < 2;
  seg($("section-ctl"), secs.map((s) => [s, names[s] || s]), "section");
  seg($("range-ctl"), RANGES.map(([k, t]) => [k, t]), "range");
}

function sec() { return state.data.sections[state.section]; }

function worldSeries(s) {
  if (s.world) return s.world;
  return s.dates.map((_, i) => {
    const vals = Object.values(s.regions).map((v) => v[i]).filter((v) => v != null);
    return vals.length ? vals.reduce((a, b) => a + b, 0) : null;
  });
}

function lastIndex(arr) { for (let i = arr.length - 1; i >= 0; i--) if (arr[i] != null) return i; return -1; }

function delta(arr, i, back) {
  const j = i - back;
  if (j < 0 || arr[i] == null || arr[j] == null) return null;
  return arr[i] - arr[j];
}

function deltaHtml(d, suffix) {
  if (d == null) return "";
  const cls = d > 0 ? "up" : d < 0 ? "down" : "";
  const sign = d > 0 ? "+" : d < 0 ? "−" : "±";
  return `<span class="${cls}">${sign}${fmt(Math.abs(d))}</span> ${suffix}`;
}

function render() {
  renderTiles();
  renderLegend();
  renderChart();
  renderTable();
  const m = state.data.meta || {};
  $("foot").textContent = `Data ${label(m.first || sec().dates[0])} – ${label(m.last || sec().dates.at(-1))}` +
    (m.file ? ` · fil: ${m.file}` : "") + (m.built ? ` · oppdatert ${m.built.slice(0, 10)}` : "");
}

function renderTiles() {
  const s = sec();
  const world = worldSeries(s);
  const i = lastIndex(world);
  const intl = s.dates.map((_, k) => {
    if (world[k] == null) return null;
    return world[k] - NA.reduce((a, r) => a + ((s.regions[r] || [])[k] || 0), 0);
  });
  const tiles = [["Verden", world]];
  if (NA.some((r) => s.regions[r])) tiles.push(["Internasjonalt (eks. USA og Canada)", intl]);
  for (const r of ["United States", "Middle East"]) if (s.regions[r]) tiles.push([r === "United States" ? "USA" : "Midtøsten", s.regions[r]]);
  $("tiles").innerHTML = tiles.map(([name, arr]) => `
    <div class="tile">
      <div class="label">${name} · ${label(s.dates[i])}</div>
      <div class="value">${fmt(arr[i])}</div>
      <div class="delta">${deltaHtml(delta(arr, i, 1), "m/m")} &nbsp; ${deltaHtml(delta(arr, i, 12), "å/å")}</div>
    </div>`).join("");
}

function regionsInOrder(s) {
  const known = REGION_ORDER.filter((r) => s.regions[r]);
  const other = Object.keys(s.regions).filter((r) => !REGION_ORDER.includes(r));
  return [...known, ...other];
}

function renderLegend() {
  $("legend").innerHTML = regionsInOrder(sec())
    .map((r) => `<li><span class="sw" style="background:${colorVar(r)}"></span>${r}</li>`).join("");
}

function renderChart() {
  const s = sec();
  const n = RANGES.find((r) => r[0] === state.range)[2];
  const end = lastIndex(worldSeries(s));
  const start = Math.max(0, end + 1 - n);
  const dates = s.dates.slice(start, end + 1);
  const regs = regionsInOrder(s);
  const series = regs.map((r) => s.regions[r].slice(start, end + 1).map((v) => v || 0));

  // Stabling
  const stacks = []; let acc = dates.map(() => 0);
  for (const vals of series) { const top = acc.map((a, i) => a + vals[i]); stacks.push([acc, top]); acc = top; }
  const totals = acc;

  const wrap = $("chart");
  const W = Math.max(320, wrap.clientWidth), H = W < 560 ? 260 : 360;
  const m = { t: 8, r: 8, b: 26, l: 44 };
  const iw = W - m.l - m.r, ih = H - m.t - m.b;
  const ymax = niceMax(Math.max(...totals, 1));
  const x = (i) => m.l + (dates.length < 2 ? 0 : (i / (dates.length - 1)) * iw);
  const y = (v) => m.t + ih - (v / ymax) * ih;

  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * ymax);
  const yearIdx = dates.map((d, i) => [d, i]).filter(([d]) => d.endsWith("-01"));
  const every = Math.ceil(yearIdx.length / Math.max(2, Math.floor(iw / 70)));
  const xt = yearIdx.filter((_, k) => k % every === 0);

  const area = ([lo, hi]) => {
    const up = hi.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" L");
    const dn = lo.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).reverse().join(" L");
    return `M${up} L${dn} Z`;
  };

  wrap.innerHTML = `
  <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Stablet arealdiagram: rigger per region">
    <g class="grid">${ticks.map((t) => `<line x1="${m.l}" x2="${W - m.r}" y1="${y(t)}" y2="${y(t)}"/>`).join("")}</g>
    <g class="axis">
      ${ticks.map((t) => `<text x="${m.l - 6}" y="${y(t) + 4}" text-anchor="end">${fmt(t)}</text>`).join("")}
      ${xt.map(([d, i]) => `<text x="${x(i)}" y="${H - 6}" text-anchor="middle">${d.slice(0, 4)}</text>`).join("")}
    </g>
    ${stacks.map((st, k) => `<path d="${area(st)}" fill="${colorVar(regs[k])}" stroke="var(--surface-1)" stroke-width="2" stroke-linejoin="round"/>`).join("")}
    <line class="baseline" x1="${m.l}" x2="${W - m.r}" y1="${y(0)}" y2="${y(0)}"/>
    <line class="crosshair" id="xh" y1="${m.t}" y2="${m.t + ih}" visibility="hidden"/>
    <rect id="hit" x="${m.l}" y="${m.t}" width="${iw}" height="${ih}" fill="transparent"/>
  </svg>`;

  const svg = wrap.querySelector("svg"), xh = svg.querySelector("#xh"), tip = $("tip");
  const move = (ev) => {
    const pt = svg.getBoundingClientRect();
    const px = ((ev.clientX - pt.left) / pt.width) * W;
    const i = Math.max(0, Math.min(dates.length - 1, Math.round(((px - m.l) / iw) * (dates.length - 1))));
    xh.setAttribute("x1", x(i)); xh.setAttribute("x2", x(i)); xh.setAttribute("visibility", "visible");
    const rows = regs.map((r, k) => [r, series[k][i]]).reverse();
    tip.innerHTML = `<div class="t-head">${label(dates[i])}</div>` +
      rows.map(([r, v]) => `<div class="row"><span><span class="sw legend-sw" style="display:inline-block;width:8px;height:8px;border-radius:2px;background:${colorVar(r)}"></span>${r}</span><b>${fmt(v)}</b></div>`).join("") +
      `<div class="row total"><span>Sum</span><b>${fmt(totals[i])}</b></div>`;
    tip.hidden = false;
    const card = wrap.parentElement.getBoundingClientRect();
    const sx = (x(i) / W) * pt.width + pt.left - card.left;
    const left = sx + 14 + tip.offsetWidth > card.width ? sx - 14 - tip.offsetWidth : sx + 14;
    tip.style.left = `${Math.max(4, left)}px`;
    tip.style.top = `${pt.top - card.top + 8}px`;
  };
  const hit = svg.querySelector("#hit");
  hit.addEventListener("pointermove", move);
  hit.addEventListener("pointerdown", move);
  hit.addEventListener("pointerleave", () => { tip.hidden = true; xh.setAttribute("visibility", "hidden"); });
}

function niceMax(v) {
  const p = Math.pow(10, Math.floor(Math.log10(v)));
  for (const f of [1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10]) if (f * p >= v) return f * p;
  return 10 * p;
}

function renderTable() {
  const s = sec();
  const sel = $("region-sel");
  const regs = [...new Set(s.countries.map((c) => c.region).filter(Boolean))].sort();
  sel.innerHTML = `<option value="">Alle</option>` + regs.map((r) => `<option ${r === state.region ? "selected" : ""}>${r}</option>`).join("");
  sel.onchange = () => { state.region = sel.value; renderTable(); };

  const i = lastIndex(worldSeries(s));
  $("table-title").textContent = `Per land · ${label(s.dates[i])}`;
  const rows = s.countries
    .filter((c) => !state.region || c.region === state.region)
    .map((c) => ({ ...c, v: c.values[i], mm: delta(c.values, i, 1), yy: delta(c.values, i, 12) }))
    .filter((c) => c.v != null)
    .sort((a, b) => b.v - a.v || a.name.localeCompare(b.name));
  const cell = (d) => `<td class="num ${d > 0 ? "up" : d < 0 ? "down" : ""}">${d == null ? "–" : (d > 0 ? "+" : d < 0 ? "−" : "±") + fmt(Math.abs(d))}</td>`;
  $("table").querySelector("tbody").innerHTML = rows.length
    ? rows.map((c) => `<tr><td>${c.name}</td><td>${c.region || "–"}</td><td class="num">${fmt(c.v)}</td>${cell(c.mm)}${cell(c.yy)}</tr>`).join("")
    : `<tr><td colspan="5">Ingen landdata i denne seksjonen.</td></tr>`;
}
