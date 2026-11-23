"use strict";
/* Delhi bus crowding: planner and operator view. All numbers come from the HTTP API (crowd/api/app.py);
   nothing is recomputed here. Wording rules: usually (never now), relative levels, no "seats available". */
const $ = (id) => document.getElementById(id);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const store = {
  get(key, fallback) { try { return localStorage.getItem(key) ?? fallback; } catch { return fallback; } },
  set(key, value) { try { localStorage.setItem(key, value); } catch { /* private mode: keep going */ } },
};
const state = { lang: store.get("lang", "en"), theme: store.get("theme", "auto"), view: "plan", planDay: "weekday", plan: null, query: null,
  mapHour: null, stopIds: {}, opDay: "weekday", opHour: 9, heat: null, cell: null, examples: [], tip: {} };
const TIER_RANK = { "No estimate": 0, Low: 1, Medium: 2, High: 3 };
const TIER_CLS = { Medium: " tm", Low: " tl" };
const HEAT_HOURS = Array.from({ length: 17 }, (_, i) => i + 5);

function t(key, vars = {}) {
  const raw = (STRINGS[state.lang][key] ?? STRINGS.en[key] ?? key);
  return raw.replace(/\{(\w+)\}/g, (_, name) => vars[name] ?? "");
}
async function api(path, params = {}) {
  const res = await fetch(path + (Object.keys(params).length ? "?" + new URLSearchParams(params) : ""));
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText);
  return res.json();
}
const stopLabel = (s) => { const label = `${s.name} (${s.stop_id})`; state.stopIds[label] = s.stop_id; return label; };
const pips = (n) => '<i class="p"></i>'.repeat(n);
function levelPill(code, tier = "High", size = "") {
  if (code === 0) return `<span class="lv l0 ${size}">? ${esc(t("L0"))}</span>`;
  return `<span class="lv l${code}${TIER_CLS[tier] || ""} ${size}">${pips(code)}${esc(t("L" + code))}</span>`;
}
const lowestTier = (legs) => legs.reduce((a, l) => (TIER_RANK[l.tier] < TIER_RANK[a] ? l.tier : a), "High");
const monoTimes = (text) => esc(text).replace(/\b\d{2}:\d{2}\b/g, '<span class="mono">$&</span>');   // clock times are set in Geist Mono
const clock = (m) => `${String(Math.floor(m / 60) % 24).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;

// ---- theme, language, static text ----------------------------------------------------------------
function applyTheme() {
  if (state.theme === "auto") document.documentElement.removeAttribute("data-theme"); else document.documentElement.dataset.theme = state.theme;
  for (const b of $("seg-theme").children) { b.classList.toggle("on", b.dataset.theme === state.theme); b.setAttribute("aria-pressed", b.dataset.theme === state.theme); }
  recolourMap();
}
function applyLang() {
  document.documentElement.lang = state.lang;
  for (const el of document.querySelectorAll("[data-i18n]")) el.textContent = t(el.dataset.i18n);
  for (const el of document.querySelectorAll("[data-i18n-ph]")) el.placeholder = t(el.dataset.i18nPh);
  for (const el of document.querySelectorAll("[data-i18n-label]")) el.setAttribute("aria-label", t(el.dataset.i18nLabel));
  for (const b of $("seg-lang").children) { b.classList.toggle("on", b.dataset.lang === state.lang); b.setAttribute("aria-pressed", b.dataset.lang === state.lang); }
  renderLegend(); renderExamples(); renderPlan(); renderHeat(); renderCell(); renderInfo(); renderOperatorLists();
}
function setSeg(group, attr, value) {
  for (const b of group.children) { b.classList.toggle("on", b.dataset[attr] === value); b.setAttribute("aria-pressed", b.dataset[attr] === value); }
}
const levelLegend = () => [1, 2, 3, 0].map((c) => levelPill(c, "High", "sm")).join("");
function renderLegend() { $("legend").innerHTML = levelLegend(); $("op-legend").innerHTML = levelLegend(); $("maplabel").textContent = t("schematic"); }

// ---- stop search ---------------------------------------------------------------------------------
const optionList = (rows) => rows.map((s) => { const option = document.createElement("option"); option.value = stopLabel(s); return option; });
function wireSearch(inputId, listId) {
  const input = $(inputId), list = $(listId);
  let timer;
  api("/stops", { limit: 60 }).then((rows) => list.replaceChildren(...optionList(rows))).catch(() => {});   // the A to Z list, before anything is typed
  input.addEventListener("input", () => {
    clearTimeout(timer);
    if (input.value.length < 2) return;
    timer = setTimeout(async () => {
      const rows = await api("/stops", { q: input.value, limit: 12 }).catch(() => []);
      list.replaceChildren(...optionList(rows));
    }, 200);
  });
}

// ---- planner results -----------------------------------------------------------------------------
function robustText(card) {
  const g = card.robustness; if (!g) return "";
  if (g.status === "finite") return t("robust", { n: g.gamma_star.toFixed(1) });
  if (g.status === "beyond_max") return t("robustBeyond", { n: 10 });
  return g.status === "not_applicable" ? t("robustNA") : "";
}
function optionHtml(card, picked) {
  const tier = lowestTier(card.legs);
  const leaning = card.legs.some((l) => !l.robust_in_range);
  const routes = card.legs.map((l) => `<span class="rt mono">${esc(l.route)}</span>`).join(" ");
  const via = card.transfers === 0 ? t("direct") : t(card.transfers === 1 ? "transfer" : "transfers", { n: card.transfers });
  const marks = [leaning ? `<span class="badge ln" title="${esc(t("leansTip"))}">${t("leans")}</span>` : "",
                 card.partly_estimated ? `<span class="badge">${t("partly")}</span>` : ""].join("");
  const foot = card.robustness ? `<div class="foot"><span class="badge" title="${esc(t("firmTip"))}">${leaning ? t("leans") : t("firm")}</span><p class="sec small" style="flex:1;min-width:200px">${esc(robustText(card))}</p></div>` : "";
  return `<article class="card opt${picked ? " pick" : ""}"><div class="head"><span style="display:flex;gap:6px;flex-wrap:wrap">${routes}</span>
    <span style="display:flex;gap:6px;align-items:center">${picked ? "" : marks}<span class="badge${picked ? " inv" : ""}">${esc(t(picked ? "comfortable" : "fastest"))}</span></span></div>
    <div class="main">${levelPill(card.level.code, tier, "big")}<span><span class="dsp mins">${Math.round(card.minutes)}</span> <span class="sec">${esc(t("min"))}</span></span></div>
    <p class="desc sec">${esc(t("fromTo", { from: card.legs[0].from, to: card.legs[card.legs.length - 1].to }))}, ${esc(via)} <span class="mono">${card.depart}–${card.arrive}</span></p>
    ${picked ? `<p class="small mut" style="margin-top:4px">${marks}</p>` : ""}${foot}${detailsHtml(card)}</article>`;
}
function stripHtml(leg, key) {
  return `<div class="strip" data-key="${key}">${leg.stretches.map((s, i) => {
    const cls = `sg l${s.level.code}${TIER_CLS[s.tier] || ""}${!s.robust_in_range && s.level.code ? " leaning" : ""}`;
    return `<button type="button" class="${cls}" data-key="${key}" data-i="${i}" aria-label="${esc(t("stretchN", { n: i + 1 }))}, ${esc(t("L" + s.level.code))}${s.robust_in_range ? "" : ", " + esc(t("leans"))}">${pips(s.level.code)}${s.level.code ? "" : "?"}</button>`;
  }).join("")}</div><div class="tip" data-tip="${key}" hidden></div>`;
}
function detailsHtml(card) {
  const hour = card.legs[0].stretches[0]?.hour ?? 0;
  const legs = card.legs.map((leg, li) => `<div class="leg"><p class="small sec" style="font-weight:500">${esc(t("alongRide", { h: String(hour).padStart(2, "0") }))} · ${esc(leg.route)}</p>${stripHtml(leg, `${card.title}-${li}`)}
    <p class="mut tiny" style="margin-top:6px"><span class="l1 tl" style="display:inline-block;width:14px;height:10px;border-radius:3px;border:1px solid var(--l1b);vertical-align:-1px"></span> ${esc(t("hatchedKey"))}</p></div>`).join("");
  return `<details class="det"><summary>${esc(t("details"))}</summary>${legs}${laterHtml()}</details>`;
}
function laterHtml() {
  const rows = state.plan?.leave_later?.offsets || [];
  if (!rows.length) return "";
  const ticks = [0, ...rows.map((r) => r.offset)];
  return `<div class="leg"><div style="display:flex;justify-content:space-between;align-items:baseline"><p class="small sec" style="font-weight:500">${esc(t("laterTitle"))}</p><p class="mono small" data-readout style="color:var(--acc-i)"></p></div>
    <div class="slider" data-slider><span class="readout" data-hour hidden></span><div class="trk"><div class="fill"></div><div class="bead"></div></div>
    <div class="ticks">${ticks.map((o) => `<button type="button" class="tick mono${o === 0 ? " on" : ""}" data-offset="${o}" aria-label="${esc(o === 0 ? t("now") : "+" + o)}"><span>${o === 0 ? esc(t("now")) : "+" + o}</span></button>`).join("")}</div></div>
    <p class="small" data-later style="margin-top:8px"></p></div>`;
}
function renderPlan() {
  const r = state.plan, box = $("results");
  if (!r) { box.innerHTML = ""; $("foot").textContent = ""; return; }
  const cards = Object.values(r.cards);
  if (!cards.length) { box.innerHTML = `<div class="card none"><p class="dsp" style="font-size:20px">${esc(t("noService"))}</p></div>`; return; }
  const parts = [`<p class="sec small" style="font-weight:500">${monoTimes(t("optionsFor", { n: cards.length, day: t("day_" + r.query.day_type), time: r.query.time }))}</p>`];
  if (r.cards.comfortable) {
    parts.push(optionHtml(r.cards.fastest, false), optionHtml(r.cards.comfortable, true));
  } else {
    parts.push(`<div class="card none"><h2 class="dsp" style="font-size:22px">${esc(t("noCalmer"))}</h2>
      <p class="sec" style="margin-top:6px;font-size:14px;line-height:1.45">${esc(t("noCalmerWhy", { r: r.evidence.route_switch_ratio.toFixed(1) }))}</p>
      <button class="lk small" type="button" id="why">${esc(t("whyCant"))}</button></div>`, optionHtml(r.cards.fastest, false));
    const chip = r.leave_later?.chip;
    if (chip) parts.push(`<button class="chip" type="button" data-chip="${chip.offset}"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg><span style="flex:1"><b>${esc(t("later", { n: chip.offset }))}</b><span class="sec small">${monoTimes(t("laterSub", { h: chip.depart.slice(0, 2) + ":00", n: Math.round(chip.arrives_later_by) }))}</span></span></button>`);
    if (r.compared) parts.push(`<div class="card" style="padding:12px 16px;border-radius:20px"><p class="sec small" style="font-weight:500">${esc(t("compared"))}</p>
      <div style="display:flex;align-items:center;gap:8px;margin-top:8px;flex-wrap:wrap">${r.compared.routes.map((x) => `<span class="rt sm mono">${esc(x)}</span>`).join("→")}${levelPill(r.compared.level.code, "High", "sm")}</div>
      ${r.compared.partly_estimated ? `<div style="display:flex;align-items:center;gap:8px;margin-top:8px"><span class="badge">${t("partly")}</span><p class="mut tiny">${esc(t("partlyNote"))}</p></div>` : ""}</div>`);
  }
  box.innerHTML = parts.join("");
  const rough = r.query.day_type === "weekend" ? " " + t("roughWeekend") : "";
  $("foot").textContent = `${t("usually", { period: r.period })} ${r.query.day_type === "weekend" ? t("basisWeekend") : t("basisWeekday")}${rough} ${t("sample")}`;
}
$("results").addEventListener("click", (ev) => {
  const seg = ev.target.closest(".sg");
  if (seg) return showTip(seg);
  const step = ev.target.closest(".tick");
  if (step) return showLater(step);
  if (ev.target.closest("#why")) { $("info").showModal(); return; }
  const chip = ev.target.closest("[data-chip]");
  if (chip) { const details = $("results").querySelector("details"); if (details) { details.open = true; $("results").querySelector(`.tick[data-offset="${chip.dataset.chip}"]`)?.click(); details.scrollIntoView({ block: "nearest" }); } }
});
function findLeg(key) {
  const [title, li] = [key.slice(0, key.lastIndexOf("-")), Number(key.slice(key.lastIndexOf("-") + 1))];
  const card = Object.values(state.plan.cards).find((c) => c.title === title);
  return card?.legs[li];
}
function showTip(btn) {
  const leg = findLeg(btn.dataset.key), s = leg?.stretches[Number(btn.dataset.i)];
  const tip = btn.closest(".leg").querySelector(".tip");
  if (!s) return;
  let html;
  if (s.level.code === 0) html = `<p class="small">${levelPill(0, "No estimate", "sm")}</p><p class="mut tiny" style="margin-top:6px">${esc(t("partlyNote"))}</p>`;
  else {
    const shares = (s.shares || []).map((p, i) => (p >= 0.05 ? levelPill(i + 1, "High", "sm") + `<span class="small"> ${Math.round(p * 100)}%</span>` : "")).join(" ");
    const head = s.robust_in_range ? `<span class="badge" title="${esc(t("firmTip"))}">${t("firm")}</span>` : `<span class="badge ln">${t("leans")}</span>`;
    html = `<div style="display:flex;align-items:center;gap:8px">${head}<b style="font-weight:500;font-size:14px">${esc(t("stretchN", { n: Number(btn.dataset.i) + 1 }))}, ${esc(t("L" + s.level.code))}</b></div>
      <div style="display:flex;gap:6px;margin-top:10px;flex-wrap:wrap;align-items:center">${shares}</div>
      <p class="mut tiny" style="margin-top:8px">${esc(t("draws"))} ${s.robust_in_range ? esc(t("firmTip")) : esc(t("leansTip"))} · ${esc(t("evidence"))}: ${esc(t("T_" + s.tier))}</p>`;
  }
  tip.innerHTML = html; tip.hidden = false;
}
function showLater(btn) {
  const wrap = btn.closest(".leg"), ticks = [...wrap.querySelectorAll(".tick")];
  const offset = Number(btn.dataset.offset), pct = (100 * ticks.indexOf(btn)) / (ticks.length - 1);
  for (const b of ticks) b.classList.toggle("on", b === btn);
  wrap.querySelector(".fill").style.width = pct + "%";
  const bead = wrap.querySelector(".bead"); bead.style.left = pct + "%";
  const out = wrap.querySelector("[data-later]"), readout = wrap.querySelector("[data-readout]"), hour = wrap.querySelector("[data-hour]");
  const row = state.plan.leave_later.offsets.find((r) => r.offset === offset);
  if (!row) { out.innerHTML = ""; readout.textContent = ""; hour.hidden = true; return; }
  readout.textContent = `+${offset} ${t("min")}, ${row.depart}`;
  hour.hidden = false; hour.style.left = `calc(${pct}% )`; hour.textContent = `${row.depart.slice(0, 2)}:00 ${t("hourWord")}: ${t("L" + row.level_code)}`;
  out.innerHTML = `${levelPill(row.level_code, "High", "sm")} <span class="mut tiny">${esc(t("min"))} +${Math.round(row.arrives_later_by)}</span>`;
}
async function submitPlan(ev) {
  ev?.preventDefault();
  const from = state.stopIds[$("from").value], to = state.stopIds[$("to").value], status = $("status");
  status.className = "small";
  if (!from || !to) { status.textContent = t("pickBoth"); status.className = "small error"; return; }
  status.textContent = t("searching");
  try {
    const q = { from_stop: from, to_stop: to, time: $("time").value, day: state.planDay };
    state.plan = await api("/plan", q); state.query = q;
    status.textContent = state.plan.message && !Object.keys(state.plan.cards).length ? t("noService") : "";
    state.mapHour = Number(q.time.slice(0, 2));
    renderPlan(); renderHours(); await drawPlanOnMap();
  } catch (e) { status.textContent = t("error"); status.className = "small error"; }
}

// ---- examples ------------------------------------------------------------------------------------
async function loadExamples() {
  state.examples = await api("/examples").catch(() => []);
  renderExamples();
}
function renderExamples() {
  $("examples-wrap").hidden = !state.examples.length;
  $("examples").innerHTML = state.examples.map((e, i) => `<button type="button" class="ex" data-i="${i}"><span style="flex:1;min-width:0"><span style="display:block;font-weight:500">${esc(t("fromTo", { from: e.from.name, to: e.to.name }))}</span><span class="mut small">${esc(t("weekday"))}, <span class="mono">${esc(e.time)}</span></span></span><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" aria-hidden="true" class="mut"><path d="M9 6l6 6-6 6"/></svg></button>`).join("");
}
$("examples").addEventListener("click", (ev) => {
  const b = ev.target.closest(".ex"); if (!b) return;
  const e = state.examples[Number(b.dataset.i)];
  $("from").value = stopLabel(e.from); $("to").value = stopLabel(e.to); $("time").value = e.time;
  state.planDay = "weekday"; setSeg($("seg-day"), "day", "weekday"); submitPlan();
});

// ---- map -----------------------------------------------------------------------------------------
let map = null, mapReady = false, marker = null;
const cssVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
function levelPaint(kind) {   // kind: "fill" for --lN, "line" for --lNb
  const suffix = kind === "line" ? "b" : "";
  return ["match", ["get", "level"], 1, cssVar("--l1" + suffix), 2, cssVar("--l2" + suffix), 3, cssVar("--l3" + suffix), cssVar("--mut")];
}
function recolourMap() {
  if (!mapReady) return;
  map.setPaintProperty("casing", "line-color", levelPaint("line"));
  map.setPaintProperty("fill", "line-color", levelPaint("fill"));
  map.setPaintProperty("none", "line-color", cssVar("--mut"));
  const dark = getComputedStyle(document.documentElement).getPropertyValue("--bg").trim().toLowerCase() === "#0e0f11";
  map.setPaintProperty("base", "raster-brightness-max", dark ? 0.4 : 1);     // street map in greys so only the levels carry colour
  map.setPaintProperty("base", "raster-saturation", -1);
}
function initMap() {
  map = new maplibregl.Map({ container: "map", center: [77.2, 28.62], zoom: 10,
    style: { version: 8, sources: { osm: { type: "raster", tileSize: 256, attribution: "© OpenStreetMap contributors", tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"] } },
             layers: [{ id: "base", type: "raster", source: "osm" }] } });
  map.on("style.load", () => {          // do not wait for tiles: the lines must work offline
    map.addSource("legs", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
    const width = ["get", "w"];
    map.addLayer({ id: "casing", type: "line", source: "legs", filter: [">", ["get", "level"], 0], layout: { "line-cap": "round" }, paint: { "line-color": levelPaint("line"), "line-width": ["+", width, 3] } });
    map.addLayer({ id: "fill", type: "line", source: "legs", filter: [">", ["get", "level"], 0], layout: { "line-cap": "round" }, paint: { "line-color": levelPaint("fill"), "line-width": width } });
    map.addLayer({ id: "none", type: "line", source: "legs", filter: ["==", ["get", "level"], 0], paint: { "line-color": cssVar("--mut"), "line-width": 4, "line-dasharray": [2, 2] } });
    mapReady = true; map.resize(); recolourMap();
    if (state.plan) drawPlanOnMap();
  });
}
function lineFeatures(items) {   // items: {coords, level, flow, label}; width follows sampled flow
  const peak = Math.max(1, ...items.map((i) => i.flow));
  return items.map((i) => ({ type: "Feature", properties: { level: i.level, w: 4 + 12 * Math.sqrt(i.flow / peak), label: i.label },
                             geometry: { type: "LineString", coordinates: i.coords } }));
}
const stretchCache = {};
async function stretchesFor(route, hour) {
  const key = `${route}|${hour}|${state.query.day}`;
  stretchCache[key] ??= api("/operator/stretches", { route, hour, day: state.query.day });
  return stretchCache[key];
}
function planStretches() {
  return Object.values(state.plan.cards).flatMap((c) => c.legs.flatMap((l) => l.stretches.map((s) => ({ ...s, route: l.route }))));
}
async function drawPlanOnMap() {
  if (!mapReady || !state.plan) return;
  const planHour = Number(state.query.time.slice(0, 2));
  let items = planStretches().map((s) => ({ coords: s.coords, level: s.level.code, flow: s.flow, label: s.route, pi: s.pi }));
  if (state.mapHour !== planHour) {          // another hour: take the route's stretch levels for that hour
    const routes = [...new Set(planStretches().map((s) => s.route))];
    const byRoute = Object.fromEntries(await Promise.all(routes.map(async (r) => [r, (await stretchesFor(r, state.mapHour)).features])));
    items = planStretches().map((s) => {
      const f = byRoute[s.route].find((x) => x.properties.stretch_id === s.stretch_id);
      return { coords: s.coords, level: f ? f.properties.level.code : 0, flow: f ? f.properties.flow : 0, label: s.route, pi: f ? f.properties.pi || 0 : 0 };
    });
  }
  map.getSource("legs").setData({ type: "FeatureCollection", features: lineFeatures(items) });
  const pts = items.flatMap((i) => i.coords);
  if (pts.length) map.fitBounds([[Math.min(...pts.map((p) => p[0])), Math.min(...pts.map((p) => p[1]))], [Math.max(...pts.map((p) => p[0])), Math.max(...pts.map((p) => p[1]))]], { padding: 70, maxZoom: 14 });
  marker?.remove();
  const worst = items.filter((i) => i.level > 0).sort((a, b) => b.pi - a.pi)[0];
  if (worst) {
    const el = document.createElement("div"); el.className = "pinch";
    el.textContent = `${t("pinch")}: ${worst.label}, ${t("L" + worst.level)}, ${String(state.mapHour).padStart(2, "0")}:00`;
    marker = new maplibregl.Marker({ element: el }).setLngLat(worst.coords[Math.floor(worst.coords.length / 2)]).addTo(map);
  }
}
function renderHours() {
  const base = state.mapHour, bar = $("seg-hours");
  const hours = [base - 1, base, base + 1].filter((h) => h >= 0 && h <= 23);
  bar.hidden = false;
  bar.innerHTML = hours.map((h) => `<button type="button" data-h="${h}" class="${h === base ? "on" : ""}" aria-pressed="${h === base}">${String(h).padStart(2, "0")}:00</button>`).join("");
  bar.dataset.base = base;
}
$("seg-hours").addEventListener("click", (ev) => {
  const b = ev.target.closest("button"); if (!b) return;
  state.mapHour = Number(b.dataset.h);
  for (const x of $("seg-hours").children) { x.classList.toggle("on", x === b); x.setAttribute("aria-pressed", x === b); }
  drawPlanOnMap();
});

// ---- operator view -------------------------------------------------------------------------------
async function loadOperator() {
  const [heat, over, relief] = await Promise.all([api("/operator/heatmap", { day: state.opDay, limit: 14 }), api("/operator/overloaded", { day: state.opDay }), api("/operator/relief", { day: state.opDay })]);
  state.heat = heat; state.over = over; state.relief = relief;
  renderHeat(); renderOperatorLists();
  if (!state.cell || state.cell.day !== state.opDay) {
    const route = heat.routes[0], c = heat.grid[route][state.opHour];
    if (c) await selectCell(route, state.opHour);
  }
}
function renderHeat() {
  const h = state.heat; if (!h) { $("heat").innerHTML = ""; return; }
  const cols = `grid-template-columns:96px repeat(${HEAT_HOURS.length},minmax(0,1fr))`;
  const head = `<div class="heat" style="${cols};margin-bottom:4px"><span></span>${HEAT_HOURS.map((x) => `<span class="hh">${String(x).padStart(2, "0")}</span>`).join("")}</div>`;
  const rows = h.routes.map((r) => `<div class="heat" style="${cols};margin-bottom:4px"><button class="rl" type="button" data-route="${esc(r)}" title="${esc(t("coverage"))}: ${Math.round(h.coverage[r] * 100)}%">${esc(r)}</button>` +
    HEAT_HOURS.map((x) => {
      const c = h.grid[r][x];
      if (!c) return `<span class="c l0" aria-hidden="true"></span>`;
      const sel = state.cell && state.cell.route === r && state.cell.hour === x ? " sel" : "";
      const label = `${r} ${String(x).padStart(2, "0")}:00, ${t("L" + c.level.code)}, ${t("evidence")}: ${t("T_" + c.tier)}${c.robust_in_range ? "" : ", " + t("leans")}`;
      return `<button type="button" class="c l${c.level.code}${TIER_CLS[c.tier] || ""}${sel}" data-route="${esc(r)}" data-hour="${x}" title="${esc(label)}" aria-label="${esc(label)}">${c.level.code ? "•".repeat(c.level.code) : "?"}</button>`;
    }).join("") + "</div>").join("");
  $("heat").innerHTML = head + rows;
}
$("heat").addEventListener("click", (ev) => {
  const b = ev.target.closest("[data-route]"); if (!b) return;
  selectCell(b.dataset.route, b.dataset.hour ? Number(b.dataset.hour) : state.opHour);
});
async function selectCell(route, hour) {
  const c = state.heat.grid[route][hour];
  state.opHour = hour; $("op-hour").value = hour;
  if (!c) { state.cell = null; renderHeat(); renderCell(); return; }
  state.cell = { ...(await api("/operator/cell", { route, stretch_id: c.stretch_id, hour, day: state.opDay })) };
  renderHeat(); renderCell();
}
function renderCell() {
  const c = state.cell, box = $("det");
  if (!c) { box.innerHTML = `<p class="mut small" style="margin-top:8px">${esc(t("pickCell"))}</p>`; $("det-title").textContent = t("detail"); return; }
  $("det-title").textContent = `${c.route}, ${c.label}`;
  const kv = (k, v) => `<div class="kv"><span>${esc(t(k))}</span><span style="font-weight:500">${esc(v)}</span></div>`;
  box.innerHTML = `<p class="mut small" style="margin-top:2px">${esc(t(c.day === "weekend" ? "weekend" : "weekday"))}, ${String(c.hour).padStart(2, "0")}:00</p>
    <div style="display:flex;gap:8px;margin-top:12px;flex-wrap:wrap;align-items:center">${levelPill(c.level.code, c.tier, "")}<span class="badge">${esc(t("T_" + c.tier))}</span>${c.level.code ? `<span class="badge${c.robust_in_range ? "" : " ln"}">${esc(t(c.robust_in_range ? "firm" : "leans"))}</span>` : ""}</div>
    <div style="margin-top:12px">${kv("pressure", `${c.pi.toFixed(2)} (${c.pi_range[0].toFixed(2)} – ${c.pi_range[1].toFixed(2)})`)}${kv("buses", c.buses_per_hour.toFixed(0))}${kv("tickets", Math.round(c.effective_tickets))}
      ${kv("coverage", `${Math.round(c.route_coverage * 100)}%`)}<div class="kv" style="border-bottom:0"><span>${esc(t("seats"))}</span><span style="font-weight:500">${esc(t("seatsVal", { n: c.seats_per_bus.toFixed(0) }))}</span></div></div>
    <div class="scn"><p class="sec small">${esc(t("pps"))}</p><p class="dsp" style="font-size:22px;margin-top:4px">${c.scenario_passengers_per_seat[0]} – ${c.scenario_passengers_per_seat[1]}</p><p class="mut tiny" style="margin-top:2px">${esc(t("scenario"))}</p></div>`;
}
function renderOperatorLists() {
  const over = state.over, relief = state.relief;
  if (!over) return;
  $("overloaded").innerHTML = `<thead><tr><th>${esc(t("colRoute"))}</th><th>${esc(t("colStretch"))}</th><th>${esc(t("colHour"))}</th><th>${esc(t("colEvidence"))}</th><th style="text-align:right">${esc(t("colRiders"))}</th><th style="text-align:right">Π</th></tr></thead><tbody>` +
    (over.map((r) => `<tr><td class="mono">${esc(r.route)}</td><td>${esc(r.label)}</td><td class="mono">${String(r.hour).padStart(2, "0")}:00</td><td><span class="badge">${esc(t("T_" + r.tier))}</span></td><td style="text-align:right">${Math.round(r.sampled)}</td><td style="text-align:right">${r.pi.toFixed(2)}</td></tr>`).join("") || `<tr><td colspan="6" class="mut">${esc(t("noRows"))}</td></tr>`) + "</tbody>";
  const top = Math.max(1e-9, ...relief.map((r) => r.relief));
  $("relief").innerHTML = relief.map((r) => `<div><div style="display:flex;justify-content:space-between;gap:8px;font-size:14px"><span><span class="mono">${esc(r.route)}</span> <span class="mut">${esc(r.label)}, N ${r.buses_per_hour.toFixed(0)}</span></span><span class="badge${r.robust_in_range ? "" : " ln"}">${esc(t(r.robust_in_range ? "firm" : "leans"))}</span></div><div class="bar" style="width:${Math.max(4, Math.round(100 * r.relief / top))}%"></div></div>`).join("");
  $("op-foot").textContent = t("footOp", { period: state.plan?.period || "October 2026" });
}

// ---- info sheet ----------------------------------------------------------------------------------
function renderInfo() {
  $("info-body").innerHTML = `<div style="display:flex;gap:6px;flex-wrap:wrap">${levelLegend()}</div>
    <p class="sec" style="font-size:14px">${esc(t("aboutLevels"))}</p>
    <p class="sec small">${esc(t("aboutEvidence"))}</p>
    <p class="sec small"><span class="badge ln">${esc(t("leans"))}</span> ${esc(t("aboutLeans"))} <span class="badge">${esc(t("firm"))}</span> ${esc(t("firmTip"))}</p>
    <p class="sec small">${esc(t("basisWeekday"))} ${esc(t("basisWeekend"))} ${esc(t("roughWeekend"))}</p>
    <p class="sec small">${esc(t("aboutNot"))}</p>${state.lang === "hi" ? `<p class="mut tiny">${esc(t("aboutHindi"))}</p>` : ""}`;
}

// ---- wiring --------------------------------------------------------------------------------------
function showView(view) {
  state.view = view;
  $("view-plan").hidden = view !== "plan"; $("view-op").hidden = view !== "operator";
  $("seg-opday").hidden = $("op-hour-wrap").hidden = view !== "operator";
  setSeg($("seg-view"), "view", view);
  if (view === "operator") { if (!state.heat) loadOperator().catch(() => {}); } else if (map) setTimeout(() => map.resize(), 0);
}
document.addEventListener("DOMContentLoaded", () => {
  for (const h of HEAT_HOURS) $("op-hour").add(new Option(`${String(h).padStart(2, "0")}:00`, h, false, h === state.opHour));
  $("seg-view").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) showView(b.dataset.view); });
  $("seg-theme").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) { state.theme = b.dataset.theme; store.set("theme", state.theme); applyTheme(); } });
  $("seg-lang").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) { state.lang = b.dataset.lang; store.set("lang", state.lang); applyLang(); } });
  $("seg-day").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) { state.planDay = b.dataset.day; setSeg($("seg-day"), "day", state.planDay); } });
  $("seg-opday").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) { state.opDay = b.dataset.day; setSeg($("seg-opday"), "day", state.opDay); state.cell = null; loadOperator().catch(() => {}); } });
  $("op-hour").addEventListener("change", (e) => { state.opHour = Number(e.target.value); if (state.cell) selectCell(state.cell.route, state.opHour); });
  $("time").value = new Date().toTimeString().slice(0, 5);          // leave "now" unless the rider picks a time
  state.planDay = [0, 6].includes(new Date().getDay()) ? "weekend" : "weekday"; setSeg($("seg-day"), "day", state.planDay);
  $("plan-form").addEventListener("submit", submitPlan);
  $("swap").addEventListener("click", () => { const f = $("from").value; $("from").value = $("to").value; $("to").value = f; });
  $("open-info").addEventListener("click", () => $("info").showModal());
  $("close-info").addEventListener("click", () => $("info").close());
  wireSearch("from", "from-list"); wireSearch("to", "to-list");
  window.addEventListener("resize", () => map?.resize());
  initMap(); applyTheme(); applyLang(); loadExamples();
});
