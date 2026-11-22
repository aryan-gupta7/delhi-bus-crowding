"use strict";
const COLORS = { 0: "#9aa3ad", 1: "#9ad0c4", 2: "#3b8f87", 3: "#0b4f56" };
const WIDTH = { 0: 3, 1: 3, 2: 5, 3: 7 };           // level is also carried by width, glyph count and word
const $ = (id) => document.getElementById(id);
let map, mapReady = false;
const stopIds = {};                                  // displayed label -> stop_id

function showTab(name) {
  for (const t of document.querySelectorAll(".tab")) t.classList.toggle("active", t.dataset.tab === name);
  $("plan").hidden = name !== "plan"; $("operator").hidden = name !== "operator";
  if (name === "operator" && !$("heatmap").dataset.loaded) loadHeatmap();
}

async function getJson(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
}

// -- stop search ---------------------------------------------------------------------------------
function wireSearch(inputId, listId) {
  const input = $(inputId), list = $(listId);
  let timer;
  input.addEventListener("input", () => {
    clearTimeout(timer);
    if (input.value.length < 2) return;
    timer = setTimeout(async () => {
      const rows = await getJson("/stops?q=" + encodeURIComponent(input.value)).catch(() => []);
      list.replaceChildren(...rows.map((s) => {
        const label = `${s.name} (${s.stop_id})`;
        stopIds[label] = s.stop_id;
        const o = document.createElement("option"); o.value = label; return o;
      }));
    }, 200);
  });
}

// -- cards ---------------------------------------------------------------------------------------
const levelText = (l) => `${l.glyph} ${l.word}`;
function legHtml(leg) {
  const hatch = leg.tier === "Low" || leg.tier === "No estimate" ? " hatch" : "";
  const firm = leg.robust_in_range ? "" : ' <span class="pill" title="The level depends on assumptions about who our tickets represent">leans</span>';
  return `<div class="leg"><strong>Bus ${leg.route}</strong> ${leg.board} ${leg.from} → ${leg.alight} ${leg.to}
    <span class="muted">(${leg.minutes} min)</span><br>
    <span class="pill l${leg.level.code}${hatch}">${levelText(leg.level)}</span>${firm}
    <span class="muted"> evidence: ${leg.tier}</span></div>`;
}
function cardHtml(c) {
  const note = c.note ? `<p class="muted">${c.note}</p>` : "";
  const gamma = c.robustness ? `<p class="muted" title="Robustness value">${c.robustness.note}</p>` : "";
  return `<article class="card"><h3>${c.title}</h3>
    <div class="big">${c.depart} → ${c.arrive} · ${c.minutes} min</div>
    <div>${c.transfers === 0 ? "Direct" : c.transfers + " transfer"} · <span class="pill l${c.level.code}">${levelText(c.level)}</span></div>
    ${c.legs.map(legHtml).join("")}${note}${gamma}</article>`;
}

function drawLegs(cards) {
  if (!mapReady) return;
  const features = [];
  for (const c of Object.values(cards))
    for (const leg of c.legs)
      for (const s of leg.stretches)
        features.push({ type: "Feature", properties: { level: s.level.code }, geometry: { type: "LineString", coordinates: s.coords } });
  setLines({ type: "FeatureCollection", features });
}

async function plan(ev) {
  ev.preventDefault();
  const from = stopIds[$("from").value], to = stopIds[$("to").value];
  const status = $("status"); status.className = ""; $("cards").replaceChildren();
  if (!from || !to) { status.textContent = "Pick both stops from the suggestions."; status.className = "error"; return; }
  status.textContent = "Searching…";
  try {
    const q = new URLSearchParams({ from_stop: from, to_stop: to, time: $("time").value, day: $("day").value });
    const r = await getJson("/plan?" + q);
    status.textContent = r.message && !Object.keys(r.cards).length ? r.message : "";
    $("cards").innerHTML = Object.values(r.cards).map(cardHtml).join("") + (r.message && Object.keys(r.cards).length ? `<p><strong>${r.message}</strong></p>` : "");
    $("footnotes").textContent = `${r.usually} ${r.basis} ${r.sample}`;
    drawLegs(r.cards);
  } catch (e) { status.textContent = e.message; status.className = "error"; }
}

// -- operator view -------------------------------------------------------------------------------
async function loadHeatmap() {
  const day = $("op-day").value;
  const r = await getJson("/operator/heatmap?day=" + day);
  const head = "<tr><th>Route</th>" + [...Array(24).keys()].map((h) => `<th>${h}</th>`).join("") + "</tr>";
  const rows = r.routes.map((route) => "<tr><th data-route='" + route + "'>" + route + "</th>" + r.grid[route].map((c) => {
    if (!c) return "<td></td>";
    const hatch = c.tier === "Low" || c.tier === "No estimate" ? " hatch" : "";
    return `<td class="c${c.level.code}${hatch}" title="${c.level.word} · evidence ${c.tier}${c.robust_in_range ? "" : " · leans"}">${c.level.code ? c.level.glyph.length : "?"}</td>`;
  }).join("") + "</tr>");
  $("heatmap").innerHTML = "<table>" + head + rows.join("") + "</table>"; $("heatmap").dataset.loaded = "1";
}
async function drawRoute(route) {
  const q = new URLSearchParams({ route, hour: $("op-hour").value, day: $("op-day").value });
  const fc = await getJson("/operator/stretches?" + q);
  for (const f of fc.features) f.properties.level = f.properties.level.code;
  setLines(fc);
  const xs = fc.features.flatMap((f) => f.geometry.coordinates);
  if (xs.length) map.fitBounds([[Math.min(...xs.map((p) => p[0])), Math.min(...xs.map((p) => p[1]))],
                                [Math.max(...xs.map((p) => p[0])), Math.max(...xs.map((p) => p[1]))]], { padding: 40 });
}

// -- map -----------------------------------------------------------------------------------------
function setLines(fc) { map.getSource("lines").setData(fc); }
function initMap() {
  map = new maplibregl.Map({
    container: "map", center: [77.2, 28.62], zoom: 10,
    style: { version: 8, sources: { osm: { type: "raster", tileSize: 256, attribution: "© OpenStreetMap contributors",
             tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"] } }, layers: [{ id: "osm", type: "raster", source: "osm" }] },
  });
  map.on("load", () => {
    map.addSource("lines", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
    map.addLayer({ id: "lines", type: "line", source: "lines", layout: { "line-cap": "round" },
      paint: { "line-color": ["match", ["get", "level"], 1, COLORS[1], 2, COLORS[2], 3, COLORS[3], COLORS[0]],
               "line-width": ["match", ["get", "level"], 1, WIDTH[1], 2, WIDTH[2], 3, WIDTH[3], WIDTH[0]],
               "line-dasharray": ["case", ["==", ["get", "level"], 0], ["literal", [2, 2]], ["literal", [1, 0]]] } });
    mapReady = true;
  });
}

document.addEventListener("DOMContentLoaded", () => {
  for (const h of [...Array(24).keys()]) $("op-hour").add(new Option(String(h).padStart(2, "0") + ":00", h, h === 9, h === 9));
  document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => showTab(t.dataset.tab)));
  $("plan-form").addEventListener("submit", plan);
  $("op-day").addEventListener("change", loadHeatmap);
  $("heatmap").addEventListener("click", (e) => { if (e.target.dataset.route) drawRoute(e.target.dataset.route); });
  wireSearch("from", "from-list"); wireSearch("to", "to-list");
  initMap();
});
