"use strict";

const RANGE_EL = document.getElementById("range");
const COLORS = ["#4ea1ff", "#ffb454", "#3ecf8e", "#ff6b6b", "#b48cff"];
const charts = {}; // panel -> { uplot, raw }

function rangeMinutes() { return parseInt(RANGE_EL.value, 10); }

async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json();
}

// ---------- status cards ----------
function humCard(label, s) {
  const v = s && s.state != null && s.state !== "unknown" ? `${parseFloat(s.state).toFixed(1)}<small>%</small>` : "—";
  return `<div class="card"><div class="label">${label}</div><div class="value">${v}</div></div>`;
}

function renderCards(st) {
  const fan = (st.fan_level && st.fan_level.state) || "—";
  const dehum = st.dehumidifier && st.dehumidifier.state === "on";
  const presence = st.presence && st.presence.state === "on";
  const html = [
    humCard("Bathroom", st.bathroom_humidity),
    humCard("Bathroom (small)", st.bathroom_small_humidity),
    humCard("Bedroom", st.room_humidity),
    `<div class="card"><div class="label">Fan level</div><div class="value" style="text-transform:capitalize">${fan}</div></div>`,
    `<div class="card"><div class="label">Dehumidifier</div><div class="value"><span class="pill ${dehum ? "on" : "off"}">${dehum ? "ON" : "OFF"}</span></div></div>`,
    `<div class="card"><div class="label">Presence</div><div class="value"><span class="pill ${presence ? "detected" : "off"}">${presence ? "DETECTED" : "CLEAR"}</span></div></div>`,
  ].join("");
  document.getElementById("cards").innerHTML = html;
  document.getElementById("updated").textContent = "updated " + new Date().toLocaleTimeString();
}

async function refreshStatus() {
  try { renderCards(await getJSON("/api/status")); }
  catch (e) { console.error(e); }
}

// ---------- charts ----------
// Align per-series [[ts,val]] onto a common x axis for uPlot.
function align(series) {
  const tset = new Set();
  series.forEach(s => s.points.forEach(p => tset.add(p[0])));
  const xs = Array.from(tset).sort((a, b) => a - b);
  const idx = new Map(xs.map((t, i) => [t, i]));
  const ys = series.map(s => {
    const arr = new Array(xs.length).fill(null);
    s.points.forEach(p => { arr[idx.get(p[0])] = p[1]; });
    return arr;
  });
  return [xs, ...ys];
}

function makeChart(panelKey, elId, resp, stepped) {
  const el = document.getElementById(elId);
  const data = align(resp.series);
  const opts = {
    width: el.clientWidth || 600,
    height: 220,
    scales: { x: { time: true }, y: stepped ? { range: [-0.1, 1.1] } : {} },
    legend: { show: resp.series.length > 1 },
    series: [
      {},
      ...resp.series.map((s, i) => ({
        label: s.label,
        stroke: COLORS[i % COLORS.length],
        width: 2,
        spanGaps: !stepped,
        ...(stepped ? { paths: uPlot.paths.stepped({ align: 1 }), points: { show: false } } : {}),
      })),
    ],
    axes: [
      { stroke: "#8b93a3", grid: { stroke: "#2a2f3a" }, ticks: { stroke: "#2a2f3a" } },
      {
        stroke: "#8b93a3", grid: { stroke: "#2a2f3a" }, ticks: { stroke: "#2a2f3a" },
        values: stepped ? (u, vals) => vals.map(v => (v >= 0.5 ? "on" : "off")) : undefined,
        size: 44,
      },
    ],
  };
  if (charts[panelKey] && charts[panelKey].uplot) charts[panelKey].uplot.destroy();
  charts[panelKey] = { uplot: new uPlot(opts, data, el), resp, stepped, elId };
}

async function refreshCharts() {
  const m = rangeMinutes();
  try {
    const [hum, deh, pres] = await Promise.all([
      getJSON(`/api/history?panel=humidity&minutes=${m}`),
      getJSON(`/api/history?panel=dehumidifier&minutes=${m}`),
      getJSON(`/api/history?panel=presence&minutes=${m}`),
    ]);
    makeChart("humidity", "chart-humidity", hum, false);
    makeChart("dehumidifier", "chart-dehumidifier", deh, true);
    makeChart("presence", "chart-presence", pres, true);
  } catch (e) { console.error(e); }
}

// ---------- limits ----------
let saveTimers = {};

function getToken() { return localStorage.getItem("dash_token") || ""; }
function promptToken() {
  const t = window.prompt("Enter the dashboard token to save changes:");
  if (t) localStorage.setItem("dash_token", t.trim());
  return getToken();
}

async function postLimit(name, value, token) {
  return fetch("/api/limits", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Dashboard-Token": token },
    body: JSON.stringify({ name, value: parseFloat(value) }),
  });
}

async function saveLimit(name, value, savedEl) {
  clearTimeout(saveTimers[name]);
  saveTimers[name] = setTimeout(async () => {
    try {
      let r = await postLimit(name, value, getToken());
      if (r.status === 401) {            // need / wrong token — ask once and retry
        const t = promptToken();
        if (t) r = await postLimit(name, value, t);
      }
      if (!r.ok) throw new Error(`save ${name}: HTTP ${r.status}`);
      savedEl.textContent = "saved ✓";
      savedEl.style.color = "";
      savedEl.classList.add("show");
      setTimeout(() => savedEl.classList.remove("show"), 1200);
    } catch (e) {
      console.error(e);
      savedEl.textContent = e.message && e.message.includes("401") ? "auth needed ✗" : "save failed ✗";
      savedEl.style.color = "var(--bad)";
      savedEl.classList.add("show");
    }
  }, 350);
}

async function renderLimits() {
  const limits = await getJSON("/api/limits");
  const groups = {};
  limits.forEach(l => { (groups[l.group] = groups[l.group] || []).push(l); });

  const container = document.getElementById("limits");
  container.innerHTML = "";
  for (const [group, items] of Object.entries(groups)) {
    const g = document.createElement("div");
    g.className = "limit-group";
    g.innerHTML = `<h3>${group}</h3>`;
    items.forEach(l => {
      const row = document.createElement("div");
      row.className = "limit-row";
      row.innerHTML = `
        <div class="name">${l.friendly_name} <span class="saved">saved ✓</span></div>
        <input type="range" min="${l.min}" max="${l.max}" step="${l.step}" value="${l.value}">
        <div class="num"><input type="number" min="${l.min}" max="${l.max}" step="${l.step}" value="${l.value}"><span class="unit">${l.unit}</span></div>`;
      const range = row.querySelector('input[type=range]');
      const num = row.querySelector('input[type=number]');
      const saved = row.querySelector('.saved');
      range.addEventListener("input", () => { num.value = range.value; saveLimit(l.name, range.value, saved); });
      num.addEventListener("input", () => { range.value = num.value; saveLimit(l.name, num.value, saved); });
      g.appendChild(row);
    });
    container.appendChild(g);
  }
}

// ---------- wire-up ----------
RANGE_EL.addEventListener("change", refreshCharts);
let resizeTimer;
window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => {
    for (const k of Object.keys(charts)) {
      const c = charts[k];
      if (c) makeChart(k, c.elId, c.resp, c.stepped);
    }
  }, 200);
});

refreshStatus();
refreshCharts();
renderLimits();
setInterval(refreshStatus, 10000);
setInterval(refreshCharts, 60000);
