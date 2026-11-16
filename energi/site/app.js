/* Energi på Stortinget – klientside. Ingen avhengigheter. */
(() => {
  "use strict";

  // ---------- Konstanter ----------
  const PARTI = {
    A: ["Arbeiderpartiet", "#e4202c"], H: ["Høyre", "#0065f1"], FrP: ["Fremskrittspartiet", "#024c93"],
    Sp: ["Senterpartiet", "#00843d"], SV: ["Sosialistisk Venstreparti", "#e3307e"], R: ["Rødt", "#8b0b0b"],
    MDG: ["Miljøpartiet De Grønne", "#3e9a3a"], KrF: ["Kristelig Folkeparti", "#f2b200"], V: ["Venstre", "#00807b"],
    PF: ["Pasientfokus", "#4a8bc2"], Uav: ["Uavhengig", "#8892a0"],
  };
  const FASE = { "-1": ["Trukket/bortfalt", ""], 0: ["Varslet", "violet"], 1: ["Mottatt", "blue"], 2: ["I komiteen", "blue"], 3: ["Innstilling avgitt", "amber"], 4: ["Behandlet", "green"] };
  const SPM = { skriftlig: "Skriftlig spørsmål", sporretime: "Spørretimespørsmål", muntlig: "Muntlig spørretime", interpellasjon: "Interpellasjon" };
  const SPM_KORT = { skriftlig: "Skriftlig", sporretime: "Spørretime", muntlig: "Muntlig", interpellasjon: "Interpellasjon" };
  const CAL = { horing: "Høring", frist: "Frist", plenum: "Stortinget", minister: "Statsråden" };
  const MND = ["jan.", "feb.", "mars", "apr.", "mai", "juni", "juli", "aug.", "sep.", "okt.", "nov.", "des."];
  const UKEDAG = ["søn", "man", "tir", "ons", "tor", "fre", "lør"];

  const I = {
    search: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6.5" fill="none" stroke="currentColor" stroke-width="2"/><path d="m16 16 4.5 4.5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
    doc: '<svg viewBox="0 0 24 24"><path d="M6 2h9l5 5v13a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2zm8 1.5V8h4.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>',
    check: '<svg viewBox="0 0 24 24"><path d="m5 12.5 4.5 4.5L19 7.5" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    gavel: '<svg viewBox="0 0 24 24"><path d="m14 4 6 6M11 7l6 6M12.5 5.5l-5 5 4 4 5-5M9.5 12.5 3 19M4 21h9" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    ask: '<svg viewBox="0 0 24 24"><path d="M4 5a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H9l-5 4z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><path d="M10 8.2a2 2 0 1 1 2.8 1.8c-.6.3-.8.7-.8 1.3" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
    reply: '<svg viewBox="0 0 24 24"><path d="M10 6 4 12l6 6M4.5 12H14a6 6 0 0 1 6 6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    gov: '<svg viewBox="0 0 24 24"><path d="M3 10 12 4l9 6M5 10v8M9.5 10v8M14.5 10v8M19 10v8M3 20.5h18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    clock: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5" fill="none" stroke="currentColor" stroke-width="2.2"/><path d="M12 7.5V12l3 2" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>',
    sun: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4.5"/><path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M4.9 19.1l1.8-1.8M17.3 6.7l1.8-1.8" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
    hear: '<svg viewBox="0 0 24 24"><path d="M7 4h10a2 2 0 0 1 2 2v14l-4-2.5-3 2-3-2L5 20V6a2 2 0 0 1 2-2z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><path d="M9 9h6M9 12.5h4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
    moon: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3a9 9 0 1 0 9 9 7 7 0 0 1-9-9z"/></svg>',
  };
  const FEED_IC = { ny_sak: ["doc", "blue"], innstilling: ["gavel", "violet"], vedtak: ["check", "green"], spm: ["ask", "amber"], svar: ["reply", "green"], regjeringen: ["gov", ""], ekstern_horing: ["hear", "violet"] };

  // ---------- Hjelpere ----------
  const $ = (s, el = document) => el.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const norm = (s) => String(s ?? "").toLowerCase();
  const toDate = (s) => {
    if (!s) return null;
    if (s.length === 10) { const [y, m, d] = s.split("-").map(Number); return new Date(y, m - 1, d); }
    return new Date(s);
  };
  const dayKey = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const TODAY = dayKey(today);
  const fmt = (s, withYear) => {
    const d = toDate(s); if (!d) return "";
    const y = withYear || d.getFullYear() !== today.getFullYear() ? ` ${d.getFullYear()}` : "";
    return `${d.getDate()}. ${MND[d.getMonth()]}${y}`;
  };
  const fmtTime = (s) => (s && s.length > 10 && !/T00:00/.test(s) ? toDate(s).toLocaleTimeString("nb-NO", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Oslo" }) : "");
  const daysBetween = (a, b) => Math.round((toDate(b).setHours(0, 0, 0, 0) - toDate(a).setHours(0, 0, 0, 0)) / 864e5);
  const rel = (s) => {
    const d = daysBetween(TODAY, s.slice(0, 10));
    if (d === 0) return "i dag"; if (d === 1) return "i morgen"; if (d === -1) return "i går";
    if (d > 1 && d < 7) return `om ${d} dager`; if (d < -1 && d > -7) return `${-d} dager siden`;
    return fmt(s);
  };
  const party = (id) => {
    if (!id) return "";
    const p = PARTI[id] || [id, "#8892a0"];
    return `<span class="party" title="${esc(p[0])}" style="--pc:${p[1]}"><i></i>${esc(id)}</span>`;
  };
  const who = (p) => (p && p.navn ? `${esc(p.navn)} ${party(p.parti)}` : "");
  const pill = (txt, cls = "", dot = false) => `<span class="pill ${cls}${dot ? " dotted" : ""}">${esc(txt)}</span>`;
  const store = {
    get(k, d) { try { const v = localStorage.getItem("energi:" + k); return v === null ? d : JSON.parse(v); } catch { return d; } },
    set(k, v) { try { localStorage.setItem("energi:" + k, JSON.stringify(v)); } catch { /* privat modus */ } },
  };
  const debounce = (fn, ms = 120) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
  const plural = (n, en, fl) => `${n} ${n === 1 ? en : fl}`;

  // ---------- Tilstand ----------
  let D = null;
  const ui = Object.assign({
    scope: "energi",            // energi | alle
    sesjon: "alle",             // alle | cur | prev
    saker: { q: "", fase: "aktive", tema: "", dok: "", sort: "nyeste" },
    spm: { q: "", type: "", status: "", parti: "", andre: false, limit: 40 },
    kal: { type: "" },
    reg: { kat: "nyhet", q: "" },
    hor: { q: "", kilde: "", vis: "aktuelle" },
  }, store.get("ui", {}));
  ui.spm.limit = 40;
  const save = () => store.set("ui", ui);

  // ---------- Tema ----------
  const setTheme = (t) => {
    if (t) document.documentElement.dataset.theme = t; else delete document.documentElement.dataset.theme;
    const dark = t ? t === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    $("#themeBtn").innerHTML = dark ? I.sun : I.moon;
  };
  setTheme(store.get("theme", null));
  $("#themeBtn").addEventListener("click", () => {
    const dark = document.documentElement.dataset.theme ? document.documentElement.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    const t = dark ? "light" : "dark"; store.set("theme", t); setTheme(t);
  });

  // ---------- Utvalg ----------
  const inSession = (x) => ui.sesjon === "alle" || !x.sesjon || (ui.sesjon === "cur" ? x.sesjon === D.sesjon : x.sesjon !== D.sesjon);
  const sakScope = (s) => ui.scope === "alle" || s.energi;
  const spmScope = (q) => q.energiminister || ui.spm.andre;
  const nextDate = (s) => {
    const d = s.datoer || {};
    return ["horingsfrist", "innstillingsfrist", "planlagt"].map((k) => [k, d[k]]).filter(([, v]) => v && v >= TODAY).sort((a, b) => a[1].localeCompare(b[1]))[0];
  };
  const NEXT_LBL = { horingsfrist: "Høringsfrist", innstillingsfrist: "Innstillingsfrist", planlagt: "Behandles" };

  // ---------- Komponenter ----------
  const scopeSwitch = (id = "scopeSw") => `<label class="switch" title="Vis også klima- og miljøsaker i Energi- og miljøkomiteen"><input type="checkbox" id="${id}" ${ui.scope === "alle" ? "checked" : ""}>Ta med klima og miljø</label>`;
  const sesjonSel = () => `<select class="sel" id="sesSel" aria-label="Sesjon">
      <option value="alle" ${ui.sesjon === "alle" ? "selected" : ""}>Begge sesjoner</option>
      <option value="cur" ${ui.sesjon === "cur" ? "selected" : ""}>${esc(D.sesjon)}</option>
      <option value="prev" ${ui.sesjon === "prev" ? "selected" : ""}>${esc(D.sesjoner[1] || "Forrige")}</option></select>`;
  const searchBox = (id, val, ph) => `<label class="search">${I.search}<span class="sr">Søk</span><input id="${id}" type="search" value="${esc(val)}" placeholder="${esc(ph)}" autocomplete="off"></label>`;
  const seg = (id, opts, cur) => `<div class="seg" role="group" id="${id}">${opts.map(([v, l, n]) => `<button type="button" data-v="${esc(v)}" aria-pressed="${v === cur}">${esc(l)}${n !== undefined ? `<span class="n">${n}</span>` : ""}</button>`).join("")}</div>`;
  const empty = (t, s) => `<div class="empty"><b>${esc(t)}</b>${esc(s || "")}</div>`;

  function sakCard(s) {
    const f = FASE[s.fase] || ["", ""];
    const nd = nextDate(s);
    const steps = s.fase < 0 ? "" : `<div class="steps ${s.fase === 4 ? "done" : ""}" aria-hidden="true">${[1, 2, 3, 4].map((i) => `<span class="${s.fase >= i || (i === 1 && s.fase >= 0) ? "on" : ""}"></span>`).join("")}</div>
      <div class="steps-l" aria-hidden="true">${["Fremmet", "Komité", "Innstilling", "Vedtatt"].map((l, i) => `<span class="${Math.max(1, s.fase) === i + 1 ? "cur" : ""}">${Math.max(1, s.fase) === i + 1 ? `<b>${l}</b>` : l}</span>`).join("")}</div>`;
    const by = s.forslagstillere?.length ? `Forslag fra ${[...new Set(s.forslagstillere.map((p) => p.parti))].map(party).join(" ")}` : s.dokgruppe === "Proposisjon" || s.dokgruppe === "Melding" ? "Fra regjeringen" : "";
    const ord = s.saksordforer?.length ? `Saksordfører ${who(s.saksordforer[0])}` : "";
    return `<a class="card" href="#/saker/${s.id}">
      <div class="row1">${pill(f[0], f[1], true)}<span class="ref">${esc(s.henvisning || s.dokgruppe)}</span>${s.komite_id && s.komite_id !== "ENERGI" ? `<span class="tag">${esc(s.komite || "")}</span>` : ""}${(s.tema || []).slice(0, 2).map((t) => `<span class="tag">${esc(t)}</span>`).join("")}</div>
      <h3>${esc(s.korttittel || s.tittel)}</h3>
      ${by || ord ? `<div class="sub">${by ? `<span>${by}</span>` : ""}${ord ? `<span>${ord}</span>` : ""}</div>` : ""}
      ${steps}
      ${nd ? `<div class="foot-row"><span class="next">${I.clock}${NEXT_LBL[nd[0]]} ${esc(fmt(nd[1]))}</span><span>${esc(rel(nd[1]))}</span></div>` : ""}
    </a>`;
  }

  function spmCard(q) {
    const st = q.status === "besvart"
      ? pill(`Besvart ${fmt(q.besvart)}`, "green", true)
      : pill(`Venter på svar${q.datert ? ` · ${Math.max(0, daysBetween(q.datert.slice(0, 10), TODAY))} d` : ""}`, "amber", true);
    const svartid = q.besvart && q.datert ? daysBetween(q.datert.slice(0, 10), q.besvart.slice(0, 10)) : null;
    return `<a class="card" href="#/sporsmal/${q.id}">
      <div class="row1"><span class="tag">${esc(SPM_KORT[q.type])}</span><span>${esc(fmt(q.datert))}</span>${!q.energiminister ? `<span class="tag">Til ${esc(q.til_tittel || "")}</span>` : ""}</div>
      <p class="q">${esc(q.tittel)}</p>
      <div class="foot-row"><span>${who(q.fra)}</span><span>${st}${svartid !== null ? ` <span class="sr">svartid</span>` : ""}</span></div>
    </a>`;
  }

  function feedItem(a) {
    const [ic, col] = FEED_IC[a.type] || ["doc", ""];
    const href = a.sak_id ? `#/saker/${a.sak_id}` : a.spm_id ? `#/sporsmal/${a.spm_id}` : a.url;
    const ext = !a.sak_id && !a.spm_id;
    return `<li class="clickable" data-href="${esc(href)}" ${ext ? 'data-ext="1"' : ""}>
      <span class="ic ${col}">${I[ic]}</span>
      <div><div class="lbl"><b>${esc(a.label)}</b><span>${esc(rel(a.dato))}</span></div>
      <a class="t" href="${esc(href)}" ${ext ? 'target="_blank" rel="noopener"' : ""}>${esc(a.tittel)}</a>
      ${a.meta ? `<div class="m">${esc(a.meta).slice(0, 220)}</div>` : ""}</div></li>`;
  }

  function calDays(items, mini) {
    if (!items.length) return empty("Ingen kommende hendelser", "Ingenting i kalenderen med dette utvalget.");
    const by = new Map();
    items.forEach((c) => { const k = c.dato.slice(0, 10); if (!by.has(k)) by.set(k, []); by.get(k).push(c); });
    return `<div class="${mini ? "mini" : ""}">${[...by].map(([k, evs]) => {
      const d = toDate(k);
      return `<div class="day"><div class="date-badge ${k === TODAY ? "today" : ""}"><div class="wd">${k === TODAY ? "i dag" : UKEDAG[d.getDay()]}</div><div class="d">${d.getDate()}</div><div class="mo">${MND[d.getMonth()]}</div></div>
        <div class="events">${evs.map((c) => {
          const href = c.sak_id && D.sakById.has(c.sak_id) ? `#/saker/${c.sak_id}` : c.url;
          const ext = !href.startsWith("#");
          return `<a class="ev ${c.type}" href="${esc(href)}" ${ext ? 'target="_blank" rel="noopener"' : ""}><span class="el">${esc(c.label)}${fmtTime(c.dato) ? `<time>kl. ${fmtTime(c.dato)}</time>` : ""}</span><span class="et">${esc(c.tittel || "")}</span></a>`;
        }).join("")}</div></div>`;
    }).join("")}</div>`;
  }

  // ---------- Sider ----------
  const main = $("#main");

  function viewOversikt() {
    const saker = D.saker.filter(sakScope);
    const aktive = saker.filter((s) => s.fase >= 0 && s.fase < 4);
    const beh = saker.filter((s) => s.fase === 4 && s.sesjon === D.sesjon);
    const spm = D.sporsmal.filter((q) => q.energiminister && (q.sesjon === D.sesjon || !q.sesjon));
    const venter = spm.filter((q) => q.status === "venter");
    const in14 = dayKey(new Date(today.getTime() + 14 * 864e5));
    const kal = D.kalender.filter((c) => (ui.scope === "alle" || c.energi) && c.dato.slice(0, 10) <= in14);
    const akt = D.aktivitet.filter((a) => ui.scope === "alle" || a.energi);
    const nyh = D.nyheter.filter((n) => n.kategori === "nyhet").slice(0, 4);
    const fail = Object.entries(D.kilder).filter(([, v]) => !v.ok);
    const apneHor = D.hor.filter((h) => horScope(h) && h.frist && h.frist >= TODAY).sort((a, b) => a.frist.localeCompare(b.frist));

    main.innerHTML = `
      <div class="page-head"><div><h1>Oversikt</h1><p>Hva skjer med energipolitikken på Stortinget nå.</p></div>${scopeSwitch()}</div>
      ${fail.length ? `<div class="warn">Noen kilder kunne ikke hentes ved siste oppdatering (${fail.map(([k]) => esc(k)).join(", ")}). Viser forrige data for disse.</div>` : ""}
      <div class="stats">
        <a class="stat" href="#/saker" data-set="aktive" style="--bar:var(--c-blue)"><div class="k">Saker til behandling</div><div class="v">${aktive.length}</div><div class="s">${aktive.filter((s) => s.fase === 3).length} med innstilling avgitt</div></a>
        <a class="stat" href="#/saker" data-set="behandlet" style="--bar:var(--c-green)"><div class="k">Behandlet ${esc(D.sesjon)}</div><div class="v">${beh.length}</div><div class="s">${saker.filter((s) => s.fase === 4 && s.sesjon !== D.sesjon).length} i ${esc(D.sesjoner[1] || "forrige sesjon")}</div></a>
        <a class="stat" href="#/sporsmal" style="--bar:var(--accent)"><div class="k">Spørsmål til energiministeren</div><div class="v">${spm.length}</div><div class="s">${venter.length} venter på svar</div></a>
        <a class="stat" href="#/kalender" style="--bar:var(--c-violet)"><div class="k">Neste 14 dager</div><div class="v">${kal.length}</div><div class="s">høringer, frister og møter</div></a>
      </div>
      <div class="grid-2">
        <section class="panel flush" aria-labelledby="h-akt"><h2 class="sec" id="h-akt">Siste aktivitet</h2>
          <ul class="feed" id="feed">${akt.slice(0, 12).map(feedItem).join("")}</ul>
          ${akt.length > 12 ? `<button class="more" id="moreFeed" type="button">Vis mer aktivitet</button>` : ""}
        </section>
        <div class="stack">
          ${apneHor.length ? `<section class="panel flush" aria-labelledby="h-hor"><h2 class="sec" id="h-hor">Åpne høringer <a href="#/horinger">Alle ${apneHor.length} →</a></h2><ul class="feed">${apneHor.slice(0, 5).map((h) => `<li class="clickable" data-href="${esc(h.href)}" ${h.ext ? 'data-ext="1"' : ""}><span class="ic ${KILDE[h.kilde][1]}">${I.hear}</span><div><div class="lbl"><b>${esc(h.avsender)}</b><span>${h.frist ? `frist ${esc(fmt(h.frist))}` : `sendt ut ${esc(fmt(h.publisert))}`}</span></div><a class="t" href="${esc(h.href)}" ${h.ext ? 'target="_blank" rel="noopener"' : ""}>${esc(h.tittel)}</a></div></li>`).join("")}</ul></section>` : ""}
          <section class="panel flush" aria-labelledby="h-kal"><h2 class="sec" id="h-kal">Kommende <a href="#/kalender">Hele kalenderen →</a></h2>${calDays(kal.slice(0, 8), true)}</section>
          ${venter.length ? `<section class="panel flush" aria-labelledby="h-vent"><h2 class="sec" id="h-vent">Venter på svar fra energiministeren</h2><ul class="feed">${venter.slice(0, 5).map((q) => `<li class="clickable" data-href="#/sporsmal/${q.id}"><span class="ic amber">${I.ask}</span><div><div class="lbl"><b>${who(q.fra)}</b><span>${esc(rel(q.datert))}</span></div><a class="t" href="#/sporsmal/${q.id}">${esc(q.tittel)}</a></div></li>`).join("")}</ul></section>` : ""}
          <section class="panel flush" aria-labelledby="h-reg"><h2 class="sec" id="h-reg">Fra Energidepartementet <a href="#/nyheter">Alle →</a></h2><ul class="feed">${nyh.map((n) => feedItem({ type: "regjeringen", label: "Nyhet", dato: n.dato, tittel: n.tittel, url: n.url })).join("")}</ul></section>
        </div>
      </div>`;
    let shown = 12;
    $("#moreFeed")?.addEventListener("click", (e) => {
      shown += 20; $("#feed").innerHTML = akt.slice(0, shown).map(feedItem).join("");
      if (shown >= akt.length) e.target.remove();
    });
    main.querySelectorAll("[data-set]").forEach((a) => a.addEventListener("click", () => { ui.saker.fase = a.dataset.set; ui.sesjon = a.dataset.set === "behandlet" ? "cur" : ui.sesjon; save(); }));
    bindScope(viewOversikt);
  }

  function viewSaker() {
    const u = ui.saker;
    main.innerHTML = `
      <div class="page-head"><div><h1>Saker</h1><p>Saker i Energi- og miljøkomiteen og energisaker i andre komiteer.</p></div>${scopeSwitch()}</div>
      <div class="toolbar">${searchBox("sq", u.q, "Søk: havvind, nettleie, Dokument 8 …")}${sesjonSel()}
        <select class="sel" id="sSort" aria-label="Sortering"><option value="nyeste">Nyeste først</option><option value="frist">Nærmeste frist</option><option value="oppdatert">Sist oppdatert</option></select></div>
      <div id="segWrap"></div>
      <div class="chips" id="temaChips"></div>
      <div class="result-meta" id="sMeta"></div>
      <div class="list" id="sList"></div>`;
    $("#sSort").value = u.sort;
    const render = () => {
      const q = norm(u.q).trim();
      const base = D.saker.filter((s) => sakScope(s) && inSession(s) && (!q || norm(`${s.tittel} ${s.korttittel} ${s.henvisning} ${s.komite} ${(s.tema || []).join(" ")} ${(s.forslagstillere || []).map((p) => p.navn + " " + p.parti).join(" ")}`).includes(q)));
      const fOK = { aktive: (s) => s.fase >= 0 && s.fase < 4, komite: (s) => s.fase === 2 || s.fase === 1 || s.fase === 0, innstilling: (s) => s.fase === 3, behandlet: (s) => s.fase === 4, alle: () => true };
      const cnt = (k) => base.filter(fOK[k]).length;
      $("#segWrap").innerHTML = seg("fSeg", [["aktive", "Til behandling", cnt("aktive")], ["innstilling", "Innstilling avgitt", cnt("innstilling")], ["behandlet", "Behandlet", cnt("behandlet")], ["alle", "Alle", cnt("alle")]], fOK[u.fase] ? u.fase : "aktive");
      const byFase = base.filter(fOK[u.fase] || fOK.aktive);
      const temaCount = {};
      byFase.forEach((s) => (s.tema || []).forEach((t) => (temaCount[t] = (temaCount[t] || 0) + 1)));
      const temaer = Object.entries(temaCount).sort((a, b) => b[1] - a[1]);
      if (u.tema && !temaCount[u.tema]) u.tema = "";
      $("#temaChips").innerHTML = temaer.length ? `<button class="chip" type="button" data-t="" aria-pressed="${!u.tema}">Alle tema</button>` + temaer.map(([t, n]) => `<button class="chip" type="button" data-t="${esc(t)}" aria-pressed="${u.tema === t}">${esc(t)} <span style="opacity:.6">${n}</span></button>`).join("") : "";
      let list = byFase.filter((s) => !u.tema || (s.tema || []).includes(u.tema));
      const sortKey = {
        nyeste: (s) => s.datoer?.fremmet || s.oppdatert || "",
        oppdatert: (s) => s.oppdatert || "",
      };
      if (u.sort === "frist") list.sort((a, b) => ((nextDate(a) || [, "9"])[1]).localeCompare((nextDate(b) || [, "9"])[1]));
      else list.sort((a, b) => sortKey[u.sort](b).localeCompare(sortKey[u.sort](a)));
      $("#sMeta").innerHTML = `<span>${plural(list.length, "sak", "saker")}</span>${u.q || u.tema ? `<a href="#" id="sReset">Nullstill filter</a>` : ""}`;
      $("#sList").innerHTML = list.length ? list.map(sakCard).join("") : empty("Ingen saker", "Prøv et annet søk eller filter.");
      $("#sReset")?.addEventListener("click", (e) => { e.preventDefault(); u.q = ""; u.tema = ""; $("#sq").value = ""; save(); render(); });
      $("#fSeg").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) { u.fase = b.dataset.v; save(); render(); } });
    };
    $("#sq").addEventListener("input", debounce((e) => { u.q = e.target.value; save(); render(); }));
    $("#sSort").addEventListener("change", (e) => { u.sort = e.target.value; save(); render(); });
    $("#sesSel").addEventListener("change", (e) => { ui.sesjon = e.target.value; save(); render(); });
    $("#temaChips").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) { u.tema = b.dataset.t; save(); render(); } });
    bindScope(render);
    render();
  }

  function viewSporsmal() {
    const u = ui.spm;
    main.innerHTML = `
      <div class="page-head"><div><h1>Spørsmål</h1><p>Skriftlige spørsmål, spørretimen og interpellasjoner til energiministeren.</p></div>
        <label class="switch"><input type="checkbox" id="andreSw" ${u.andre ? "checked" : ""}>Energispørsmål til andre statsråder</label></div>
      <div class="layout-side">
        <div>
          <div class="toolbar">${searchBox("qq", u.q, "Søk i spørsmål eller representant …")}${sesjonSel()}</div>
          <div id="qSeg" style="margin-bottom:10px"></div>
          <div class="result-meta" id="qMeta"></div>
          <div class="list" id="qList"></div>
          <button class="btn" id="qMore" type="button" style="margin:14px auto 0;display:none">Vis flere</button>
        </div>
        <aside class="panel" id="qSide" aria-label="Statistikk"></aside>
      </div>`;
    const render = () => {
      const q = norm(u.q).trim();
      const base = D.sporsmal.filter((x) => spmScope(x) && inSession(x) && (!q || norm(`${x.tittel} ${x.fra?.navn} ${x.fra?.parti} ${x.til_tittel}`).includes(q)));
      const typeN = (t) => base.filter((x) => !t || x.type === t || (t === "sporretime" && x.type === "muntlig")).length;
      $("#qSeg").innerHTML = `<div class="toolbar" style="margin:0">${seg("tSeg", [["", "Alle", typeN("")], ["skriftlig", "Skriftlige", typeN("skriftlig")], ["sporretime", "Spørretimen", typeN("sporretime")], ["interpellasjon", "Interpellasjoner", typeN("interpellasjon")]], u.type)}
        ${seg("stSeg", [["", "Alle"], ["venter", "Venter"], ["besvart", "Besvart"]], u.status)}</div>`;
      const pcAll = {};
      base.forEach((x) => { const p = x.fra?.parti; if (p) pcAll[p] = (pcAll[p] || 0) + 1; });
      $("#qSeg").insertAdjacentHTML("beforeend", `<div class="chips mobile-only" id="pChips" style="margin:10px 0 0"><button class="chip" type="button" data-p="" aria-pressed="${!u.parti}">Alle partier</button>${Object.entries(pcAll).sort((a, b) => b[1] - a[1]).map(([p]) => `<button class="chip" type="button" data-p="${esc(p)}" aria-pressed="${u.parti === p}" style="--pc:${(PARTI[p] || [, "#8892a0"])[1]}"><span class="dot"></span>${esc(p)}</button>`).join("")}</div>`);
      $("#pChips").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) { u.parti = b.dataset.p; save(); render(); } });
      const byType = base.filter((x) => !u.type || x.type === u.type || (u.type === "sporretime" && x.type === "muntlig"));
      const byStatus = byType.filter((x) => !u.status || x.status === u.status);
      const list = byStatus.filter((x) => !u.parti || x.fra?.parti === u.parti);
      // statistikk
      const besv = byType.filter((x) => x.besvart && x.datert).map((x) => daysBetween(x.datert.slice(0, 10), x.besvart.slice(0, 10))).sort((a, b) => a - b);
      const median = besv.length ? besv[Math.floor(besv.length / 2)] : "–";
      const pc = {};
      byStatus.forEach((x) => { const p = x.fra?.parti || "?"; pc[p] = (pc[p] || 0) + 1; });
      const parts = Object.entries(pc).sort((a, b) => b[1] - a[1]);
      const max = parts[0]?.[1] || 1;
      $("#qSide").innerHTML = `
        <div class="kpis"><div class="kpi"><div class="v">${byType.length}</div><div class="k">spørsmål</div></div>
        <div class="kpi"><div class="v">${byType.filter((x) => x.status === "venter").length}</div><div class="k">venter</div></div>
        <div class="kpi"><div class="v">${median}</div><div class="k">dager svartid (median)</div></div></div>
        <h2 class="sec">Hvem spør? ${u.parti ? `<a href="#" id="pReset">Vis alle</a>` : ""}</h2>
        <div class="bars">${parts.map(([p, n]) => `<button class="bar" type="button" data-p="${esc(p)}" aria-pressed="${u.parti === p}" style="--pc:${(PARTI[p] || [, "#8892a0"])[1]}"><span>${party(p)}</span><span class="track"><b style="width:${(n / max) * 100}%"></b></span><span class="num">${n}</span></button>`).join("")}</div>`;
      $("#qMeta").innerHTML = `<span>${plural(list.length, "spørsmål", "spørsmål")}${u.parti ? ` fra ${esc(u.parti)}` : ""}</span>`;
      $("#qList").innerHTML = list.length ? list.slice(0, u.limit).map(spmCard).join("") : empty("Ingen spørsmål", "Prøv et annet søk eller filter.");
      $("#qMore").style.display = list.length > u.limit ? "flex" : "none";
      $("#tSeg").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) { u.type = b.dataset.v; u.limit = 40; save(); render(); } });
      $("#stSeg").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) { u.status = b.dataset.v; u.limit = 40; save(); render(); } });
      $("#pReset")?.addEventListener("click", (e) => { e.preventDefault(); u.parti = ""; save(); render(); });
    };
    $("#qSide").addEventListener("click", (e) => { const b = e.target.closest(".bar"); if (b) { u.parti = u.parti === b.dataset.p ? "" : b.dataset.p; save(); render(); } });
    $("#qq").addEventListener("input", debounce((e) => { u.q = e.target.value; u.limit = 40; save(); render(); }));
    $("#sesSel").addEventListener("change", (e) => { ui.sesjon = e.target.value; save(); render(); });
    $("#andreSw").addEventListener("change", (e) => { u.andre = e.target.checked; save(); render(); });
    $("#qMore").addEventListener("click", () => { u.limit += 40; render(); });
    render();
  }

  function viewKalender() {
    const u = ui.kal;
    main.innerHTML = `
      <div class="page-head"><div><h1>Kalender</h1><p>Høringer, frister, behandling i Stortinget og statsrådens program.</p></div>${scopeSwitch()}</div>
      <div id="kSeg" style="margin-bottom:12px"></div>
      <section class="panel flush" id="kList"></section>`;
    const render = () => {
      const base = D.kalender.filter((c) => ui.scope === "alle" || c.energi);
      const n = (t) => base.filter((c) => !t || c.type === t).length;
      $("#kSeg").innerHTML = seg("kS", [["", "Alt", n("")], ["horing", "Høringer", n("horing")], ["frist", "Frister", n("frist")], ["plenum", "Stortinget", n("plenum")], ["minister", "Statsråden", n("minister")]], u.type);
      $("#kList").innerHTML = calDays(base.filter((c) => !u.type || c.type === u.type));
      $("#kS").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) { u.type = b.dataset.v; save(); render(); } });
    };
    bindScope(render);
    render();
  }

  function viewRegjeringen() {
    const u = ui.reg;
    main.innerHTML = `
      <div class="page-head"><div><h1>Regjeringen</h1><p>Nyheter, pressemeldinger og statsrådens program fra Energidepartementet.</p></div></div>
      <div class="toolbar">${searchBox("rq", u.q, "Søk i nyheter …")}<div id="rSeg"></div></div>
      <section class="panel flush"><ul class="feed" id="rList"></ul></section>`;
    const render = () => {
      const q = norm(u.q).trim();
      const base = D.nyheter.filter((n) => !q || norm(n.tittel + " " + n.beskrivelse).includes(q));
      const c = (k) => base.filter((n) => !k || n.kategori === k).length;
      $("#rSeg").innerHTML = seg("rS", [["nyhet", "Nyheter", c("nyhet")], ["kalender", "Statsrådens program", c("kalender")], ["", "Alt", c("")]], u.kat);
      const list = base.filter((n) => !u.kat || n.kategori === u.kat);
      $("#rList").innerHTML = list.length ? list.map((n) => `<li class="clickable" data-href="${esc(n.url)}" data-ext="1"><span class="ic ${n.kategori === "kalender" ? "green" : ""}">${n.kategori === "kalender" ? I.clock : I.gov}</span><div><div class="lbl"><b>${n.kategori === "kalender" ? "Program" : "Nyhet"}</b><span>${esc(fmt(n.dato, true))}${fmtTime(n.dato) ? ` kl. ${fmtTime(n.dato)}` : ""}</span></div><a class="t" href="${esc(n.url)}" target="_blank" rel="noopener">${esc(n.tittel)}</a>${n.beskrivelse ? `<div class="m">${esc(n.beskrivelse.slice(0, 240))}</div>` : ""}</div></li>`).join("") : `<li>${empty("Ingen treff")}</li>`;
      $("#rS").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) { u.kat = b.dataset.v; save(); render(); } });
    };
    $("#rq").addEventListener("input", debounce((e) => { u.q = e.target.value; save(); render(); }));
    render();
  }

  // ---------- Høringer ----------
  const KILDE = { stortinget: ["Stortinget", "blue"], regjeringen: ["Regjeringen", "violet"], miljodirektoratet: ["Miljødirektoratet", "green"] };
  const horScope = (h) => ui.scope === "alle" || h.energi;
  const aktuell = (h) => (h.frist ? h.frist >= TODAY : !!h.publisert && daysBetween(h.publisert, TODAY) <= 90);
  function buildHoringer() {
    const st = (D.horinger || []).map((h) => {
      const sak = h.saker[0] || {};
      const own = D.sakById.get(sak.id);
      return {
        id: "st-" + h.id, kilde: "stortinget", avsender: "Energi- og miljøkomiteen", tittel: sak.tittel || "Høring",
        beskrivelse: h.skriftlig ? "Skriftlig høring" : "Høring i komiteen", saksnr: sak.henvisning,
        publisert: (h.start || h.innspillsfrist || "").slice(0, 10) || null, frist: (h.innspillsfrist || "").slice(0, 10) || null,
        fristTid: h.innspillsfrist, tema: own ? own.tema : [], energi: own ? own.energi : true,
        href: own ? `#/saker/${own.id}` : h.url, ext: !own,
      };
    });
    const ext = (D.eksterne_horinger || []).map((h) => ({ ...h, href: h.url, ext: true }));
    return [...st, ...ext];
  }
  function horCard(h) {
    const k = KILDE[h.kilde];
    let fr;
    if (h.frist) {
      const dleft = daysBetween(TODAY, h.frist);
      fr = dleft < 0 ? `<span>Frist var ${esc(fmt(h.frist, true))}</span>`
        : `${pill(`Frist ${fmt(h.frist)}${fmtTime(h.fristTid) ? " kl. " + fmtTime(h.fristTid) : ""}`, dleft <= 7 ? "amber" : "green", true)} <span>${esc(rel(h.frist))}</span>`;
    } else fr = `<span>Sendt ut ${esc(fmt(h.publisert, true))} · frist står på høringssiden</span>`;
    return `<a class="card" href="${esc(h.href)}" ${h.ext ? 'target="_blank" rel="noopener"' : ""}>
      <div class="row1">${pill(k[0], k[1])}${h.avsender !== k[0] ? `<span class="ref">${esc(h.avsender)}</span>` : ""}${h.saksnr ? `<span>${esc(h.saksnr)}</span>` : ""}</div>
      <h3>${esc(h.tittel)}</h3>
      ${h.beskrivelse && h.kilde === "regjeringen" ? `<p class="q" style="-webkit-line-clamp:2;margin-top:6px;font-size:14px;color:var(--ink-2)">${esc(h.beskrivelse)}</p>` : ""}
      <div class="foot-row"><span style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">${fr}</span><span style="display:flex;gap:5px;flex-wrap:wrap">${(h.tema || []).slice(0, 3).map((t) => `<span class="tag">${esc(t)}</span>`).join("")}</span></div>
    </a>`;
  }
  function viewHoringer() {
    const u = ui.hor;
    main.innerHTML = `
      <div class="page-head"><div><h1>Høringer</h1><p>Høringer i Stortinget, fra Energidepartementet, om petroleum fra andre departementer og fra Miljødirektoratet.</p></div>${scopeSwitch()}</div>
      <div class="toolbar">${searchBox("hq", u.q, "Søk i høringer, f.eks. Equinor, vindkraft …")}<div id="hVis"></div></div>
      <div id="hSeg" style="margin-bottom:12px"></div>
      <div class="result-meta" id="hMeta"></div>
      <div class="list" id="hList"></div>`;
    const render = () => {
      const q = norm(u.q).trim();
      const base = D.hor.filter((h) => horScope(h) && (u.vis === "alle" || aktuell(h)) && (!q || norm(`${h.tittel} ${h.beskrivelse} ${h.avsender} ${h.saksnr} ${(h.tema || []).join(" ")}`).includes(q)));
      const n = (k) => base.filter((h) => !k || h.kilde === k).length;
      $("#hVis").innerHTML = seg("hV", [["aktuelle", "Aktuelle"], ["alle", "Alle"]], u.vis);
      $("#hSeg").innerHTML = seg("hK", [["", "Alle kilder", n("")], ["stortinget", "Stortinget", n("stortinget")], ["regjeringen", "Regjeringen", n("regjeringen")], ["miljodirektoratet", "Miljødirektoratet", n("miljodirektoratet")]], u.kilde);
      const list = base.filter((h) => !u.kilde || h.kilde === u.kilde);
      if (u.vis === "aktuelle") list.sort((a, b) => (a.frist && b.frist ? a.frist.localeCompare(b.frist) : a.frist ? -1 : b.frist ? 1 : (b.publisert || "").localeCompare(a.publisert || "")));
      else list.sort((a, b) => (b.publisert || b.frist || "").localeCompare(a.publisert || a.frist || ""));
      $("#hMeta").innerHTML = `<span>${plural(list.length, "høring", "høringer")}${u.vis === "aktuelle" ? " – åpne, og regjeringshøringer fra siste 90 dager" : ""}</span>`;
      $("#hList").innerHTML = list.length ? list.map(horCard).join("") : empty("Ingen høringer", "Prøv «Alle» eller et annet søk.");
      $("#hV").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) { u.vis = b.dataset.v; save(); render(); } });
      $("#hK").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) { u.kilde = b.dataset.v; save(); render(); } });
    };
    $("#hq").addEventListener("input", debounce((e) => { u.q = e.target.value; save(); render(); }));
    bindScope(render);
    render();
  }

  function bindScope(render) {
    $("#scopeSw")?.addEventListener("change", (e) => { ui.scope = e.target.checked ? "alle" : "energi"; save(); render(); });
  }

  // ---------- Detaljark ----------
  const sheet = $("#sheet"), backdrop = $("#backdrop");
  let lastFocus = null;
  function openSheet(html) {
    $("#sheetBody").innerHTML = html;
    if (sheet.hidden) lastFocus = document.activeElement;
    sheet.hidden = false; backdrop.hidden = false;
    document.body.style.overflow = "hidden";
    sheet.scrollTop = 0;
    sheet.focus({ preventScroll: true });
  }
  function closeSheet(fromRoute) {
    if (sheet.hidden) return;
    sheet.hidden = true; backdrop.hidden = true; document.body.style.overflow = "";
    if (!fromRoute) location.hash = `#/${route().tab}`;
    lastFocus?.focus?.({ preventScroll: true });
  }
  $("#sheetClose").addEventListener("click", () => closeSheet());
  backdrop.addEventListener("click", () => closeSheet());
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeSheet(); });

  function sakSheet(s) {
    const f = FASE[s.fase] || ["", ""];
    const hor = D.horinger.filter((h) => h.saker.some((x) => x.id === s.id));
    const d = s.datoer || {};
    const fut = [["horingsfrist", "Frist for å melde seg til høring"], ["innstillingsfrist", "Frist for innstilling"], ["planlagt", "Planlagt behandlet i Stortinget"]]
      .filter(([k]) => d[k] && d[k] >= TODAY && !s.hendelser.some((h) => h.dato === d[k] && NEXT_ID[k] === h.id));
    const tl = [...s.hendelser.map((h) => ({ ...h, fut: h.dato > TODAY })), ...fut.map(([k, l]) => ({ dato: d[k], label: l, fut: true }))].sort((a, b) => a.dato.localeCompare(b.dato));
    const forsl = s.forslagstillere || [];
    return `
      <div class="row1" style="display:flex;gap:6px;flex-wrap:wrap;align-items:center">${pill(f[0], f[1], true)}<span class="ref">${esc(s.henvisning || "")}</span></div>
      <h2 id="sheetTitle">${esc(s.korttittel)}</h2>
      ${s.tittel && s.tittel !== s.korttittel ? `<p class="lead">${esc(s.tittel.length > 400 ? s.tittel.slice(0, 400) + " …" : s.tittel)}</p>` : ""}
      <dl class="facts">
        <dt>Type</dt><dd>${esc([s.dokgruppe, s.type].filter(Boolean).join(" · "))}</dd>
        <dt>Komité</dt><dd>${esc(s.komite || "–")}</dd>
        ${s.saksordforer?.length ? `<dt>Saksordfører</dt><dd>${s.saksordforer.map(who).join(", ")}</dd>` : ""}
        ${forsl.length ? `<dt>Forslag fra</dt><dd>${forsl.slice(0, 6).map(who).join(", ")}${forsl.length > 6 ? ` og ${forsl.length - 6} til` : ""}</dd>` : ""}
        <dt>Sesjon</dt><dd>${esc(s.sesjon)}</dd>
        ${s.tema?.length ? `<dt>Tema</dt><dd>${s.tema.map((t) => `<span class="tag">${esc(t)}</span>`).join(" ")}</dd>` : ""}
      </dl>
      ${s.kortvedtak ? `<h4>Vedtak</h4><p class="quote">${esc(s.kortvedtak)}</p>` : s.vedtakstekst ? `<h4>Vedtak</h4><p class="quote">${esc(s.vedtakstekst)}</p>` : ""}
      ${tl.length ? `<h4>Saksgang</h4><ol class="tl">${tl.map((h) => `<li class="${h.fut ? "future" : ""}"><time>${esc(fmt(h.dato, true))}</time>${esc(h.label)}</li>`).join("")}</ol>` : ""}
      ${hor.length ? `<h4>Høring</h4><div class="links">${hor.map((h) => `<a href="${esc(h.url)}" target="_blank" rel="noopener">${h.skriftlig ? "Skriftlig høring" : "Høring"}${h.innspillsfrist ? ` – frist ${esc(fmt(h.innspillsfrist, true))}` : ""}</a>`).join("")}</div>` : ""}
      ${s.publikasjoner?.length ? `<h4>Dokumenter</h4><div class="links">${s.publikasjoner.slice(0, 12).map((p) => `<a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.tekst)}</a>`).join("")}</div>` : ""}
      <a class="cta" href="${esc(s.url)}" target="_blank" rel="noopener">Åpne saken på stortinget.no ↗</a>`;
  }
  const NEXT_ID = { horingsfrist: "HOERFRIST", innstillingsfrist: "AVGFRIST", planlagt: "PLBEHS" };

  function spmSheet(q) {
    const svartid = q.besvart && q.datert ? daysBetween(q.datert.slice(0, 10), q.besvart.slice(0, 10)) : null;
    return `
      <div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center">${pill(SPM[q.type], "blue")}${q.status === "besvart" ? pill("Besvart", "green", true) : pill("Venter på svar", "amber", true)}</div>
      <h2 id="sheetTitle">${esc(SPM[q.type])} fra ${esc(q.fra?.navn || "representant")}</h2>
      <p class="quote">${esc(q.tittel)}</p>
      <h4>Detaljer</h4>
      <dl class="facts">
        ${q.fra ? `<dt>Fra</dt><dd>${who(q.fra)}${q.fra.fylke ? ` · ${esc(q.fra.fylke)}` : ""}</dd>` : ""}
        <dt>Til</dt><dd>${esc([q.til, q.til_tittel].filter(Boolean).join(", ") || "Energiministeren")}</dd>
        ${q.besvart_av ? `<dt>Besvart av</dt><dd>${esc(q.besvart_av)}${q.besvart_av_tittel ? `, ${esc(q.besvart_av_tittel)}` : ""}</dd>` : ""}
        <dt>Datert</dt><dd>${esc(fmt(q.datert, true))}</dd>
        ${q.besvart ? `<dt>Besvart</dt><dd>${esc(fmt(q.besvart, true))}${svartid !== null ? ` · ${plural(svartid, "dag", "dager")} svartid` : ""}</dd>` : ""}
        ${q.tema?.length ? `<dt>Tema</dt><dd>${q.tema.map((t) => `<span class="tag">${esc(t)}</span>`).join(" ")}</dd>` : ""}
      </dl>
      <a class="cta" href="${esc(q.url)}" target="_blank" rel="noopener">${q.status === "besvart" ? "Les svaret på stortinget.no" : "Se spørsmålet på stortinget.no"} ↗</a>`;
  }

  // ---------- Ruting ----------
  const TABS = { oversikt: viewOversikt, saker: viewSaker, sporsmal: viewSporsmal, horinger: viewHoringer, kalender: viewKalender, nyheter: viewRegjeringen };
  const route = () => {
    let [, tab, id] = (location.hash || "#/oversikt").split("/");
    if (tab === "regjeringen") tab = "nyheter";
    return { tab: TABS[tab] ? tab : "oversikt", id };
  };
  let curTab = null;
  function go() {
    const r = route();
    document.querySelectorAll(".tabs a").forEach((a) => (a.dataset.tab === r.tab ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current")));
    if (r.tab !== curTab || !r.id) {
      if (r.tab !== curTab) window.scrollTo(0, 0);
      curTab = r.tab; TABS[r.tab]();
      document.title = r.tab === "oversikt" ? "Energi på Stortinget" : `${$(".tabs a[aria-current]")?.textContent.trim()} – Energi på Stortinget`;
    }
    if (r.id) {
      const id = Number(r.id);
      if (r.tab === "saker" && D.sakById.has(id)) openSheet(sakSheet(D.sakById.get(id)));
      else if (r.tab === "sporsmal" && D.spmById.has(id)) openSheet(spmSheet(D.spmById.get(id)));
      else closeSheet(true);
    } else closeSheet(true);
  }
  window.addEventListener("hashchange", go);

  // Klikk på hele feed-raden
  document.addEventListener("click", (e) => {
    const li = e.target.closest("li.clickable");
    if (!li || e.target.closest("a")) return;
    if (li.dataset.ext) window.open(li.dataset.href, "_blank", "noopener"); else location.hash = li.dataset.href;
  });

  // ---------- Oppstart ----------
  function footer() {
    const k = Object.entries(D.kilder);
    $("#foot").innerHTML = `<details><summary>Om siden og datakildene</summary>
      <p>Data hentes automatisk fra <a href="https://data.stortinget.no" target="_blank" rel="noopener">Stortingets åpne data</a>, Stortingets RSS-feeder (ubesvarte spørsmål og hovedtema Energi) , <a href="https://www.regjeringen.no/no/dokument/hoyringar/id1763/" target="_blank" rel="noopener">regjeringen.no</a> (nyheter og høringer fra Energidepartementet, og høringer om petroleum fra alle departementer) og <a href="https://www.miljodirektoratet.no/hoeringer/" target="_blank" rel="noopener">Miljødirektoratets høringer</a> (olje og gass, energi og klima). Høringsfrister fra regjeringen.no står bare på selve høringssiden. Saker regnes som energisaker når de er merket med energitema av Stortinget, eller tittelen inneholder energirelaterte ord. Sist oppdatert ${esc(fmt(D.generert, true))} kl. ${esc(fmtTime(D.generert))}.</p>
      <ul>${k.map(([n, v]) => `<li><span class="${v.ok ? "ok" : "err"}">${v.ok ? "✓" : "✗"}</span> ${esc(n)}${v.ok ? (v.antall !== null ? ` – ${v.antall}` : "") : ` – feil: ${esc(v.feil)}`}</li>`).join("")}</ul>
      <p>Abonner på nye hendelser med <a href="feed.xml">RSS-feeden</a>.</p></details>`;
  }

  fetch("data/energi.json", { cache: "no-cache" })
    .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then((d) => {
      D = d;
      D.sakById = new Map(d.saker.map((s) => [s.id, s]));
      D.spmById = new Map(d.sporsmal.map((q) => [q.id, q]));
      D.hor = buildHoringer();
      $("#updated").textContent = `Oppdatert ${fmt(d.generert)} kl. ${fmtTime(d.generert)} · sesjon ${d.sesjon}`;
      footer();
      go();
    })
    .catch((err) => {
      main.innerHTML = empty("Kunne ikke laste data", `Prøv å laste siden på nytt. (${err.message})`);
    });
})();
