"use strict";
(() => {
const { h, api, busy, census, stats, showError, labeled, banner } = Kit;

/* shared: what the planning CSP did */
function planReport(el, r) {
  el.innerHTML = "";
  if (!r.plan) {
    el.appendChild(Kit.errorBox(r.unsolvable ? "This position can't be solved (wrong parity)." : "No plan found within the limits."));
    return;
  }
  const m = r.metrics || {};
  el.appendChild(stats(h("div"), [["plan length", r.plan.length], ["search nodes", (m.nodes || 0).toLocaleString()],
    ["time", `${m.elapsed_ms} ms`], ["CSPs solved", r.iterations.length]]));
  if (r.iterations && r.iterations.length) {
    const rows = r.iterations.map((it) => `<tr class="${it.found ? "hl" : ""}"><td class="n">${it.steps}</td><td class="n">${it.nodes.toLocaleString()}</td><td>${it.found ? "plan found ✓" : "no plan this short"}</td></tr>`).join("");
    el.appendChild(h("div", { html: `<p class="info">Iterative deepening: one planning CSP per horizon T (T step variables, one “legal plan” predicate). The first T with a solution is optimal.</p>
      <table class="t"><tr><th>T</th><th>nodes</th><th></th></tr>${rows}</table>` }));
  }
  if (r.census) census(r.census);
}

/* "you finished in N — optimal is M" */
async function verdict(el, yours, optimalFn, what = "moves") {
  try {
    const best = await optimalFn();
    if (best === null || best === undefined) { banner(el, `Done in ${yours} ${what}!`); return; }
    banner(el, yours <= best ? `Perfect! ${yours} ${what} — exactly the optimum the engine proves.`
      : `Solved in ${yours} ${what}. The engine's optimum is ${best} — can you match it?`);
  } catch (e) { banner(el, `Done in ${yours} ${what}!`); }
}

const ARROWS = { ArrowUp: "U", ArrowDown: "D", ArrowLeft: "L", ArrowRight: "R", w: "U", s: "D", a: "L", d: "R" };
const DIR = { U: [-1, 0], D: [1, 0], L: [0, -1], R: [0, 1] };

function keyPad(onMove) {
  return h("div", { class: "toolbar", style: { marginTop: "8px" } },
    ...[["U", "↑"], ["L", "←"], ["D", "↓"], ["R", "→"]].map(([d, t]) => h("button", { class: "btn ghost", onclick: () => onMove(d) }, t)));
}

function gridDrawer(cv, cs) {
  const { ctx } = cv;
  return {
    cell(r, c, color, inset = 1) { ctx.fillStyle = color; ctx.fillRect(c * cs + inset, r * cs + inset, cs - 2 * inset, cs - 2 * inset); },
    dot(r, c, color, rad = 0.3) { ctx.fillStyle = color; ctx.beginPath(); ctx.arc(c * cs + cs / 2, r * cs + cs / 2, cs * rad, 0, 7); ctx.fill(); },
    clear() { ctx.clearRect(0, 0, cv.w, cv.h); },
  };
}

/* ================================================================ Maze === */
Kit.register("maze", (root) => {
  const size = h("select", {}, ...[[11, 15], [15, 21], [21, 31], [31, 41]].map(([r, c]) => h("option", { value: `${r}x${c}` }, `${r}×${c}`)));
  size.value = "15x21";
  const fresh = h("button", { class: "btn" }, "New maze");
  root.append(h("div", { class: "toolbar" }, size, fresh));
  const { panes } = Kit.modes(root, ["You play", "Engine solves"]);
  const stage = h("div", { class: "stage", tabindex: 0 }), info = h("div");
  const solve = h("button", { class: "btn" }, "Find the shortest escape");
  const stage2 = h("div", { class: "stage" }), rep = h("div"), play = h("div");
  panes["You play"].append(h("p", { class: "info" }, "Click the maze, then use the arrow keys (or the buttons) to walk from the blue dot to the gold exit."),
    stage, keyPad((d) => step(d)), info);
  panes["Engine solves"].append(h("div", { class: "toolbar" }, solve), stage2, play, rep);
  let M = null, me, trail, done;

  function canvasFor(el) {
    const cs = Kit.fitSize(el, M.grid[0].length, M.grid.length, 26, 8);
    const cv = Kit.canvas(M.grid[0].length * cs, M.grid.length * cs);
    el.innerHTML = ""; el.appendChild(cv.cv);
    return gridDrawer(cv, cs);
  }
  function draw(d, path = [], upto = 0, player = null) {
    d.clear();
    M.grid.forEach((row, r) => row.forEach((w, c) => d.cell(r, c, w ? "#8f96ab" : "#f2efe7", 0)));
    for (let i = 0; i <= Math.min(upto, path.length - 1); i++) d.cell(path[i][0], path[i][1], "rgba(91,108,255,.28)", 3);
    d.dot(M.goal[0], M.goal[1], "#f3c13a", 0.38);
    const p = player || (path.length ? path[Math.min(upto, path.length - 1)] : M.start);
    d.dot(p[0], p[1], "#5b6cff", 0.36);
  }
  let D1, D2;
  function step(dir) {
    if (!M || done) return;
    const [r, c] = me, [dr, dc] = DIR[dir], n = [r + dr, c + dc];
    if (!M.grid[n[0]] || M.grid[n[0]][n[1]] !== false) return;
    me = n; trail.push(n);
    draw(D1, trail, trail.length, me);
    info.innerHTML = `<p class="info">Steps: <strong>${trail.length - 1}</strong></p>`;
    if (n[0] === M.goal[0] && n[1] === M.goal[1]) {
      done = true;
      verdict(info, trail.length - 1, async () => (await api("solve", M)).plan.length, "steps");
    }
  }
  stage.addEventListener("keydown", (e) => { const d = ARROWS[e.key]; if (d) { e.preventDefault(); step(d); } });
  async function load() {
    const [rows, cols] = size.value.split("x").map(Number);
    M = await api("new", { rows, cols });
    me = M.start; trail = [M.start]; done = false; info.innerHTML = ""; rep.innerHTML = ""; play.innerHTML = "";
    D1 = canvasFor(stage); D2 = canvasFor(stage2);
    draw(D1, [], 0, me); draw(D2);
    stage.focus();
  }
  fresh.addEventListener("click", busy(fresh, load));
  size.addEventListener("change", load);
  solve.addEventListener("click", busy(solve, async () => {
    const r = await api("solve", M);
    planReport(rep, r);
    if (r.states) { const p = Kit.player(r.states.length, (i) => draw(D2, r.states, i), { fps: 20 }); play.innerHTML = ""; play.appendChild(p.el); p.play(); }
  }, "Searching…"));
  load();
});

/* ============================================================ 8-puzzle === */
Kit.register("eight", (root) => {
  const sizeSel = h("select", {}, h("option", { value: 3 }, "8-puzzle (3×3)"), h("option", { value: 4 }, "15-puzzle (4×4)"));
  const moves = h("input", { type: "number", value: 20, min: 1, max: 80, style: { width: "70px" } });
  const shuffle = h("button", { class: "btn" }, "Shuffle");
  const solve = h("button", { class: "btn ghost" }, "Let the engine solve it");
  const err = h("div"), stage = h("div", { class: "stage" }), rep = h("div"), play = h("div"), info = h("div");
  root.append(h("div", { class: "toolbar" }, sizeSel, labeled("random moves", moves), shuffle, solve), err,
    h("p", { class: "info" }, "Click a tile next to the gap to slide it. Put the tiles in order 1, 2, 3 … with the gap last."), stage, info, play, rep);
  let board = null, start = null, n = 3, cv, cs = 74, yourMoves = 0, won = false;

  function draw(b) {
    const { ctx } = cv;
    ctx.clearRect(0, 0, cv.w, cv.h);
    b.forEach((v, i) => {
      if (!v) return;
      const r = Math.floor(i / n), c = i % n, home = v - 1 === i;
      ctx.fillStyle = home ? "#bfe9da" : "#ffffff";
      ctx.shadowColor = "rgba(60,45,20,.15)"; ctx.shadowBlur = 6; ctx.shadowOffsetY = 2;
      ctx.beginPath(); ctx.roundRect(c * cs + 5, r * cs + 5, cs - 10, cs - 10, 14); ctx.fill();
      ctx.shadowColor = "transparent";
      ctx.fillStyle = "#2a2d3a"; ctx.font = `700 ${cs * 0.38}px Fredoka, sans-serif`; ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.fillText(v, c * cs + cs / 2, r * cs + cs / 2 + 2);
    });
  }
  function mount() {
    cv = Kit.canvas(n * cs, n * cs);
    stage.innerHTML = ""; stage.appendChild(cv.cv);
    cv.cv.addEventListener("click", (e) => {
      if (won) return;
      const rect = cv.cv.getBoundingClientRect();
      const c = Math.floor((e.clientX - rect.left) / cs), r = Math.floor((e.clientY - rect.top) / cs);
      const i = r * n + c, z = board.indexOf(0);
      if (Math.abs(Math.floor(z / n) - r) + Math.abs((z % n) - c) !== 1) return;
      [board[i], board[z]] = [board[z], board[i]];
      yourMoves++;
      draw(board);
      if (board.every((v, k) => v === (k + 1) % (n * n))) {
        won = true;
        verdict(info, yourMoves, async () => (await api("solve", { board: start, size: n })).plan.length);
      } else info.innerHTML = `<p class="info">Your moves: <strong>${yourMoves}</strong></p>`;
    });
    draw(board);
  }
  async function load() {
    showError(err, ""); rep.innerHTML = ""; play.innerHTML = ""; yourMoves = 0; info.innerHTML = ""; won = false;
    n = +sizeSel.value; cs = n === 3 ? 92 : 72;
    const r = await api("new", { size: n, moves: +moves.value });
    board = r.board; start = r.board.slice();
    mount();
  }
  shuffle.addEventListener("click", busy(shuffle, load));
  sizeSel.addEventListener("change", load);
  solve.addEventListener("click", busy(solve, async () => {
    showError(err, "");
    try {
      const r = await api("solve", { board, size: n });
      planReport(rep, r);
      if (r.states) {
        const p = Kit.player(r.states.length, (i) => { draw(r.states[i]); info.innerHTML = `<p class="info">Engine: move ${i} of ${r.plan.length}</p>`; }, { fps: 4 });
        play.innerHTML = ""; play.appendChild(p.el); p.play();
        board = r.states[r.states.length - 1].slice(); won = true;
      }
    } catch (e) { showError(err, e.message); }
  }, "Searching…"));
  load();
});

/* ======================================================= Tower of Hanoi === */
Kit.register("hanoi", (root) => {
  const disks = h("select", {}, ...[3, 4, 5, 6, 7, 8].map((k) => h("option", { value: k }, `${k} disks`)));
  disks.value = 4;
  const reset = h("button", { class: "btn" }, "Restart");
  root.append(h("div", { class: "toolbar" }, disks, reset));
  const { panes } = Kit.modes(root, ["You play", "Engine solves"]);
  const W = 560, H = 230;
  const cv1 = Kit.canvas(W, H), cv2 = Kit.canvas(W, H), info = h("div");
  panes["You play"].append(h("p", { class: "info" }, "Click a peg to pick up its top disk, then click another peg to drop it. Never put a bigger disk on a smaller one. Move the tower to peg C."),
    h("div", { class: "stage" }, cv1.cv), info);
  const heur = h("select", {}, h("option", { value: "exact" }, "exact distance (fast)"),
    h("option", { value: "simple" }, "disks out of place (weak)"), h("option", { value: "none" }, "no heuristic"));
  const solve = h("button", { class: "btn" }, "Solve");
  const err = h("div"), rep = h("div"), play = h("div");
  panes["Engine solves"].append(h("div", { class: "toolbar" }, labeled("lower bound used by the bound predicate", heur), solve),
    h("p", { class: "info" }, "Try the weak heuristic or none on 4–5 disks to see how much the bound matters."), err, h("div", { class: "stage" }, cv2.cv), play, rep);
  let state, held = null, moves = 0, won = false;

  function draw(cv, s, lift = null) {
    const { ctx } = cv, n = s.length;
    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = "#c9ab84"; ctx.beginPath(); ctx.roundRect(20, H - 22, W - 40, 10, 5); ctx.fill();
    for (let p = 0; p < 3; p++) { ctx.fillStyle = lift !== null && lift[1] === p ? "#5b6cff" : "#b8a487"; ctx.beginPath(); ctx.roundRect(100 + p * 180 - 4, 46, 8, H - 66, 4); ctx.fill(); }
    const heights = [0, 0, 0];
    for (let d = n - 1; d >= 0; d--) {
      const p = s[d], w = 34 + (d / Math.max(1, n - 1)) * 116;
      let y = H - 22 - (heights[p] + 1) * 19;
      if (lift && lift[0] === d) y = 14;
      ctx.fillStyle = Kit.COLORS[d % Kit.COLORS.length];
      ctx.beginPath(); ctx.roundRect(100 + p * 180 - w / 2, y, w, 17, 9); ctx.fill();
      heights[p]++;
    }
    ctx.fillStyle = "#7a7f90"; ctx.font = "700 14px Fredoka, sans-serif"; ctx.textAlign = "center";
    "ABC".split("").forEach((l, p) => ctx.fillText(l, 100 + p * 180, 40));
  }
  function restart() { state = Array(+disks.value).fill(0); held = null; moves = 0; won = false; info.innerHTML = ""; draw(cv1, state); draw(cv2, state); rep.innerHTML = ""; play.innerHTML = ""; }
  cv1.cv.addEventListener("click", (e) => {
    if (won) return;
    const p = Math.max(0, Math.min(2, Math.floor((e.clientX - cv1.cv.getBoundingClientRect().left) / (W / 3))));
    const top = (peg) => { const on = state.map((q, d) => (q === peg ? d : -1)).filter((d) => d >= 0); return on.length ? Math.min(...on) : null; };
    if (held === null) { const t = top(p); if (t !== null) { held = [t, p]; draw(cv1, state, held); } return; }
    const t = top(p);
    if (p !== held[1] && (t === null || t > held[0])) { state[held[0]] = p; moves++; }
    held = null; draw(cv1, state);
    info.innerHTML = `<p class="info">Moves: <strong>${moves}</strong> · the minimum for ${state.length} disks is ${2 ** state.length - 1}</p>`;
    if (state.every((q) => q === 2)) { won = true; verdict(info, moves, async () => 2 ** state.length - 1); }
  });
  disks.addEventListener("change", restart);
  reset.addEventListener("click", restart);
  solve.addEventListener("click", busy(solve, async () => {
    showError(err, "");
    try {
      const r = await api("solve", { disks: +disks.value, heuristic: heur.value });
      planReport(rep, r);
      if (r.states) { const p = Kit.player(r.states.length, (i) => draw(cv2, r.states[i]), { fps: 6 }); play.innerHTML = ""; play.appendChild(p.el); p.play(); }
    } catch (e) { showError(err, e.message); }
  }, "Searching…"));
  restart();
});

/* ======================================================= River crossing === */
Kit.register("river", (root) => {
  const variant = h("select", {}, h("option", { value: "fwgc" }, "Farmer, wolf, goat & cabbage"), h("option", { value: "mc" }, "Missionaries & cannibals"));
  const m = h("input", { type: "number", value: 3, min: 1, max: 8, style: { width: "60px" } });
  const c = h("input", { type: "number", value: 3, min: 1, max: 8, style: { width: "60px" } });
  const boat = h("input", { type: "number", value: 2, min: 2, max: 4, style: { width: "60px" } });
  const reset = h("button", { class: "btn" }, "Restart");
  const mcOpts = h("div", { class: "toolbar", style: { margin: 0 } }, labeled("missionaries", m), labeled("cannibals", c), labeled("boat seats", boat));
  root.append(h("div", { class: "toolbar" }, variant, mcOpts, reset));
  const { panes } = Kit.modes(root, ["You play", "Engine solves"]);
  const W = 620, H = 200;
  const cv1 = Kit.canvas(W, H), cv2 = Kit.canvas(W, H);
  const choices = h("div", { class: "toolbar" }), info = h("div");
  panes["You play"].append(h("div", { class: "stage" }, cv1.cv), h("p", { class: "info" }, "Who gets in the boat?"), choices, info);
  const solve = h("button", { class: "btn" }, "Solve");
  const err = h("div"), rep = h("div"), play = h("div"), stepTxt = h("p", { class: "info" });
  panes["Engine solves"].append(h("div", { class: "toolbar" }, solve), err, h("div", { class: "stage" }, cv2.cv), stepTxt, play, rep);
  let s, moves, over;

  const isF = () => variant.value === "fwgc";
  const start = () => (isF() ? [0, 0, 0, 0] : [+m.value, +c.value, 1]);
  function options() {
    if (isF()) return [["alone", "Farmer alone"], ["wolf", "with the wolf"], ["goat", "with the goat"], ["cabbage", "with the cabbage"]];
    const out = [], k = +boat.value;
    for (let i = 0; i <= k; i++) for (let j = 0; j <= k; j++) if (i + j >= 1 && i + j <= k) out.push([`${i}M${j}C`, `${i} missionar${i === 1 ? "y" : "ies"} + ${j} cannibal${j === 1 ? "" : "s"}`]);
    return out;
  }
  function apply(st, a) {           // returns [next, problem-or-null]
    if (isF()) {
      const items = { wolf: 1, goat: 2, cabbage: 3 }, f = st[0], nx = st.slice();
      nx[0] = 1 - f;
      if (a !== "alone") { if (st[items[a]] !== f) return [null, `The ${a} isn't on the farmer's bank.`]; nx[items[a]] = 1 - f; }
      const [F, W_, G_, C_] = nx;
      if (G_ === W_ && W_ !== F) return [nx, "The wolf ate the goat!"];
      if (G_ === C_ && C_ !== F) return [nx, "The goat ate the cabbage!"];
      return [nx, null];
    }
    const [dm, dc] = [+a[0], +a[2]], [ml, cl, b] = st, M = +m.value, C = +c.value, sg = b ? -1 : 1;
    const m2 = ml + sg * dm, c2 = cl + sg * dc;
    if (m2 < 0 || c2 < 0 || m2 > M || c2 > C) return [null, "There aren't that many people on the boat's bank."];
    const nx = [m2, c2, 1 - b];
    if ((m2 > 0 && c2 > m2) || (M - m2 > 0 && C - c2 > M - m2)) return [nx, "Missionaries were outnumbered on one bank!"];
    return [nx, null];
  }
  const goal = (st) => (isF() ? st.every((x) => x === 1) : st[0] === 0 && st[1] === 0);

  function draw(cv, st) {
    const { ctx } = cv;
    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = "#bfe0f5"; ctx.fillRect(220, 0, 180, H);
    ctx.fillStyle = "#cdebc5"; ctx.fillRect(0, 0, 220, H); ctx.fillRect(400, 0, 220, H);
    ctx.font = "700 13px Fredoka, sans-serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
    const put = (items, side) => items.forEach((t, i) => {
      const x = side === 0 ? 30 + (i % 4) * 52 : 430 + (i % 4) * 52, y = 40 + Math.floor(i / 4) * 44;
      ctx.fillStyle = t.color; ctx.beginPath(); ctx.roundRect(x - 23, y - 16, 46, 32, 10); ctx.fill();
      ctx.fillStyle = "#0b1020"; ctx.fillText(t.label, x, y);
    });
    let left = [], right = [], side;
    if (isF()) {
      [["Farmer", "#9db4ff"], ["Wolf", "#c3c7d3"], ["Goat", "#ffe08a"], ["Cabb.", "#a6e3c4"]].forEach(([nm, col], i) => (st[i] ? right : left).push({ label: nm, color: col }));
      side = st[0];
    } else {
      const [ml, cl, b] = st, M = +m.value, C = +c.value;
      for (let i = 0; i < ml; i++) left.push({ label: "M", color: "#9db4ff" });
      for (let i = 0; i < cl; i++) left.push({ label: "C", color: "#ffb3b8" });
      for (let i = 0; i < M - ml; i++) right.push({ label: "M", color: "#9db4ff" });
      for (let i = 0; i < C - cl; i++) right.push({ label: "C", color: "#ffb3b8" });
      side = b ? 0 : 1;
    }
    put(left, 0); put(right, 1);
    ctx.fillStyle = "#a47552"; ctx.beginPath(); ctx.roundRect(side ? 336 : 228, H - 44, 56, 20, 10); ctx.fill();
  }
  function restart() {
    s = start(); moves = 0; over = false; info.innerHTML = ""; rep.innerHTML = ""; play.innerHTML = ""; stepTxt.textContent = "";
    mcOpts.style.display = isF() ? "none" : "";
    choices.innerHTML = "";
    for (const [a, label] of options()) choices.appendChild(h("button", { class: "btn ghost", onclick: () => go(a) }, label));
    draw(cv1, s); draw(cv2, s);
  }
  function go(a) {
    if (over) return;
    const [nx, problem] = apply(s, a);
    if (!nx) { banner(info, problem, true); return; }
    s = nx; moves++; draw(cv1, s);
    if (problem) { over = true; banner(info, `${problem} Press Restart to try again.`, true); return; }
    info.innerHTML = `<p class="info">Crossings: <strong>${moves}</strong></p>`;
    if (goal(s)) { over = true; verdict(info, moves, async () => (await api("solve", { variant: variant.value, m: +m.value, c: +c.value, boat: +boat.value })).plan.length, "crossings"); }
  }
  [variant, m, c, boat].forEach((x) => x.addEventListener("change", restart));
  reset.addEventListener("click", restart);
  solve.addEventListener("click", busy(solve, async () => {
    showError(err, "");
    try {
      const r = await api("solve", { variant: variant.value, m: +m.value, c: +c.value, boat: +boat.value });
      planReport(rep, r);
      if (r.states) {
        const p = Kit.player(r.states.length, (i) => { draw(cv2, r.states[i]); stepTxt.textContent = i ? `Crossing ${i}: ${r.plan[i - 1].replace(/(\d)M(\d)C/, (_, a, b) => `${a} missionaries, ${b} cannibals`)}` : "Start"; }, { fps: 1 });
        play.innerHTML = ""; play.appendChild(p.el); p.play();
      }
    } catch (e) { showError(err, e.message); }
  }));
  restart();
});

/* ============================================================== Sokoban === */
Kit.register("sokoban", (root) => {
  const pick = h("select");
  const reset = h("button", { class: "btn" }, "Restart level");
  const solve = h("button", { class: "btn ghost" }, "Show the optimal solution");
  const err = h("div"), stage = h("div", { class: "stage", tabindex: 0 }), rep = h("div"), play = h("div"), info = h("div");
  root.append(h("div", { class: "toolbar" }, pick, reset, solve),
    h("p", { class: "info" }, "Click the board, then use the arrow keys (or buttons). Push every box onto a gold square."), err, stage,
    keyPad((d) => move(d)), info, play, rep);
  let levels = [], L = null, cv, cs = 50, moves = 0, won = false;

  function parse(map) {
    const rows = map.split("\n");
    const S = { walls: new Set(), goals: new Set(), boxes: new Set(), player: null, rows: rows.length, cols: Math.max(...rows.map((r) => r.length)) };
    rows.forEach((row, r) => [...row].forEach((ch, c) => {
      const k = `${r},${c}`;
      if (ch === "#") S.walls.add(k);
      if (".*+".includes(ch)) S.goals.add(k);
      if ("$*".includes(ch)) S.boxes.add(k);
      if ("@+".includes(ch)) S.player = [r, c];
    }));
    return S;
  }
  function draw(S) {
    const { ctx } = cv;
    ctx.clearRect(0, 0, cv.w, cv.h);
    for (let r = 0; r < S.rows; r++) for (let c = 0; c < S.cols; c++) {
      const k = `${r},${c}`, x = c * cs, y = r * cs;
      ctx.fillStyle = S.walls.has(k) ? "#b39b7d" : "#f2efe7";
      ctx.fillRect(x, y, cs, cs);
      if (S.goals.has(k)) { ctx.fillStyle = "#ffe08a"; ctx.beginPath(); ctx.arc(x + cs / 2, y + cs / 2, cs * 0.2, 0, 7); ctx.fill(); }
      if (S.boxes.has(k)) { ctx.fillStyle = S.goals.has(k) ? "#40c08a" : "#d29a5c"; ctx.beginPath(); ctx.roundRect(x + 6, y + 6, cs - 12, cs - 12, 8); ctx.fill(); }
    }
    ctx.fillStyle = "#5b6cff";
    ctx.beginPath(); ctx.arc(S.player[1] * cs + cs / 2, S.player[0] * cs + cs / 2, cs * 0.3, 0, 7); ctx.fill();
  }
  function stateOf(st) { const S = parse(L.map); S.player = st[0]; S.boxes = new Set(st[1].map(([r, c]) => `${r},${c}`)); return S; }
  function load() {
    L = levels[+pick.value];
    const S = parse(L.map);
    cv = Kit.canvas(S.cols * cs, S.rows * cs);
    stage.innerHTML = ""; stage.appendChild(cv.cv);
    L.S = S; moves = 0; won = false; info.innerHTML = ""; rep.innerHTML = ""; play.innerHTML = "";
    draw(S); stage.focus();
  }
  function move(dir) {
    if (!L || won) return;
    const d = DIR[dir], S = L.S, [r, c] = S.player, n = [r + d[0], c + d[1]], nk = `${n[0]},${n[1]}`;
    if (S.walls.has(nk)) return;
    if (S.boxes.has(nk)) {
      const b = `${n[0] + d[0]},${n[1] + d[1]}`;
      if (S.walls.has(b) || S.boxes.has(b)) return;
      S.boxes.delete(nk); S.boxes.add(b);
    }
    S.player = n; moves++;
    draw(S);
    info.innerHTML = `<p class="info">Moves: <strong>${moves}</strong></p>`;
    if ([...S.boxes].every((k) => S.goals.has(k))) { won = true; verdict(info, moves, async () => (await api("solve", { map: L.map })).plan.length); }
  }
  stage.addEventListener("keydown", (e) => { const d = ARROWS[e.key]; if (d) { e.preventDefault(); move(d); } });
  reset.addEventListener("click", load);
  pick.addEventListener("change", load);
  solve.addEventListener("click", busy(solve, async () => {
    showError(err, "");
    const r = await api("solve", { map: L.map });
    planReport(rep, r);
    if (r.states) { const p = Kit.player(r.states.length, (i) => draw(stateOf(r.states[i])), { fps: 5 }); play.innerHTML = ""; play.appendChild(p.el); p.play(); won = true; }
  }, "Searching…"));
  api("levels").then((r) => {
    levels = r.levels;
    pick.innerHTML = levels.map((l, i) => `<option value="${i}">${l.name}</option>`).join("");
    pick.value = 1;
    load();
  });
});
})();
