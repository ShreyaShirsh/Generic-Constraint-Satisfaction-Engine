"use strict";

// ---------------------------------------------------------------- tabs ----
document.querySelectorAll("nav.tabs button").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("nav.tabs button").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById("tab-" + btn.dataset.tab).classList.add("active");
    if (btn.dataset.tab === "benchmark" && !window.__bmLoaded) loadBenchmark();
  });
});

// -------------------------------------------------------------- helpers ----
async function postJSON(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "request failed");
  return data;
}

function showError(elId, message) {
  const el = document.getElementById(elId);
  el.innerHTML = message ? `<div class="error-box">${escapeHtml(message)}</div>` : "";
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function renderMetrics(elId, m) {
  const el = document.getElementById(elId);
  if (!m) { el.innerHTML = ""; return; }
  let badge = m.solved
    ? '<span class="badge ok">solved</span>'
    : (m.timed_out ? '<span class="badge warn">timed out</span>' : '<span class="badge bad">no solution</span>');
  el.innerHTML = `
    <div class="metric"><div class="label">status</div><div class="value">${badge}</div></div>
    <div class="metric"><div class="label">algorithm</div><div class="value" style="font-size:0.78rem">${escapeHtml(m.algorithm)}</div></div>
    <div class="metric"><div class="label">nodes</div><div class="value">${m.nodes}</div></div>
    <div class="metric"><div class="label">backtracks</div><div class="value">${m.backtracks}</div></div>
    <div class="metric"><div class="label">pruned</div><div class="value">${m.pruned}</div></div>
    <div class="metric"><div class="label">time</div><div class="value">${m.elapsed_ms} ms</div></div>
  `;
}

function withBusy(button, fn) {
  return async (...args) => {
    button.disabled = true;
    const original = button.textContent;
    button.textContent = "Solving…";
    try { await fn(...args); } finally { button.disabled = false; button.textContent = original; }
  };
}

// circle-layout graph renderer, reused by Map Colouring and Exam Scheduling
function renderGraph(container, adjacency, labelOf, colourOf) {
  const nodes = Object.keys(adjacency);
  const n = nodes.length;
  const w = container.clientWidth || 600, h = 360;
  const cx = w / 2, cy = h / 2, r = Math.min(w, h) / 2 - 50;
  const pos = {};
  nodes.forEach((node, i) => {
    const angle = (2 * Math.PI * i) / n - Math.PI / 2;
    pos[node] = [cx + r * Math.cos(angle), cy + r * Math.sin(angle)];
  });

  const seen = new Set();
  let edgesSvg = "";
  for (const u of nodes) {
    for (const v of adjacency[u] || []) {
      const key = [u, v].sort().join("|");
      if (seen.has(key)) continue;
      seen.add(key);
      const [x1, y1] = pos[u], [x2, y2] = pos[v];
      edgesSvg += `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="#3a4054" stroke-width="1.5"/>`;
    }
  }

  let nodesSvg = "";
  for (const node of nodes) {
    const [x, y] = pos[node];
    const fill = colourOf(node) || "#2a2f3d";
    nodesSvg += `
      <circle cx="${x}" cy="${y}" r="22" fill="${fill}" stroke="#e8eaf0" stroke-width="1.5"/>
      <text x="${x}" y="${y + 4}" text-anchor="middle">${escapeHtml(labelOf(node))}</text>`;
  }

  container.innerHTML = `<svg class="graph-svg" viewBox="0 0 ${w} ${h}">${edgesSvg}${nodesSvg}</svg>`;
}

// =============================================================== N-Queens ==
const nqBtn = document.getElementById("nq-solve");
nqBtn.addEventListener("click", withBusy(nqBtn, async () => {
  showError("nq-error", "");
  const n = parseInt(document.getElementById("nq-n").value, 10);
  const algorithm = document.getElementById("nq-algo").value;
  try {
    const data = await postJSON("/api/solve/nqueens", { n, algorithm });
    renderMetrics("nq-metrics", data.metrics);
    const viz = document.getElementById("nq-viz");
    if (!data.queens) { viz.innerHTML = "<p>No solution.</p>"; return; }
    const cell = Math.max(14, Math.min(38, Math.floor(560 / n)));
    let html = `<div class="board" style="grid-template-columns:repeat(${n},${cell}px)">`;
    for (let row = 0; row < n; row++) {
      for (let col = 0; col < n; col++) {
        const dark = (row + col) % 2 === 1;
        const isQueen = data.queens[col] === row;
        html += `<div class="cell ${dark ? "dark" : "light"} ${isQueen ? "queen" : ""}"
                      style="width:${cell}px;height:${cell}px;font-size:${cell * 0.55}px">${isQueen ? "♛" : ""}</div>`;
      }
    }
    html += "</div>";
    viz.innerHTML = html;
  } catch (e) { showError("nq-error", e.message); }
}));

// =========================================================== Map Colouring ==
let colMode = "australia";
document.querySelectorAll("#col-presets button").forEach((b) => {
  b.addEventListener("click", () => {
    document.querySelectorAll("#col-presets button").forEach((x) => x.classList.remove("active"));
    b.classList.add("active");
    colMode = b.dataset.preset;
  });
});

function parseEdges(text) {
  const adjacency = {};
  text.split("\n").map((l) => l.trim()).filter(Boolean).forEach((line) => {
    if (line.includes("-")) {
      const [u, v] = line.split("-").map((s) => s.trim());
      (adjacency[u] = adjacency[u] || []).push(v);
      (adjacency[v] = adjacency[v] || []).push(u);
    } else {
      adjacency[line] = adjacency[line] || [];           // isolated node (e.g. Tasmania)
    }
  });
  return adjacency;
}

const colBtn = document.getElementById("col-solve");
colBtn.addEventListener("click", withBusy(colBtn, async () => {
  showError("col-error", "");
  const colours = document.getElementById("col-colours").value.split(",").map((s) => s.trim()).filter(Boolean);
  const body = { colours, algorithm: document.getElementById("col-algo").value };
  if (colMode === "custom") body.adjacency = parseEdges(document.getElementById("col-edges").value);
  try {
    const data = await postJSON("/api/solve/graph-colouring", body);
    renderMetrics("col-metrics", data.metrics);
    const viz = document.getElementById("col-viz");
    viz.innerHTML = "";
    if (!data.assignment) { viz.innerHTML = "<p>No valid colouring with these colours.</p>"; return; }
    renderGraph(viz, data.adjacency, (n) => n, (n) => data.assignment[n]);
  } catch (e) { showError("col-error", e.message); }
}));

// =================================================================== Sudoku ==
const EASY_9x9 = [
  [5,3,0,0,7,0,0,0,0],[6,0,0,1,9,5,0,0,0],[0,9,8,0,0,0,0,6,0],
  [8,0,0,0,6,0,0,0,3],[4,0,0,8,0,3,0,0,1],[7,0,0,0,2,0,0,0,6],
  [0,6,0,0,0,0,2,8,0],[0,0,0,4,1,9,0,0,5],[0,0,0,0,8,0,0,7,9],
];
let suGrid = EASY_9x9.map((row) => row.slice());
let suSolvedGrid = null;

function renderSudoku() {
  const viz = document.getElementById("su-viz");
  let html = '<div class="sudoku-grid">';
  for (let r = 0; r < 9; r++) {
    for (let c = 0; c < 9; c++) {
      const given = EASY_9x9[r][c] !== 0 && suGrid[r][c] === EASY_9x9[r][c];
      const val = suGrid[r][c] || "";
      const solvedOnly = suSolvedGrid && !given && val;
      const classes = ["cell"];
      if (given) classes.push("given");
      if (solvedOnly) classes.push("solved");
      if (c % 3 === 2 && c !== 8) classes.push("b-right");
      if (r % 3 === 2 && r !== 8) classes.push("b-bottom");
      html += `<div class="${classes.join(" ")}" contenteditable="true"
                    data-r="${r}" data-c="${c}">${val}</div>`;
    }
  }
  html += "</div>";
  viz.innerHTML = html;
  viz.querySelectorAll(".cell").forEach((cellEl) => {
    cellEl.addEventListener("input", () => {
      const r = +cellEl.dataset.r, c = +cellEl.dataset.c;
      const digit = cellEl.textContent.trim().replace(/[^1-9]/g, "").slice(0, 1);
      cellEl.textContent = digit;
      suGrid[r][c] = digit ? parseInt(digit, 10) : 0;
      suSolvedGrid = null;
    });
  });
}
renderSudoku();

document.getElementById("su-reset").addEventListener("click", () => {
  suGrid = Array.from({ length: 9 }, () => Array(9).fill(0));
  suSolvedGrid = null;
  renderSudoku();
});

const suBtn = document.getElementById("su-solve");
suBtn.addEventListener("click", withBusy(suBtn, async () => {
  showError("su-error", "");
  try {
    const data = await postJSON("/api/solve/sudoku", {
      grid: suGrid, algorithm: document.getElementById("su-algo").value,
    });
    renderMetrics("su-metrics", data.metrics);
    if (data.grid) { suSolvedGrid = data.grid; suGrid = data.grid.map((r) => r.slice()); renderSudoku(); }
    else showError("su-error", "No solution for this grid.");
  } catch (e) { showError("su-error", e.message); }
}));

// ========================================================= Cryptarithmetic ==
const crBtn = document.getElementById("cr-solve");
crBtn.addEventListener("click", withBusy(crBtn, async () => {
  showError("cr-error", "");
  try {
    const data = await postJSON("/api/solve/cryptarithmetic", {
      addend1: document.getElementById("cr-a1").value,
      addend2: document.getElementById("cr-a2").value,
      result: document.getElementById("cr-r").value,
      algorithm: document.getElementById("cr-algo").value,
    });
    renderMetrics("cr-metrics", data.metrics);
    const viz = document.getElementById("cr-viz");
    if (!data.equation) { viz.innerHTML = "<p>No solution exists.</p>"; return; }
    const chips = Object.entries(data.letters).map(([L, d]) => `<div class="chip">${L} = ${d}</div>`).join("");
    viz.innerHTML = `
      <div class="equation">${data.addend1} + ${data.addend2} = ${data.result}</div>
      <div class="equation">${data.equation}</div>
      <div class="letters">${chips}</div>`;
  } catch (e) { showError("cr-error", e.message); }
}));

// ==================================================================== Zebra ==
const zbBtn = document.getElementById("zb-solve");
zbBtn.addEventListener("click", withBusy(zbBtn, async () => {
  showError("zb-error", "");
  try {
    const data = await postJSON("/api/solve/zebra", { algorithm: document.getElementById("zb-algo").value });
    renderMetrics("zb-metrics", data.metrics);
    const viz = document.getElementById("zb-viz");
    if (!data.houses) { viz.innerHTML = "<p>No solution.</p>"; return; }
    let rows = data.houses.map((h, i) =>
      `<tr><td class="num">${i + 1}</td><td>${h.nation}</td><td>${h.colour}</td><td>${h.drink}</td><td>${h.smoke}</td><td>${h.pet}</td></tr>`
    ).join("");
    const zebraOwner = data.houses.find((h) => h.pet === "Zebra");
    viz.innerHTML = `
      <p>The <strong>${escapeHtml(zebraOwner.nation)}</strong> owns the zebra.</p>
      <table class="pretty">
        <tr><th>House</th><th>Nationality</th><th>Colour</th><th>Drink</th><th>Smoke</th><th>Pet</th></tr>
        ${rows}
      </table>`;
  } catch (e) { showError("zb-error", e.message); }
}));

// ========================================================= Exam Scheduling ==
function parseEnrollments(text) {
  const enrollments = {};
  text.split("\n").map((l) => l.trim()).filter(Boolean).forEach((line) => {
    const [name, rest] = line.split(":");
    if (!name || !rest) return;
    enrollments[name.trim()] = rest.split(",").map((s) => s.trim()).filter(Boolean);
  });
  return enrollments;
}

const exBtn = document.getElementById("ex-solve");
exBtn.addEventListener("click", withBusy(exBtn, async () => {
  showError("ex-error", "");
  try {
    const data = await postJSON("/api/solve/exam-scheduling", {
      enrollments: parseEnrollments(document.getElementById("ex-enroll").value),
      num_slots: parseInt(document.getElementById("ex-slots").value, 10),
      algorithm: document.getElementById("ex-algo").value,
    });
    renderMetrics("ex-metrics", data.metrics);
    const viz = document.getElementById("ex-viz");
    if (!data.assignment) { viz.innerHTML = "<p>No feasible timetable with this many slots.</p>"; return; }
    const palette = ["#6ea8fe", "#7ee2b8", "#f5a35c", "#f27272", "#c792ea", "#ffd479", "#89ddff"];
    const slotColour = {};
    viz.innerHTML = "";
    const graphDiv = document.createElement("div");
    renderGraph(graphDiv, data.adjacency, (n) => n, (n) => {
      const slot = data.assignment[n];
      if (!(slot in slotColour)) slotColour[slot] = palette[Object.keys(slotColour).length % palette.length];
      return slotColour[slot];
    });
    const bySlot = {};
    Object.entries(data.assignment).forEach(([exam, slot]) => (bySlot[slot] = bySlot[slot] || []).push(exam));
    const list = Object.keys(bySlot).sort((a, b) => a - b)
      .map((s) => `<li><strong>Slot ${s}:</strong> ${bySlot[s].sort().join(", ")}</li>`).join("");
    viz.appendChild(graphDiv);
    const ul = document.createElement("ul");
    ul.innerHTML = list;
    viz.appendChild(ul);
  } catch (e) { showError("ex-error", e.message); }
}));

// ============================================================ Custom CSP ==
const cuBtn = document.getElementById("cu-solve");
cuBtn.addEventListener("click", withBusy(cuBtn, async () => {
  showError("cu-error", "");
  let spec;
  try { spec = JSON.parse(document.getElementById("cu-spec").value); }
  catch (e) { showError("cu-error", "Invalid JSON: " + e.message); return; }
  spec.algorithm = document.getElementById("cu-algo").value;
  try {
    const data = await postJSON("/api/solve/custom", spec);
    renderMetrics("cu-metrics", data.metrics);
    const viz = document.getElementById("cu-viz");
    if (!data.assignment) { viz.innerHTML = "<p>No solution satisfies every constraint.</p>"; return; }
    const rows = Object.entries(data.assignment).map(([k, v]) => `<tr><td>${escapeHtml(k)}</td><td class="num">${v}</td></tr>`).join("");
    viz.innerHTML = `<table class="pretty"><tr><th>Variable</th><th>Value</th></tr>${rows}</table>`;
  } catch (e) { showError("cu-error", e.message); }
}));

// ============================================================= Benchmark ==
let bmChart = null, bmData = [];

async function loadBenchmark() {
  window.__bmLoaded = true;
  const res = await fetch("/api/benchmark");
  bmData = await res.json();
  document.getElementById("bm-loading").style.display = "none";
  document.getElementById("bm-content").style.display = "block";

  const problems = [...new Set(bmData.map((r) => r.problem))];
  const select = document.getElementById("bm-problem");
  select.innerHTML = problems.map((p) => `<option>${escapeHtml(p)}</option>`).join("");
  select.addEventListener("change", () => renderBenchmark(select.value));
  renderBenchmark(problems[0]);
}

function renderBenchmark(problem) {
  const rows = bmData.filter((r) => r.problem === problem);
  const ctx = document.getElementById("bm-chart").getContext("2d");
  if (bmChart) bmChart.destroy();
  bmChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: rows.map((r) => r.technique),
      datasets: [
        { label: "nodes", data: rows.map((r) => r.nodes), backgroundColor: "#6ea8fe" },
        { label: "backtracks", data: rows.map((r) => r.backtracks), backgroundColor: "#f27272" },
      ],
    },
    options: {
      responsive: true,
      scales: { y: { type: "logarithmic", title: { display: true, text: "count (log scale)" } } },
      plugins: { legend: { labels: { color: "#e8eaf0" } } },
    },
  });

  const tableRows = rows.map((r) => `
    <tr>
      <td>${escapeHtml(r.technique)}</td>
      <td class="num">${r.nodes}${r.timed_out ? " (cap)" : ""}</td>
      <td class="num">${r.backtracks}</td>
      <td class="num">${r.pruned}</td>
      <td class="num">${r.elapsed_ms} ms</td>
    </tr>`).join("");
  document.getElementById("bm-table").innerHTML = `
    <table class="pretty" style="margin-top:14px">
      <tr><th>Technique</th><th>Nodes</th><th>Backtracks</th><th>Pruned</th><th>Time</th></tr>
      ${tableRows}
    </table>`;
}
