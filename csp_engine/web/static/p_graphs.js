"use strict";
(() => {
const { h, api, busy, census, stats, metricPairs, showError, bubble, algoSelect, labeled, banner, COLORS } = Kit;

function tabs(root, names) {
  const bar = h("div", { class: "tabs2" }), panes = {};
  names.forEach((n, i) => {
    const b = h("button", { class: i ? "" : "on" }, n), p = h("div", { style: { display: i ? "none" : "" } });
    b.addEventListener("click", () => { bar.querySelectorAll("button").forEach((x) => x.classList.remove("on")); b.classList.add("on");
      Object.values(panes).forEach((x) => (x.style.display = "none")); p.style.display = ""; });
    bar.appendChild(b); panes[n] = p;
  });
  root.append(bar, ...Object.values(panes));
  return panes;
}

/* ======================================================= Map colouring === */
Kit.register("map", (root) => {
  const regions = h("select", {}, ...[8, 14, 20, 30, 45].map((k) => h("option", { value: k }, `${k} regions`)));
  regions.value = 14;
  const ncol = h("select", {}, ...[4, 3, 2].map((k) => h("option", { value: k }, `${k} colours`)));
  const random = h("button", { class: "btn" }, "New random map");
  const aus = h("button", { class: "btn ghost" }, "Australia");
  const err = h("div");
  root.append(h("div", { class: "toolbar" }, random, regions, aus, ncol), err);
  const panes = tabs(root, ["Colour it yourself", "Watch two solvers race"]);
  const stage = h("div", { class: "stage" }), coach = h("div"), st = h("div");
  const algo = algoSelect("smart");
  const hintBtn = h("button", { class: "btn green" }, "Hint");
  const solveBtn = h("button", { class: "btn ghost" }, "Solve with");
  const fewest = h("button", { class: "btn ghost" }, "Find the fewest colours");
  panes["Colour it yourself"].append(h("p", { class: "info" }, "Click a region to cycle its colour. Neighbouring regions must differ."),
    stage, h("div", { class: "toolbar", style: { marginTop: "10px" } }, hintBtn, solveBtn, algo, fewest), coach, st);
  const raceBox = h("div");
  panes["Watch two solvers race"].append(raceBox);
  let inst = null, colour = {}, full = [];

  function instNow() { return { adjacency: inst.adjacency, colours: full.slice(0, +ncol.value), grid: inst.grid, layout: inst.layout }; }

  function drawMap(el, assign, opts = {}) {
    el.innerHTML = "";
    if (inst.grid) {
      const rows = inst.grid.length, cols = inst.grid[0].length, cs = Kit.fitSize(el, cols, rows, 34, 10);
      const c = Kit.canvas(cols * cs, rows * cs), ctx = c.ctx;
      for (let r = 0; r < rows; r++) for (let q = 0; q < cols; q++) {
        const reg = inst.grid[r][q];
        ctx.fillStyle = assign[reg] || "#d9dee9";
        if (opts.current === reg) ctx.fillStyle = "#f5b400";
        ctx.fillRect(q * cs, r * cs, cs, cs);
      }
      ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 2;
      for (let r = 0; r < rows; r++) for (let q = 0; q < cols; q++) {
        if (q + 1 < cols && inst.grid[r][q] !== inst.grid[r][q + 1]) { ctx.beginPath(); ctx.moveTo((q + 1) * cs, r * cs); ctx.lineTo((q + 1) * cs, (r + 1) * cs); ctx.stroke(); }
        if (r + 1 < rows && inst.grid[r][q] !== inst.grid[r + 1][q]) { ctx.beginPath(); ctx.moveTo(q * cs, (r + 1) * cs); ctx.lineTo((q + 1) * cs, (r + 1) * cs); ctx.stroke(); }
      }
      if (opts.marks) for (const reg of opts.marks) {
        const cells = []; inst.grid.forEach((row, r) => row.forEach((x, q) => x === reg && cells.push([r, q])));
        const [r, q] = cells[Math.floor(cells.length / 2)];
        ctx.fillStyle = "#fff"; ctx.beginPath(); ctx.arc(q * cs + cs / 2, r * cs + cs / 2, Math.max(3, cs * 0.22), 0, 7); ctx.fill();
      }
      if (opts.click) c.cv.addEventListener("click", (e) => { const rc = c.cv.getBoundingClientRect(); opts.click(inst.grid[Math.floor((e.clientY - rc.top) / cs)][Math.floor((e.clientX - rc.left) / cs)]); });
      el.appendChild(c.cv);
    } else {
      const c = Kit.canvas(460, 400), ctx = c.ctx, L = inst.layout, P = (k) => [L[k][0] * 4.4, L[k][1] * 3.8];
      ctx.strokeStyle = "#a3a9bb"; ctx.lineWidth = 2;
      for (const [a, ns] of Object.entries(inst.adjacency)) for (const b of ns) { const [x1, y1] = P(a), [x2, y2] = P(b); ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke(); }
      for (const k of Object.keys(L)) {
        const [x, y] = P(k);
        ctx.fillStyle = opts.current === k ? "#f5b400" : assign[k] || "#d9dee9";
        ctx.beginPath(); ctx.arc(x, y, 26, 0, 7); ctx.fill();
        ctx.strokeStyle = (opts.marks || []).includes(k) ? "#fff" : "#ffffff"; ctx.lineWidth = 3; ctx.stroke();
        ctx.fillStyle = "#0b1020"; ctx.font = "bold 13px sans-serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText(k, x, y);
      }
      if (opts.click) c.cv.addEventListener("click", (e) => { const rc = c.cv.getBoundingClientRect();
        for (const k of Object.keys(L)) { const [x, y] = P(k); if ((x - (e.clientX - rc.left)) ** 2 + (y - (e.clientY - rc.top)) ** 2 < 900) opts.click(k); } });
      el.appendChild(c.cv);
    }
  }

  function redraw(marks) {
    drawMap(stage, colour, { marks, click: (reg) => {
      const pal = full.slice(0, +ncol.value), i = pal.indexOf(colour[reg]);
      colour[reg] = i + 1 < pal.length ? pal[i + 1] : undefined;
      if (!colour[reg]) delete colour[reg];
      check();
    } });
  }

  async function check() {
    const r = await api("check", { inst: instNow(), entries: Object.entries(colour) });
    const bad = new Set(r.conflicts.flatMap((c) => c.vars));
    redraw([...bad]);
    coach.innerHTML = "";
    if (bad.size) coach.appendChild(bubble({ kind: "conflict", text: `Clash: ${r.conflicts[0].label}.` }));
    else if (r.solved) coach.appendChild(bubble({ kind: "ok", text: "Perfect colouring — no two neighbours match." }));
  }

  function setupRace() {
    Kit.race(raceBox, { body: () => ({ inst: instNow() }), defaults: ["naive", "smart"],
      makeView: (el) => ({ draw: (s) => drawMap(el, Object.fromEntries(s.assign), { current: s.current }) }) });
  }

  async function load(body) {
    showError(err, "");
    const r = await api("new", body);
    inst = r.inst; full = inst.colours; colour = {}; coach.innerHTML = ""; st.innerHTML = "";
    redraw(); setupRace();
  }
  random.addEventListener("click", busy(random, () => load({ regions: +regions.value })));
  aus.addEventListener("click", busy(aus, () => load({ mode: "australia" })));
  ncol.addEventListener("change", () => { colour = {}; redraw(); setupRace(); });
  hintBtn.addEventListener("click", busy(hintBtn, async () => {
    const hint = await api("hint", { inst: instNow(), entries: Object.entries(colour) });
    coach.innerHTML = "";
    coach.appendChild(bubble({ ...hint, text: hint.text.replace(/#[0-9a-f]{6}/gi, (c) => `colour ${full.indexOf(c) + 1}`) }));
    if (hint.var) coach.appendChild(h("button", { class: "btn ghost", onclick: () => { colour[hint.var] = hint.value; check(); } }, "Fill it in"));
    redraw([...(hint.highlight || []), ...(hint.var ? [hint.var] : [])]);
  }));
  solveBtn.addEventListener("click", busy(solveBtn, async () => {
    const r = await api("solve", { inst: instNow(), algorithm: algo.value });
    coach.innerHTML = "";
    if (!r.solution) { coach.appendChild(bubble({ kind: "mistake", text: `No colouring with ${ncol.value} colours exists.` })); census(r.census); return; }
    colour = r.solution; redraw();
    stats(st, metricPairs(r.metrics)); census(r.census);
  }));
  fewest.addEventListener("click", busy(fewest, async () => {
    const r = await api("chromatic", { inst: instNow() });
    coach.innerHTML = "";
    coach.appendChild(bubble({ kind: "ok", text: `This map needs ${r.k} colours: ${r.attempts.map((a) => `${a.slots} colour${a.slots > 1 ? "s" : ""} — ${a.found ? "works ✓" : "impossible"}`).join(" · ")}.` }));
    ncol.value = Math.max(2, Math.min(4, r.k)); colour = {};
    for (const [k, v] of Object.entries(r.solution)) colour[k] = full[v - 1];
    redraw();
  }));
  load({ regions: 14 });
});

/* ================================================================= TSP === */
Kit.register("tsp", (root) => {
  const n = h("select", {}, ...[5, 7, 9, 10, 11].map((k) => h("option", { value: k }, `${k} cities`)));
  n.value = 9;
  const fresh = h("button", { class: "btn" }, "New cities");
  const undo = h("button", { class: "btn ghost" }, "Undo");
  const solve = h("button", { class: "btn ghost" }, "Show the engine's optimal tour");
  const stage = h("div", { class: "stage" }), st = h("div"), rep = h("div"), info = h("div");
  root.append(h("div", { class: "toolbar" }, n, fresh, undo, solve),
    h("p", { class: "info" }, "Your turn: starting from the gold city, click the cities in the order you'd visit them. The tour returns home automatically. Try to make it as short as possible!"),
    stage, info, st, rep);
  let cities = [], mine = [0], best = null;
  const S = 5.2, cv = Kit.canvas(100 * S, 100 * S);
  stage.appendChild(cv.cv);
  const dist = (a, b) => Math.hypot(cities[a][0] - cities[b][0], cities[a][1] - cities[b][1]);
  const length = (t, closed) => t.reduce((s, c, i) => s + (i ? dist(t[i - 1], c) : 0), 0) + (closed && t.length > 1 ? dist(t[t.length - 1], t[0]) : 0);
  function draw() {
    const { ctx } = cv;
    ctx.clearRect(0, 0, cv.w, cv.h);
    const path = (t, col, dash, w, closed) => { if (!t || t.length < 2) return; ctx.setLineDash(dash); ctx.strokeStyle = col; ctx.lineWidth = w; ctx.lineCap = "round"; ctx.beginPath();
      t.forEach((c, i) => (i ? ctx.lineTo : ctx.moveTo).call(ctx, cities[c][0] * S, cities[c][1] * S)); if (closed) ctx.closePath(); ctx.stroke(); ctx.setLineDash([]); };
    if (best) path(best.tour, "rgba(18,165,138,.55)", [7, 6], 4, true);
    path(mine, "#5b6cff", [], 3.5, mine.length === cities.length);
    cities.forEach(([x, y], i) => {
      const visited = mine.includes(i);
      ctx.fillStyle = i === 0 ? "#f3c13a" : visited ? "#5b6cff" : "#ffffff";
      ctx.strokeStyle = "#5b6cff"; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(x * S, y * S, 11, 0, 7); ctx.fill(); ctx.stroke();
      ctx.fillStyle = visited && i ? "#fff" : "#2a2d3a"; ctx.font = "700 11px Nunito, sans-serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText(i + 1, x * S, y * S);
    });
  }
  function report() {
    const done = mine.length === cities.length;
    info.innerHTML = `<p class="info">Your tour so far: <strong>${length(mine, done).toFixed(1)}</strong>${done ? " (complete)" : ` · ${cities.length - mine.length} cities left`}</p>`;
  }
  cv.cv.addEventListener("click", async (e) => {
    const rc = cv.cv.getBoundingClientRect(), x = (e.clientX - rc.left) / S, y = (e.clientY - rc.top) / S;
    const i = cities.findIndex(([px, py]) => (px - x) ** 2 + (py - y) ** 2 < 16);
    if (i < 0 || mine.includes(i)) return;
    mine.push(i); draw(); report();
    if (mine.length === cities.length) {
      const r = await getBest();
      const you = length(mine, true), gap = ((you / r.length - 1) * 100).toFixed(1);
      banner(info, you <= r.length + 1e-6 ? `Optimal! Your tour (${you.toFixed(1)}) matches the shortest one the engine can prove.`
        : `Your tour: ${you.toFixed(1)}. The optimum is ${r.length.toFixed(1)} — yours is ${gap}% longer. Reveal the engine's tour to compare.`, you > r.length + 1e-6);
    }
  });
  async function getBest() { if (!best) best = await api("solve", { cities }); return best; }
  async function load() { cities = (await api("new", { n: +n.value })).cities; mine = [0]; best = null; st.innerHTML = ""; rep.innerHTML = ""; info.innerHTML = ""; draw(); }
  undo.addEventListener("click", () => { if (mine.length > 1) mine.pop(); info.innerHTML = ""; draw(); });
  fresh.addEventListener("click", busy(fresh, load));
  n.addEventListener("change", load);
  solve.addEventListener("click", busy(solve, async () => {
    const r = await getBest();
    draw();
    const gain = ((1 - r.length / r.nearest_neighbour.length) * 100).toFixed(1);
    stats(st, [["optimal length", r.length.toFixed(1)], ["greedy nearest-city", r.nearest_neighbour.length.toFixed(1)], ["optimal is better by", `${gain}%`], ...metricPairs(r.metrics)]);
    rep.innerHTML = `<p class="info">Dashed green = the engine's proven-optimal tour. Branch and bound kept tightening "better than the best so far": ${r.improvements.map((x) => `<span class="tag">${x.cost.toFixed(1)} after ${x.nodes} nodes</span>`).join(" → ")}.</p>`;
    census(r.census);
  }, "Optimising…"));
  load();
});

/* ======================================================= Shortest path === */
Kit.register("shortest", (root) => {
  const n = h("select", {}, ...[12, 24, 36, 50].map((k) => h("option", { value: k }, `${k} junctions`)));
  n.value = 24;
  const fresh = h("button", { class: "btn" }, "New road network");
  const undo = h("button", { class: "btn ghost" }, "Undo");
  const solve = h("button", { class: "btn ghost" }, "Show the engine's cheapest route");
  const stage = h("div", { class: "stage" }), st = h("div"), rep = h("div"), info = h("div");
  root.append(h("div", { class: "toolbar" }, n, fresh, undo, solve),
    h("p", { class: "info" }, "Your turn: drive from the green junction to the gold one by clicking neighbouring junctions (outlined) along the roads. The numbers are road costs."),
    stage, info, st, rep);
  let G = null, mine = [], best = null;
  const S = 5.2, cv = Kit.canvas(100 * S, 100 * S);
  stage.appendChild(cv.cv);
  const w = (a, b) => { const e = G.edges.find(([x, y]) => (x === a && y === b) || (x === b && y === a)); return e ? e[2] : null; };
  const cost = (p) => p.slice(1).reduce((s, v, i) => s + w(p[i], v), 0);
  function draw() {
    const { ctx } = cv, P = G.points;
    ctx.clearRect(0, 0, cv.w, cv.h);
    const key = (p) => new Set(p.slice(1).map((v, i) => [p[i], v].sort((a, b) => a - b).join("-")));
    const mineK = key(mine), bestK = best ? key(best.path) : new Set();
    const here = mine[mine.length - 1];
    for (const [a, b, wt] of G.edges) {
      const k = [a, b].join("-");
      ctx.strokeStyle = mineK.has(k) ? "#5b6cff" : bestK.has(k) ? "rgba(18,165,138,.6)" : (a === here || b === here) ? "#b9bfd6" : "#e0dcd3";
      ctx.lineWidth = mineK.has(k) ? 5 : bestK.has(k) ? 7 : 2;
      ctx.beginPath(); ctx.moveTo(P[a][0] * S, P[a][1] * S); ctx.lineTo(P[b][0] * S, P[b][1] * S); ctx.stroke();
      ctx.fillStyle = "#8a90a3"; ctx.font = "600 9px Nunito, sans-serif"; ctx.fillText(wt, (P[a][0] + P[b][0]) / 2 * S, (P[a][1] + P[b][1]) / 2 * S);
    }
    P.forEach(([x, y], i) => {
      const reach = here !== G.target && w(here, i) !== null && !mine.includes(i);
      ctx.fillStyle = i === G.source ? "#12a58a" : i === G.target ? "#f3c13a" : mine.includes(i) ? "#5b6cff" : reach ? "#ffffff" : "#c9cde0";
      ctx.strokeStyle = reach ? "#5b6cff" : "rgba(0,0,0,0)"; ctx.lineWidth = 2.5;
      ctx.beginPath(); ctx.arc(x * S, y * S, i === G.source || i === G.target ? 10 : reach ? 8 : 6, 0, 7); ctx.fill(); ctx.stroke();
    });
  }
  cv.cv.addEventListener("click", async (e) => {
    const rc = cv.cv.getBoundingClientRect(), x = (e.clientX - rc.left) / S, y = (e.clientY - rc.top) / S;
    const i = G.points.findIndex(([px, py]) => (px - x) ** 2 + (py - y) ** 2 < 12);
    const here = mine[mine.length - 1];
    if (i < 0 || mine.includes(i) || here === G.target || w(here, i) === null) return;
    mine.push(i); draw();
    info.innerHTML = `<p class="info">Your route so far costs <strong>${cost(mine).toFixed(1)}</strong></p>`;
    if (i === G.target) {
      const r = await getBest(), you = cost(mine);
      banner(info, Math.abs(you - r.cost) < 1e-6 ? `Cheapest possible! ${you.toFixed(1)} — the engine proves nothing beats it.`
        : `You arrived for ${you.toFixed(1)}. The cheapest route costs ${r.cost.toFixed(1)} — reveal it to compare.`, you > r.cost + 1e-6);
    }
  });
  async function getBest() { if (!best) best = await api("solve", { points: G.points, edges: G.edges, source: G.source, target: G.target }); return best; }
  async function load() { G = await api("new", { n: +n.value }); mine = [G.source]; best = null; st.innerHTML = ""; rep.innerHTML = ""; info.innerHTML = ""; draw(); }
  undo.addEventListener("click", () => { if (mine.length > 1) mine.pop(); info.innerHTML = ""; draw(); });
  fresh.addEventListener("click", busy(fresh, load));
  n.addEventListener("change", load);
  solve.addEventListener("click", busy(solve, async () => {
    const r = await getBest();
    draw();
    const same = Math.abs(r.cost - r.dijkstra.cost) < 1e-6;
    stats(st, [["cheapest cost", r.cost.toFixed(1)], ["junctions", r.path.length], ["Dijkstra agrees", same ? "yes ✓" : "NO"], ...metricPairs(r.metrics)]);
    rep.innerHTML = `<p class="info">Wide green = the engine's route. Planning CSP with costs: one "legal route within the cost bound" predicate; the bound rose ${r.iterations.length} time${r.iterations.length > 1 ? "s" : ""} until a route fit — so the first route found is the cheapest.</p>`;
    census(r.census);
  }));
  load();
});

/* ===================================================== Exam scheduling === */
Kit.register("exam", (root) => {
  const students = h("input", { type: "number", value: 14, min: 2, max: 40, style: { width: "64px" } });
  const exams = h("input", { type: "number", value: 8, min: 2, max: 16, style: { width: "64px" } });
  const per = h("input", { type: "number", value: 3, min: 1, max: 6, style: { width: "64px" } });
  const fresh = h("button", { class: "btn" }, "New enrolment data");
  const err = h("div"), info = h("div");
  root.append(h("div", { class: "toolbar" }, labeled("students", students), labeled("exams", exams), labeled("exams each", per), fresh), err, info);
  const panes = tabs(root, ["Build the timetable yourself", "Watch two solvers race"]);
  const table = h("div"), coach = h("div"), st = h("div");
  const hintBtn = h("button", { class: "btn green" }, "Hint");
  const solveBtn = h("button", { class: "btn ghost" }, "Solve");
  panes["Build the timetable yourself"].append(table, h("div", { class: "toolbar", style: { marginTop: "10px" } }, hintBtn, solveBtn), coach, st);
  const raceBox = h("div");
  panes["Watch two solvers race"].append(raceBox);
  let inst = null, adj = null, sel = {};

  function entries() { return Object.entries(sel).filter(([, s]) => s.value).map(([e, s]) => [e, +s.value]); }
  function render() {
    const ex = Object.keys(adj).sort();
    sel = {};
    const rows = ex.map((e) => {
      const s = h("select", {}, h("option", { value: "" }, "—"), ...Array.from({ length: inst.slots }, (_, i) => h("option", { value: i + 1 }, `slot ${i + 1}`)));
      s.addEventListener("change", check);
      sel[e] = s;
      return h("tr", {}, h("td", {}, e), h("td", {}, s), h("td", { class: "muted" }, adj[e].join(", ") || "—"));
    });
    table.innerHTML = "";
    table.appendChild(h("table", { class: "t" }, h("tr", {}, h("th", {}, "Exam"), h("th", {}, "Slot"), h("th", {}, "Clashes with (shared students)")), ...rows));
    Kit.race(raceBox, { body: () => ({ inst }), defaults: ["naive", "smart"], makeView: (el) => ({ draw(s) {
      const by = {};
      for (const [e, slot] of s.assign) (by[slot] = by[slot] || []).push(e);
      el.innerHTML = Array.from({ length: inst.slots }, (_, i) => `<div class="tag" style="display:block;margin:4px 0">slot ${i + 1}: ${(by[i + 1] || []).join(", ") || "—"}</div>`).join("");
    } }) });
  }
  async function check() {
    const r = await api("check", { inst, entries: entries() });
    const bad = new Set(r.conflicts.flatMap((c) => c.vars));
    for (const [e, s] of Object.entries(sel)) s.style.outline = bad.has(e) ? "2px solid var(--danger)" : "";
    coach.innerHTML = "";
    if (bad.size) coach.appendChild(bubble({ kind: "conflict", text: `Clash: ${r.conflicts[0].label}.` }));
    else if (r.solved) coach.appendChild(bubble({ kind: "ok", text: "A clash-free timetable in the minimum number of slots." }));
  }
  fresh.addEventListener("click", busy(fresh, async () => {
    showError(err, "");
    const r = await api("new", { students: +students.value, exams: +exams.value, per: +per.value });
    inst = r.inst; adj = r.adjacency; coach.innerHTML = ""; st.innerHTML = "";
    info.innerHTML = `<p class="info">Two exams clash if some student takes both — that is an edge in a graph, and time slots are colours. The engine tried ${r.attempts.map((a) => `<span class="tag">${a.slots} slot${a.slots > 1 ? "s" : ""}: ${a.found ? "works" : "impossible"}</span>`).join(" ")} → <strong>${r.min_slots} slots</strong> is the minimum.</p>`;
    census(r.census);
    render();
  }));
  hintBtn.addEventListener("click", busy(hintBtn, async () => {
    const hint = await api("hint", { inst, entries: entries() });
    coach.innerHTML = ""; coach.appendChild(bubble(hint));
    if (hint.var) coach.appendChild(h("button", { class: "btn ghost", onclick: () => { sel[hint.var].value = hint.value; check(); } }, "Fill it in"));
  }));
  solveBtn.addEventListener("click", busy(solveBtn, async () => {
    const r = await api("solve", { inst, algorithm: "smart" });
    for (const [e, s] of Object.entries(r.solution || {})) sel[e].value = s;
    stats(st, metricPairs(r.metrics)); check();
  }));
  fresh.click();
});

/* ============================================================ Knapsack === */
Kit.register("knapsack", (root) => {
  const n = h("select", {}, ...[8, 12, 16, 22, 30].map((k) => h("option", { value: k }, `${k} items`)));
  n.value = 12;
  const fresh = h("button", { class: "btn ghost" }, "New items");
  const solve = h("button", { class: "btn" }, "Pack optimally");
  const table = h("div"), bar = h("div", { class: "info" }), st = h("div"), rep = h("div");
  root.append(h("div", { class: "toolbar" }, n, fresh, solve), h("p", { class: "info" }, "Tick items to pack your own bag, then see if you beat the engine."), bar, table, st, rep);
  let K = null, mine = new Set(), best = new Set();
  function render() {
    const rows = K.items.map((it, i) => {
      const cb = h("input", { type: "checkbox" });
      cb.checked = mine.has(i);
      cb.addEventListener("change", () => { cb.checked ? mine.add(i) : mine.delete(i); summary(); });
      return h("tr", { class: best.has(i) ? "hl" : "" }, h("td", {}, cb), h("td", {}, it.name), h("td", { class: "n" }, it.weight), h("td", { class: "n" }, it.value), h("td", { class: "n" }, (it.value / it.weight).toFixed(2)));
    });
    table.innerHTML = "";
    table.appendChild(h("table", { class: "t" }, h("tr", {}, h("th", {}, "pack"), h("th", {}, "item"), h("th", {}, "weight"), h("th", {}, "value"), h("th", {}, "value / kg")), ...rows));
    summary();
  }
  function summary() {
    const w = [...mine].reduce((a, i) => a + K.items[i].weight, 0), v = [...mine].reduce((a, i) => a + K.items[i].value, 0);
    bar.innerHTML = `Capacity <strong>${K.capacity}</strong> · your bag: weight <strong style="color:${w > K.capacity ? "var(--danger)" : "inherit"}">${w}</strong>, value <strong>${v}</strong>`;
  }
  async function load() { K = await api("new", { n: +n.value }); mine = new Set(); best = new Set(); st.innerHTML = ""; rep.innerHTML = ""; render(); }
  fresh.addEventListener("click", busy(fresh, load));
  n.addEventListener("change", load);
  solve.addEventListener("click", busy(solve, async () => {
    const r = await api("solve", { items: K.items, capacity: K.capacity });
    best = new Set(r.chosen); render();
    stats(st, [["optimal value", r.value], ["weight used", `${r.weight} / ${K.capacity}`], ["greedy by value/kg", r.greedy.value], ...metricPairs(r.metrics)]);
    rep.innerHTML = `<p class="info">Highlighted rows are the optimal bag. Improvements found during branch and bound: ${r.improvements.map((x) => `<span class="tag">${x.value} @ ${x.nodes} nodes</span>`).join(" → ")}. The bound predicate used the "fill the rest greedily, even fractionally" relaxation, so whole subtrees that couldn't beat the best were never explored.</p>`;
    census(r.census);
  }));
  load();
});
})();
