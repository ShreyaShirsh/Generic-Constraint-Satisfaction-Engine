"use strict";
(() => {
const { h, api, busy, census, stats, metricPairs, showError, bubble, labeled, banner, COLORS } = Kit;

const ARROWS = { ArrowUp: "U", ArrowDown: "D", ArrowLeft: "L", ArrowRight: "R", w: "U", s: "D", a: "L", d: "R" };
const DIR = { U: [-1, 0], D: [1, 0], L: [0, -1], R: [0, 1] };

function keyPad(onMove) {
  return h("div", { class: "toolbar", style: { marginTop: "8px" } },
    ...[["U", "↑"], ["L", "←"], ["D", "↓"], ["R", "→"]].map(([d, t]) => h("button", { class: "btn ghost", onclick: () => onMove(d) }, t)));
}

function gridCanvas(stage, grid, max = 46) {
  const rows = grid.length, cols = grid[0].length, cs = Kit.fitSize(stage, cols, rows, max, 14);
  const c = Kit.canvas(cols * cs, rows * cs);
  stage.innerHTML = ""; stage.appendChild(c.cv);
  const ctx = c.ctx;
  return {
    c, cs, ctx,
    base() {
      ctx.clearRect(0, 0, c.w, c.h);
      grid.forEach((row, r) => row.forEach((w, q) => { ctx.fillStyle = w ? "#b39b7d" : "#f2efe7"; ctx.beginPath(); ctx.roundRect(q * cs + 1, r * cs + 1, cs - 2, cs - 2, 4); ctx.fill(); }));
    },
    fill(r, q, col, inset = 1) { ctx.fillStyle = col; ctx.fillRect(q * cs + inset, r * cs + inset, cs - 2 * inset, cs - 2 * inset); },
    dot(r, q, col, rad = 0.32) { ctx.fillStyle = col; ctx.beginPath(); ctx.arc(q * cs + cs / 2, r * cs + cs / 2, cs * rad, 0, 7); ctx.fill(); },
    text(r, q, t, col = "#0b1020", s = 0.45) { ctx.fillStyle = col; ctx.font = `700 ${cs * s}px Nunito, sans-serif`; ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText(t, q * cs + cs / 2, r * cs + cs / 2 + 1); },
    path(cells, col, w = 3) { if (cells.length < 2) return; ctx.strokeStyle = col; ctx.lineWidth = w; ctx.lineCap = "round"; ctx.lineJoin = "round"; ctx.beginPath(); cells.forEach(([r, q], i) => (i ? ctx.lineTo : ctx.moveTo).call(ctx, q * cs + cs / 2, r * cs + cs / 2)); ctx.stroke(); },
  };
}

function freeAt(grid, r, c) { return r >= 0 && c >= 0 && r < grid.length && c < grid[0].length && !grid[r][c]; }

/* =================================================== Robot treasure hunt === */
Kit.register("treasure", (root) => {
  const t = h("select", {}, ...[3, 4, 5, 6, 7].map((k) => h("option", { value: k }, `${k} treasures`)));
  t.value = 4;
  const fresh = h("button", { class: "btn" }, "New world");
  root.append(h("div", { class: "toolbar" }, t, fresh));
  const { panes } = Kit.modes(root, ["You play", "Engine solves"]);
  const stage1 = h("div", { class: "stage", tabindex: 0 }), info = h("div");
  panes["You play"].append(h("p", { class: "info" }, "Click the map, then drive the robot with the arrow keys. Collect every gold treasure, then reach the EXIT in as few steps as you can."),
    stage1, keyPad((d) => step(d)), info);
  const solve = h("button", { class: "btn" }, "Plan the shortest hunt");
  const stage2 = h("div", { class: "stage" }), play = h("div"), st = h("div"), rep = h("div");
  panes["Engine solves"].append(h("div", { class: "toolbar" }, solve), stage2, play, st, rep);
  let W = null, G1, G2, me, trail, got, done, best = null;

  function draw(G, path, upto, pos, collected) {
    G.base();
    G.path(path.slice(0, upto + 1), "rgba(91,108,255,.45)", 4);
    W.treasures.forEach(([r, q], i) => { if (!collected.has(`${r},${q}`)) { G.dot(r, q, "#f3c13a", 0.3); G.text(r, q, i + 1, "#6b4e00", 0.34); } });
    G.fill(W.exit[0], W.exit[1], "rgba(18,165,138,.25)", 3);
    G.text(W.exit[0], W.exit[1], "EXIT", "#0c8a66", 0.22);
    G.dot(pos[0], pos[1], "#5b6cff", 0.36);
  }
  const got1 = (path, upto) => new Set(path.slice(0, upto + 1).map(([r, q]) => `${r},${q}`));
  function step(d) {
    if (!W || done) return;
    const [dr, dc] = DIR[d], n = [me[0] + dr, me[1] + dc];
    if (!freeAt(W.grid, ...n)) return;
    me = n; trail.push(n);
    const k = `${n[0]},${n[1]}`;
    if (W.treasures.some(([r, q]) => `${r},${q}` === k)) got.add(k);
    draw(G1, trail, trail.length, me, got);
    info.innerHTML = `<p class="info">Steps: <strong>${trail.length - 1}</strong> · treasures: ${got.size}/${W.treasures.length}</p>`;
    if (got.size === W.treasures.length && n[0] === W.exit[0] && n[1] === W.exit[1]) {
      done = true;
      getBest().then((r) => banner(info, trail.length - 1 <= r.length ? `Perfect hunt — ${trail.length - 1} steps, the proven optimum!` : `Done in ${trail.length - 1} steps. The engine's shortest hunt takes ${r.length}.`, trail.length - 1 > r.length));
    }
  }
  stage1.addEventListener("keydown", (e) => { const d = ARROWS[e.key]; if (d) { e.preventDefault(); step(d); } });
  async function getBest() { if (!best) best = await api("solve", W); return best; }
  async function load() {
    W = await api("new", { treasures: +t.value }); best = null;
    G1 = gridCanvas(stage1, W.grid); G2 = gridCanvas(stage2, W.grid);
    me = W.start; trail = [W.start]; got = new Set(); done = false;
    info.innerHTML = ""; play.innerHTML = ""; st.innerHTML = ""; rep.innerHTML = "";
    draw(G1, [], -1, me, got); draw(G2, [], -1, W.start, new Set());
    stage1.focus();
  }
  fresh.addEventListener("click", busy(fresh, load));
  solve.addEventListener("click", busy(solve, async () => {
    const r = await getBest();
    const p = Kit.player(r.path.length, (i) => draw(G2, r.path, i, r.path[i], got1(r.path, i)), { fps: 10 });
    play.innerHTML = ""; play.appendChild(p.el); p.play();
    stats(st, [["route length", r.length], ["order", r.order.slice(1, -1).map((k) => `T${k}`).join(" → ")], ["order-CSP nodes", r.metrics.nodes], ["leg-planning nodes", r.leg_nodes]]);
    rep.innerHTML = `<p class="info">Two layers, one engine: every leg between two points is a planning CSP (step variables + one "legal path" predicate); then the visiting ORDER is a CSP with all-different slots and the branch-and-bound predicate.</p>`;
    census(r.census);
  }, "Planning…"));
  load();
});

/* =========================================== Gridworld + Q-learning contrast === */
function gridworldPage(root, learnFirst) {
  const fresh = h("button", { class: "btn" }, "New world");
  root.append(h("div", { class: "toolbar" }, fresh),
    h("p", { class: "info" }, "Reach a gem (gold +10, blue +4). Every step costs 1; falling into a red pit costs 10 and ends the run."));
  const names = learnFirst ? ["Learn vs reason", "You play"] : ["You play", "Engine vs learner"];
  const { panes } = Kit.modes(root, names);
  const playPane = panes["You play"], cmpPane = panes[names.find((n) => n !== "You play")];
  const stage1 = h("div", { class: "stage", tabindex: 0 }), info = h("div");
  playPane.append(stage1, keyPad((d) => step(d)), info);
  const plan = h("button", { class: "btn" }, "Plan with the CSP engine");
  const learn = h("button", { class: "btn ghost" }, "Learn with Q-learning");
  const episodes = h("select", {}, ...[50, 200, 500, 2000].map((k) => h("option", { value: k }, `${k} episodes`)));
  episodes.value = 500;
  const slip = h("select", {}, h("option", { value: 0 }, "deterministic moves"), h("option", { value: 0.2 }, "20% slippery"));
  const stage = h("div", { class: "stage" }), play = h("div"), st1 = h("div"), st2 = h("div"), chart = h("div"), note = h("div");
  cmpPane.append(h("div", { class: "toolbar" }, plan, learn, episodes, slip), stage, play,
    h("div", { class: "row2" }, h("div", {}, h("h3", {}, "CSP planner"), st1), h("div", {}, h("h3", {}, "Q-learning (contrast)"), st2)), chart, note);
  let W = null, G, G1, policy = null, me, score, over, best = null;
  const ARROW = { U: "↑", D: "↓", L: "←", R: "→" };
  const gemAt = (r, q) => W.gems.find((g) => g.cell[0] === r && g.cell[1] === q);
  const pitAt = (r, q) => W.pits.some(([a, b]) => a === r && b === q);
  function draw(GG, path = [], upto = -1, pos = null, arrows = null) {
    GG.base();
    W.pits.forEach(([r, q]) => { GG.fill(r, q, "rgba(229,72,77,.3)", 3); GG.dot(r, q, "rgba(229,72,77,.65)", 0.18); });
    W.gems.forEach((g, i) => GG.dot(g.cell[0], g.cell[1], i ? "#4c6ef5" : "#f3c13a", 0.3));
    if (arrows) for (const [k, a] of Object.entries(arrows)) { const [r, q] = k.split(",").map(Number); GG.text(r, q, ARROW[a], "rgba(42,45,58,.4)", 0.5); }
    GG.path(path.slice(0, upto + 1), "rgba(91,108,255,.55)", 4);
    const p = pos || (upto >= 0 ? path[Math.min(upto, path.length - 1)] : W.start);
    GG.dot(p[0], p[1], "#12a58a", 0.34);
  }
  function step(d) {
    if (!W || over) return;
    const [dr, dc] = DIR[d], n = [me[0] + dr, me[1] + dc];
    if (!freeAt(W.grid, ...n)) return;
    me = n; score -= W.step_cost;
    draw(G1, [], -1, me);
    const g = gemAt(...n);
    if (g || pitAt(...n)) {
      over = true;
      score += g ? g.reward : -10;
      getBest().then((r) => {
        const opt = r.best ? r.best.score : null;
        if (!g) banner(info, `Splash! You fell into a pit. Score ${score}. The CSP plan scores ${opt}.`, true);
        else banner(info, score >= opt ? `Best possible! Score ${score} — the same as the CSP planner's optimal plan.` : `You scored ${score}. The CSP planner's best plan scores ${opt}.`, score < opt);
      });
    } else info.innerHTML = `<p class="info">Score so far: <strong>${score}</strong></p>`;
  }
  stage1.addEventListener("keydown", (e) => { const d = ARROWS[e.key]; if (d) { e.preventDefault(); step(d); } });
  async function getBest() { if (!best) best = await api("plan", W, "gridworld"); return best; }
  async function load() {
    W = await api("new", {}, "gridworld"); policy = null; best = null;
    G = gridCanvas(stage, W.grid, 52); G1 = gridCanvas(stage1, W.grid, 52);
    me = W.start; score = 0; over = false;
    play.innerHTML = ""; st1.innerHTML = st2.innerHTML = chart.innerHTML = note.innerHTML = info.innerHTML = "";
    draw(G); draw(G1, [], -1, me);
    stage1.focus();
  }
  fresh.addEventListener("click", busy(fresh, load));
  plan.addEventListener("click", busy(plan, async () => {
    const r = await getBest();
    if (!r.best) { st1.innerHTML = ""; st1.appendChild(Kit.errorBox("No gem is reachable.")); return; }
    const p = Kit.player(r.best.path.length, (i) => draw(G, r.best.path, i, null, policy), { fps: 6 });
    play.innerHTML = ""; play.appendChild(p.el); p.play();
    stats(st1, [["reward", r.best.score], ["steps", r.best.path.length - 1], ["search nodes", r.best.nodes], ["trial runs", 0]]);
    census(r.census);
  }, "Planning…"));
  learn.addEventListener("click", busy(learn, async () => {
    const r = await api("learn", { inst: W, episodes: +episodes.value, slip: +slip.value }, "gridworld");
    policy = r.policy;
    const p = Kit.player(r.greedy_path.length, (i) => draw(G, r.greedy_path, i, null, policy), { fps: 6 });
    play.innerHTML = ""; play.appendChild(p.el); p.play();
    stats(st2, [["reward of learned route", r.greedy_reward ?? "never reaches a gem"], ["episodes", r.episodes], ["first success", r.first_success ? `episode ${r.first_success}` : "never"], ["steps of experience", r.experience_steps.toLocaleString()]]);
    const R = r.returns, w = 520, hh = 120, c = Kit.canvas(w, hh), ctx = c.ctx;
    const lo = Math.min(...R), hi = Math.max(...R);
    ctx.strokeStyle = "#f08c2b"; ctx.lineWidth = 1.5; ctx.beginPath();
    R.forEach((v, i) => (i ? ctx.lineTo : ctx.moveTo).call(ctx, (i / Math.max(1, R.length - 1)) * w, hh - 6 - ((v - lo) / Math.max(1e-9, hi - lo)) * (hh - 12)));
    ctx.stroke();
    chart.innerHTML = `<p class="info">Q-learning's reward per episode (it starts clueless and improves by trial and error):</p>`;
    chart.appendChild(c.cv);
    note.innerHTML = `<div class="bubble">The CSP engine reasons from the rules and finds the best route in one search, with zero trial runs. Q-learning needs thousands of steps of experience to discover a route. This is the only learning code in the project, kept outside the engine as a contrast.</div>`;
  }, "Learning…"));
  load().then(() => { if (learnFirst) { plan.click(); learn.click(); } });
}
Kit.register("gridworld", (root) => gridworldPage(root, false));
Kit.register("qlearning", (root) => gridworldPage(root, true));

/* ===================================================== Resource planning === */
Kit.register("resource", (root) => {
  const n = h("select", {}, ...[5, 6, 8, 10, 12].map((k) => h("option", { value: k }, `${k} tasks`)));
  n.value = 6;
  const fresh = h("button", { class: "btn" }, "New project");
  const solve = h("button", { class: "btn ghost" }, "Let the engine schedule it");
  const tasks = h("div"), gantt = h("div", { class: "stage" }), info = h("div"), st = h("div"), rep = h("div");
  root.append(h("div", { class: "toolbar" }, n, fresh, solve),
    h("p", { class: "info" }, "Your turn: pick a start day for every task. A task can only start after the tasks it depends on have finished, and the crew (max 4) and the crane (max 1) can't be over-used on any day. Finish as early as you can."),
    tasks, gantt, info, st, rep);
  let P = null, starts = [], best = null;

  function problems(s) {
    const out = [];
    P.precedence.forEach(([a, b]) => { if (s[a] + P.tasks[a].duration > s[b]) out.push(`${P.tasks[b].name} starts before ${P.tasks[a].name} is finished`); });
    const span = Math.max(...s.map((x, i) => x + P.tasks[i].duration));
    for (const [res, cap] of Object.entries(P.capacity)) for (let d = 0; d < span; d++) {
      const load = P.tasks.reduce((a, t, i) => a + (s[i] <= d && d < s[i] + t.duration ? (t[res] || 0) : 0), 0);
      if (load > cap) { out.push(`day ${d}: ${load} ${res} needed but only ${cap} available`); break; }
    }
    return out;
  }
  function table() {
    const pre = (j) => P.precedence.filter(([a, b]) => b === j).map(([a]) => P.tasks[a].name).join(", ") || "—";
    tasks.innerHTML = "";
    tasks.appendChild(h("table", { class: "t" }, h("tr", {}, ...["task", "days", "crew", "crane", "after", "start day"].map((x) => h("th", {}, x))),
      ...P.tasks.map((t, i) => {
        const inp = h("input", { type: "number", min: 0, max: 60, value: starts[i], style: { width: "64px" } });
        inp.addEventListener("input", () => { starts[i] = Math.max(0, +inp.value || 0); update(); });
        return h("tr", {}, h("td", {}, t.name), h("td", { class: "n" }, t.duration), h("td", { class: "n" }, t.crew), h("td", { class: "n" }, t.crane), h("td", { class: "muted" }, pre(i)), h("td", {}, inp));
      })));
  }
  function drawGantt(s, el, bad) {
    const span = Math.max(...s.map((x, i) => x + P.tasks[i].duration), 1);
    const W = 640, row = 26, H = P.tasks.length * row + 74, c = Kit.canvas(W, H), ctx = c.ctx, sx = (W - 120) / Math.max(span, 10);
    for (let d = 0; d <= Math.max(span, 10); d++) { ctx.fillStyle = d % 2 ? "rgba(0,0,0,.025)" : "rgba(0,0,0,0)"; ctx.fillRect(120 + d * sx, 0, sx, P.tasks.length * row); }
    P.tasks.forEach((t, i) => {
      ctx.fillStyle = "#6f7486"; ctx.font = "600 12px Nunito, sans-serif"; ctx.textBaseline = "middle"; ctx.fillText(t.name, 6, i * row + row / 2);
      ctx.fillStyle = COLORS[i % 12]; ctx.beginPath(); ctx.roundRect(120 + s[i] * sx, i * row + 4, t.duration * sx - 2, row - 8, 8); ctx.fill();
    });
    const y0 = P.tasks.length * row + 12;
    for (let d = 0; d < span; d++) {
      let crew = 0;
      P.tasks.forEach((t, i) => { if (s[i] <= d && d < s[i] + t.duration) crew += t.crew; });
      ctx.fillStyle = crew > P.capacity.crew ? "#e5484d" : "#9db4ff";
      ctx.beginPath(); ctx.roundRect(120 + d * sx, y0 + 52 - crew * 10, sx - 2, crew * 10, 3); ctx.fill();
    }
    ctx.fillStyle = "#6f7486"; ctx.fillText(`crew in use (max ${P.capacity.crew})`, 6, y0 + 36);
    el.innerHTML = ""; el.appendChild(c.cv);
    return span;
  }
  async function update() {
    const bad = problems(starts), span = drawGantt(starts, gantt);
    if (bad.length) { info.innerHTML = ""; info.appendChild(bubble({ kind: "conflict", text: `Not allowed yet: ${bad.slice(0, 3).join("; ")}.` })); return; }
    const r = await getBest();
    if (span <= r.makespan) banner(info, `Valid and optimal — your project finishes on day ${span}, the earliest the engine can prove!`);
    else banner(info, `Valid schedule finishing on day ${span}. The engine's best finishes on day ${r.makespan} — can you shave off ${span - r.makespan}?`, true);
  }
  async function getBest() { if (!best) best = await api("solve", P); return best; }
  async function load() {
    P = await api("new", { tasks: +n.value }); best = null;
    let t = 0; starts = P.tasks.map((x) => { const s = t; t += x.duration; return s; });   // one after another: valid but slow
    st.innerHTML = ""; rep.innerHTML = "";
    table(); update();
  }
  fresh.addEventListener("click", busy(fresh, load));
  n.addEventListener("change", load);
  solve.addEventListener("click", busy(solve, async () => {
    const r = await getBest();
    if (!r.starts) { rep.innerHTML = ""; rep.appendChild(Kit.errorBox("No schedule found within the search budget.")); return; }
    starts = r.starts.slice(); table(); update();
    stats(st, [["finishes on day", r.makespan], ["longest chain of tasks", r.critical_path], ["proven optimal", r.optimal ? "yes" : "best found"], ...metricPairs(r.metrics)]);
    rep.innerHTML = `<p class="info">Start-time variables; "A finishes before B starts" binary relations; one predicate per resource; plus the bound predicate. Makespan improved: ${r.improvements.map((x) => `<span class="tag">${x.cost} days</span>`).join(" → ")}.</p>`;
    census(r.census);
  }, "Scheduling…"));
  load();
});

/* =============================================== Multi-agent coordination === */
Kit.register("mapf", (root) => {
  const agents = h("select", {}, ...[2, 3, 4, 5, 6].map((k) => h("option", { value: k }, `${k} robots`)));
  agents.value = 3;
  const fresh = h("button", { class: "btn" }, "New warehouse");
  root.append(h("div", { class: "toolbar" }, agents, fresh),
    h("p", { class: "info" }, "Each robot (circle) must reach its own goal (square of the same colour). Robots move at the same time; they may never share a cell or swap places."));
  const { panes } = Kit.modes(root, ["You play", "Engine solves"]);
  const stage1 = h("div", { class: "stage" }), orders = h("div"), info = h("div");
  const goBtn = h("button", { class: "btn" }, "Go! (advance one tick)");
  const undoBtn = h("button", { class: "btn ghost" }, "Undo tick");
  panes["You play"].append(stage1, h("p", { class: "info" }, "Give every robot an order for this tick, then press Go."), orders, h("div", { class: "toolbar" }, goBtn, undoBtn), info);
  const solve = h("button", { class: "btn" }, "Coordinate them");
  const stage2 = h("div", { class: "stage" }), play = h("div"), st = h("div"), rep = h("div");
  panes["Engine solves"].append(h("div", { class: "toolbar" }, solve), stage2, play, st, rep);
  let W = null, G1, G2, hist, pending, done, best = null;
  const N = "ABCDEFGH";

  function draw(G, pos, trails) {
    G.base();
    W.goals.forEach(([r, q], a) => { G.fill(r, q, COLORS[a] + "44", G.cs * 0.1); G.text(r, q, N[a], COLORS[a], 0.34); });
    if (trails) trails.forEach((p, a) => G.path(p, COLORS[a] + "99", 3));
    pos.forEach(([r, q], a) => { G.dot(r, q, COLORS[a], 0.34); G.text(r, q, N[a], "#fff", 0.34); });
  }
  function renderOrders() {
    orders.innerHTML = "";
    const cur = hist[hist.length - 1];
    cur.forEach((p, a) => {
      const row = h("div", { class: "toolbar", style: { margin: "4px 0", alignItems: "center" } }, h("span", { class: "tag", style: { color: COLORS[a], borderColor: COLORS[a], minWidth: "60px" } }, `robot ${N[a]}`));
      [["W", "wait"], ["U", "↑"], ["D", "↓"], ["L", "←"], ["R", "→"]].forEach(([d, t]) => {
        const b = h("button", { class: "btn ghost", style: { padding: "5px 11px" } }, t);
        if (pending[a] === d) { b.style.background = COLORS[a]; b.style.color = "#fff"; }
        b.addEventListener("click", () => { pending[a] = d; renderOrders(); });
        row.appendChild(b);
      });
      orders.appendChild(row);
    });
  }
  function tick() {
    if (done) return;
    const cur = hist[hist.length - 1];
    const next = cur.map(([r, q], a) => { const d = pending[a]; if (d === "W") return [r, q]; const [dr, dc] = DIR[d]; return [r + dr, q + dc]; });
    for (let a = 0; a < next.length; a++) if (!freeAt(W.grid, ...next[a])) { banner(info, `Robot ${N[a]} would hit a wall.`, true); return; }
    for (let a = 0; a < next.length; a++) for (let b = a + 1; b < next.length; b++) {
      if (next[a][0] === next[b][0] && next[a][1] === next[b][1]) { banner(info, `Crash! Robots ${N[a]} and ${N[b]} would land on the same cell.`, true); return; }
      if (next[a][0] === cur[b][0] && next[a][1] === cur[b][1] && next[b][0] === cur[a][0] && next[b][1] === cur[a][1]) { banner(info, `Robots ${N[a]} and ${N[b]} can't swap places.`, true); return; }
    }
    hist.push(next); pending = next.map(() => "W");
    draw(G1, next, W.starts.map((_, a) => hist.map((p) => p[a])));
    renderOrders();
    info.innerHTML = `<p class="info">Tick <strong>${hist.length - 1}</strong></p>`;
    if (next.every(([r, q], a) => r === W.goals[a][0] && q === W.goals[a][1])) {
      done = true;
      getBest().then((r) => banner(info, hist.length - 1 <= r.makespan ? `Everyone home in ${hist.length - 1} ticks — the fastest possible!` : `Everyone home in ${hist.length - 1} ticks. The engine does it in ${r.makespan}.`, hist.length - 1 > r.makespan));
    }
  }
  goBtn.addEventListener("click", tick);
  undoBtn.addEventListener("click", () => { if (hist.length > 1 && !done) { hist.pop(); pending = hist[0].map(() => "W"); draw(G1, hist[hist.length - 1], W.starts.map((_, a) => hist.map((p) => p[a]))); renderOrders(); info.innerHTML = ""; } });
  async function getBest() { if (!best) best = await api("solve", W); return best; }
  async function load() {
    W = await api("new", { agents: +agents.value }); best = null;
    G1 = gridCanvas(stage1, W.grid, 56); G2 = gridCanvas(stage2, W.grid, 56);
    hist = [W.starts]; pending = W.starts.map(() => "W"); done = false;
    play.innerHTML = ""; st.innerHTML = ""; rep.innerHTML = ""; info.innerHTML = "";
    draw(G1, W.starts); draw(G2, W.starts); renderOrders();
  }
  fresh.addEventListener("click", busy(fresh, load));
  agents.addEventListener("change", load);
  solve.addEventListener("click", busy(solve, async () => {
    const r = await getBest();
    if (!r.paths) { rep.innerHTML = ""; rep.appendChild(Kit.errorBox(r.reason || "No plan found.")); return; }
    const p = Kit.player(r.makespan + 1, (t) => draw(G2, r.paths.map((p) => p[Math.min(t, p.length - 1)]), r.paths.map((p) => p.slice(0, t + 1))), { fps: 2 });
    play.innerHTML = ""; play.appendChild(p.el); p.play();
    stats(st, [["everyone arrives by tick", r.makespan], ["search nodes", r.nodes]]);
    rep.innerHTML = `<p class="info">Variables = position of robot a at tick t. The engine tried makespans ${r.attempts.map((a) => `<span class="tag">T=${a.T}: ${a.found ? "solved" : a.by === "propagation" ? "ruled out by propagation alone" : "no plan"}</span>`).join(" ")}.</p>`;
    census(r.census);
  }, "Coordinating…"));
  load();
});
})();
