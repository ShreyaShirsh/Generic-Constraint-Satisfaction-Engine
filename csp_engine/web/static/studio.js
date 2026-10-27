"use strict";

const $ = (id) => document.getElementById(id);
const key = (r, c) => `${r},${c}`;
const LEVEL = { 1: "Easy", 2: "Medium", 3: "Hard", 4: "Expert" };
const OP_SYMBOL = { "+": "+", "*": "×", "-": "−", "/": "÷", "=": "" };
const BOX_SHAPES = { 4: [2, 2], 6: [2, 3], 8: [2, 4], 9: [3, 3] };

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

async function api(path, body) {
  const res = await fetch(path, body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "request failed");
  return data;
}

function showError(id, msg) {
  $(id).innerHTML = msg ? `<div class="error-box">${escapeHtml(msg)}</div>` : "";
}

// ======================================================= shared state ====
const S = {
  presets: [],
  current: null,            // the most recently generated / built puzzle
};

function puzzleList(includeQueens) {
  const list = S.presets.map((p) => ({ id: "preset:" + p.id, name: p.name, kind: "grid", spec: p.spec, grade: p.grade }));
  if (S.current) list.unshift({ id: "current", ...S.current });
  if (includeQueens) {
    list.push({ id: "queens:8", name: "N-Queens 8×8", kind: "nqueens", n: 8 });
    list.push({ id: "queens:12", name: "N-Queens 12×12", kind: "nqueens", n: 12 });
  }
  return list;
}

function fillSelect(select, includeQueens, wanted) {
  const keep = wanted || select.value;
  const list = puzzleList(includeQueens);
  select.innerHTML = list.map((p) => `<option value="${p.id}">${escapeHtml(p.name)}${p.grade ? " — " + p.grade.name : ""}</option>`).join("");
  if (list.some((p) => p.id === keep)) select.value = keep;
}

function puzzleById(id, includeQueens = true) {
  return puzzleList(includeQueens).find((p) => p.id === id);
}

// ======================================================= grid view ====
class GridView {
  constructor(container, spec, opts = {}) {
    this.spec = spec;
    this.n = spec.size;
    this.values = spec.values || Array.from({ length: this.n }, (_, i) => i + 1);
    this.opts = opts;
    this.build(container);
  }

  build(container) {
    const n = this.n, spec = this.spec, rules = spec.rules || {};
    const avail = Math.max(260, (container.clientWidth || 520) - 8);
    const cs = Math.max(26, Math.min(this.opts.max || 54, Math.floor(avail / n)));
    const grid = document.createElement("div");
    grid.className = "pgrid" + (this.opts.interactive ? " interactive" : "");
    grid.style.setProperty("--n", n);
    grid.style.setProperty("--cs", cs + "px");
    grid.style.setProperty("--cc", this.values.length <= 4 ? 2 : this.values.length <= 9 ? 3 : 4);

    const box = rules.boxes;
    const regionOf = {};
    (spec.regions || []).forEach((reg, i) => reg.cells.forEach(([r, c]) => (regionOf[key(r, c)] = i)));
    const cageOf = {};
    (spec.cages || []).forEach((cage, i) => cage.cells.forEach(([r, c]) => (cageOf[key(r, c)] = i)));

    this.cells = [];
    for (let r = 0; r < n; r++) {
      const row = [];
      for (let c = 0; c < n; c++) {
        const el = document.createElement("div");
        el.className = "pcell";
        if (box && (c + 1) % box[1] === 0 && c < n - 1) el.classList.add("bt-r");
        if (box && (r + 1) % box[0] === 0 && r < n - 1) el.classList.add("bt-b");
        const k = key(r, c);
        if (k in regionOf) el.classList.add("reg-" + (regionOf[k] % 6));
        else if (rules.diagonals && (r === c || r + c === n - 1)) el.classList.add("tint-diag");

        if (k in cageOf) {
          const idx = cageOf[k], cage = spec.cages[idx];
          const outline = document.createElement("div");
          outline.className = "cage";
          const same = (rr, cc) => cageOf[key(rr, cc)] === idx;
          outline.style.borderTopWidth = same(r - 1, c) ? "0" : "1.5px";
          outline.style.borderBottomWidth = same(r + 1, c) ? "0" : "1.5px";
          outline.style.borderLeftWidth = same(r, c - 1) ? "0" : "1.5px";
          outline.style.borderRightWidth = same(r, c + 1) ? "0" : "1.5px";
          el.appendChild(outline);
          const anchor = cage.cells.map(([a, b]) => [a, b]).sort((x, y) => x[0] - y[0] || x[1] - y[1])[0];
          if (anchor[0] === r && anchor[1] === c) {
            const lab = document.createElement("div");
            lab.className = "cage-label";
            lab.textContent = cage.target + (OP_SYMBOL[cage.op] ?? "");
            el.classList.add("has-label");
            el.appendChild(lab);
          }
        }

        const val = document.createElement("span");
        val.className = "val";
        el.appendChild(val);
        if (this.opts.onCell) {
          el.addEventListener("mousedown", (e) => { e.preventDefault(); this.opts.onCell(r, c, e); });
          el.addEventListener("mouseenter", (e) => this.opts.onEnter && this.opts.onEnter(r, c, e));
        }
        grid.appendChild(el);
        row.push({ el, val, cands: null, candEls: {} });
      }
      this.cells.push(row);
    }

    for (const { a, b } of spec.inequalities || []) {
      const [ar, ac] = a, [br, bc] = b;
      const m = document.createElement("div");
      if (ar === br && Math.abs(ac - bc) === 1) {
        const leftIsA = ac < bc;
        m.className = "ineq h";
        m.textContent = leftIsA ? "<" : ">";
        this.cells[ar][Math.min(ac, bc)].el.appendChild(m);
      } else if (ac === bc && Math.abs(ar - br) === 1) {
        const topIsA = ar < br;
        m.className = "ineq v";
        m.textContent = topIsA ? "∧" : "∨";
        this.cells[Math.min(ar, br)][ac].el.appendChild(m);
      }
    }

    container.innerHTML = "";
    container.appendChild(grid);
    this.grid = grid;
  }

  setValue(r, c, v, kind) {
    const cell = this.cells[r][c];
    cell.el.classList.remove("given", "entry", "ai", "sol");
    cell.el.classList.add(kind);
    cell.val.textContent = v;
    if (cell.cands) cell.cands.style.display = "none";
  }

  clearValue(r, c) {
    const cell = this.cells[r][c];
    cell.el.classList.remove("given", "entry", "ai", "sol");
    cell.val.textContent = "";
    if (cell.cands) cell.cands.style.display = "";
  }

  hasValue(r, c) { return this.cells[r][c].val.textContent !== ""; }

  showCands(r, c, present) {
    const cell = this.cells[r][c];
    if (!cell.cands) {
      cell.cands = document.createElement("div");
      cell.cands.className = "cands";
      for (const v of this.values) {
        const s = document.createElement("span");
        s.textContent = v;
        cell.cands.appendChild(s);
        cell.candEls[v] = s;
      }
      cell.el.appendChild(cell.cands);
    }
    const set = new Set(present);
    for (const v of this.values) cell.candEls[v].classList.toggle("gone", !set.has(v));
    cell.cands.style.display = this.hasValue(r, c) ? "none" : "";
  }

  candGone(r, c, v, gone) {
    const s = this.cells[r][c].candEls[v];
    if (s) s.classList.toggle("gone", gone);
  }

  hideAllCands() {
    for (const row of this.cells) for (const cell of row) if (cell.cands) cell.cands.style.display = "none";
  }

  mark(cells, cls) { for (const [r, c] of cells) this.cells[r]?.[c]?.el.classList.add(cls); }
  unmark(cls) { this.grid.querySelectorAll("." + cls).forEach((el) => el.classList.remove(cls)); }

  flash(r, c) {
    const el = this.cells[r][c].el;
    el.classList.remove("flash-bad");
    void el.offsetWidth;
    el.classList.add("flash-bad");
  }
}

function givensMap(spec) {
  const m = new Map();
  for (const [r, c, v] of spec.givens || []) m.set(key(r, c), v);
  return m;
}

// ================================================ N-Queens view (watch) ====
class QueensView {
  constructor(container, n) {
    this.n = n;
    const grid = document.createElement("div");
    grid.className = "qgrid";
    const cs = Math.max(24, Math.min(44, Math.floor(((container.clientWidth || 420) - 8) / n)));
    grid.style.setProperty("--n", n);
    grid.style.setProperty("--cs", cs + "px");
    this.cells = [];
    for (let r = 0; r < n; r++) {
      const row = [];
      for (let c = 0; c < n; c++) {
        const el = document.createElement("div");
        el.className = "qcell " + ((r + c) % 2 ? "dark" : "light");
        const dot = document.createElement("div");
        dot.className = "dot";
        const queen = document.createElement("span");
        queen.className = "queen";
        el.append(dot, queen);
        grid.appendChild(el);
        row.push({ el, dot, queen });
      }
      this.cells.push(row);
    }
    container.innerHTML = "";
    container.appendChild(grid);
    this.grid = grid;
  }
}

// ======================================================= watch mode ====
const WATCH_ALGOS = [
  ["naive", "Naive backtracking"],
  ["fc", "Forward checking"],
  ["mac", "Arc consistency (MAC)"],
  ["mac_mrv", "MAC + MRV"],
  ["full", "MAC + MRV + degree + LCV"],
  ["smart", "MAC + MRV + pigeonhole groups"],
];

class Lane {
  constructor(root, defaultAlgo) {
    this.root = root;
    this.select = root.querySelector(".lane-algo");
    this.select.innerHTML = WATCH_ALGOS.map(([k, l]) => `<option value="${k}">${l}</option>`).join("");
    this.select.value = defaultAlgo;
    this.wrap = root.querySelector(".board-wrap");
    this.stats = root.querySelector(".lane-stats");
    this.status = root.querySelector(".lane-status");
  }

  load(puzzle, trace) {
    this.puzzle = puzzle;
    this.trace = trace;
    this.i = 0;
    this.counts = { guesses: 0, backtracks: 0, crossed: 0 };
    this.current = null;
    this.done = false;
    this.givens = puzzle.kind === "grid" ? givensMap(puzzle.spec) : new Map();
    this.vars = trace.vars.map((k) => k.split(",").map(Number));

    if (puzzle.kind === "nqueens") {
      this.view = new QueensView(this.wrap, puzzle.n);
      this.qdom = trace.vars.map((k) => new Set(trace.initial[k]));
      for (let c = 0; c < puzzle.n; c++) {
        for (let r = 0; r < puzzle.n; r++) this.view.cells[r][c].dot.classList.toggle("gone", !this.qdom[c].has(r));
      }
    } else {
      this.view = new GridView(this.wrap, puzzle.spec, { max: 44 });
      trace.vars.forEach((k, idx) => {
        const [r, c] = this.vars[idx];
        if (this.givens.has(k)) this.view.setValue(r, c, this.givens.get(k), "given");
        else this.view.showCands(r, c, trace.initial[k]);
      });
    }
    this.status.textContent = "";
    this.status.className = "lane-status";
    this.renderStats();
  }

  apply(ev) {
    const [t, idx, v] = ev;
    if (t === "s") {
      this.view.grid.classList.add("solved-glow");
      return;
    }
    const pos = this.vars[idx];
    if (this.puzzle.kind === "nqueens") return this.applyQueens(t, pos[0], v);
    const [r, c] = pos;
    const given = this.givens.has(key(r, c));
    if (t === "a") {
      this.counts.guesses += given ? 0 : 1;
      if (!given) {
        this.view.setValue(r, c, v, "ai");
        if (this.current) this.view.cells[this.current[0]][this.current[1]].el.classList.remove("current");
        this.view.cells[r][c].el.classList.add("current");
        this.current = [r, c];
      }
    } else if (t === "p") {
      this.counts.crossed += 1;
      this.view.candGone(r, c, v, true);
    } else if (t === "r") {
      this.view.candGone(r, c, v, false);
    } else if (t === "u") {
      if (!given) {
        this.counts.backtracks += 1;
        this.view.clearValue(r, c);
        this.view.cells[r][c].el.classList.remove("current");
        this.view.flash(r, c);
      }
    }
  }

  applyQueens(t, col, row) {
    const cell = this.view.cells[row]?.[col];
    if (t === "a") {
      this.counts.guesses += 1;
      cell.queen.textContent = "♛";
      if (this.current) this.current.el.classList.remove("current");
      cell.el.classList.add("current");
      this.current = cell;
      for (let r = 0; r < this.puzzle.n; r++) this.view.cells[r][col].dot.style.visibility = "hidden";
    } else if (t === "p") {
      this.counts.crossed += 1;
      cell.dot.classList.add("gone");
    } else if (t === "r") {
      cell.dot.classList.remove("gone");
    } else if (t === "u") {
      this.counts.backtracks += 1;
      cell.queen.textContent = "";
      cell.el.classList.remove("current");
      for (let r = 0; r < this.puzzle.n; r++) this.view.cells[r][col].dot.style.visibility = "";
      cell.el.classList.remove("flash-bad");
      void cell.el.offsetWidth;
      cell.el.classList.add("flash-bad");
    }
  }

  step(k) {
    if (!this.trace || this.done) return true;
    const ev = this.trace.events;
    const end = Math.min(ev.length, this.i + k);
    for (; this.i < end; this.i++) this.apply(ev[this.i]);
    if (this.i >= ev.length) this.finish();
    this.renderStats();
    return this.done;
  }

  finish() {
    this.done = true;
    if (this.current && this.current.el) this.current.el.classList.remove("current");
    else if (this.current) this.view.cells[this.current[0]][this.current[1]].el.classList.remove("current");
    const m = this.trace.metrics;
    const guesses = this.counts.guesses.toLocaleString();
    if (m.solved) {
      this.status.textContent = `Solved — ${guesses} guesses, ${m.elapsed_ms} ms`;
      this.status.className = "lane-status ok";
    } else {
      this.status.textContent = this.trace.truncated
        ? `Still searching after ${guesses} guesses — replay limit reached`
        : "No solution";
      this.status.className = "lane-status bad";
    }
  }

  renderStats() {
    const total = this.trace ? this.trace.events.length : 0;
    const pct = total ? Math.round((this.i / total) * 100) : 0;
    this.stats.innerHTML = `
      <div class="metric"><div class="label">guesses</div><div class="value">${this.counts.guesses.toLocaleString()}</div></div>
      <div class="metric"><div class="label">backtracks</div><div class="value">${this.counts.backtracks.toLocaleString()}</div></div>
      <div class="metric"><div class="label">crossed out</div><div class="value">${this.counts.crossed.toLocaleString()}</div></div>
      <div class="metric"><div class="label">progress</div><div class="value">${pct}%</div></div>`;
  }
}

const W = {
  lanes: [new Lane($("lane-a"), "naive"), new Lane($("lane-b"), "smart")],
  playing: false, budget: 0, last: 0,
};

function speedRate() {
  const s = +$("w-speed").value;
  return Math.max(1, Math.round(Math.pow(10, (s / 100) * 3.7)));
}
function updateSpeedLabel() { $("w-speed-label").textContent = speedRate().toLocaleString() + " steps/s"; }
$("w-speed").addEventListener("input", updateSpeedLabel);
updateSpeedLabel();

function setWatchButtons(enabled) {
  ["w-play", "w-step", "w-end"].forEach((id) => ($(id).disabled = !enabled));
}

function setPlaying(on) {
  W.playing = on;
  $("w-play").innerHTML = on ? "&#10074;&#10074; Pause" : "&#9654; Play";
  if (on) { W.last = performance.now(); W.budget = 0; setTimeout(tick, 16); }
}

function tick() {
  if (!W.playing) return;
  const now = performance.now();
  const dt = Math.min(0.25, (now - W.last) / 1000);
  W.last = now;
  W.budget += speedRate() * dt;
  const k = Math.floor(W.budget);
  W.budget -= k;
  let allDone = true;
  if (k > 0) for (const lane of W.lanes) allDone = lane.step(k) && allDone;
  else allDone = W.lanes.every((l) => l.done);
  if (allDone) { setPlaying(false); return; }
  setTimeout(tick, 16);
}

async function runWatch() {
  showError("w-error", "");
  const puzzle = puzzleById($("w-puzzle").value);
  if (!puzzle) return;
  setPlaying(false);
  setWatchButtons(false);
  const btn = $("w-run");
  btn.disabled = true;
  btn.textContent = "Thinking…";
  try {
    const req = puzzle.kind === "nqueens" ? { kind: "nqueens", n: puzzle.n } : { kind: "grid", spec: puzzle.spec };
    const traces = await Promise.all(W.lanes.map((lane) =>
      api("/api/studio/trace", { puzzle: req, algorithm: lane.select.value })));
    W.lanes.forEach((lane, i) => lane.load(puzzle, traces[i]));
    setWatchButtons(true);
    setPlaying(true);
  } catch (e) {
    showError("w-error", e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "Run both";
  }
}

$("w-run").addEventListener("click", runWatch);
$("w-play").addEventListener("click", () => setPlaying(!W.playing));
$("w-step").addEventListener("click", () => { setPlaying(false); W.lanes.forEach((l) => l.step(1)); });
$("w-end").addEventListener("click", () => { setPlaying(false); W.lanes.forEach((l) => l.step(Infinity)); });
$("w-puzzle").addEventListener("change", () => {
  const p = puzzleById($("w-puzzle").value);
  if (p && p.kind === "nqueens") { W.lanes[0].select.value = "naive"; W.lanes[1].select.value = "full"; }
});

function previewWatch() {
  const puzzle = puzzleById($("w-puzzle").value);
  if (!puzzle) return;
  for (const lane of W.lanes) {
    lane.trace = null;
    lane.status.textContent = "";
    lane.stats.innerHTML = "";
    if (puzzle.kind === "nqueens") new QueensView(lane.wrap, puzzle.n);
    else {
      const v = new GridView(lane.wrap, puzzle.spec, { max: 44 });
      for (const [r, c, val] of puzzle.spec.givens || []) v.setValue(r, c, val, "given");
    }
  }
  setWatchButtons(false);
}
$("w-puzzle").addEventListener("change", () => { setPlaying(false); previewWatch(); });

// ======================================================= play mode ====
const P = {
  puzzle: null, view: null, entries: new Map(), givens: new Map(), selected: null,
  hints: 0, start: 0, timer: null, solved: false, pending: null,
};

function loadPlay(puzzle) {
  P.puzzle = puzzle;
  P.entries = new Map();
  P.givens = givensMap(puzzle.spec);
  P.selected = null;
  P.hints = 0;
  P.solved = false;
  $("p-hints").textContent = "0";
  $("p-coach").innerHTML = "";
  $("p-banner").innerHTML = "";
  P.view = new GridView($("p-board"), puzzle.spec, { interactive: true, max: 56, onCell: playClick });
  for (const [r, c, v] of puzzle.spec.givens || []) P.view.setValue(r, c, v, "given");
  const n = puzzle.spec.size;
  $("p-numpad").innerHTML = Array.from({ length: n }, (_, i) => `<button data-v="${i + 1}">${i + 1}</button>`).join("")
    + `<button data-v="0" title="clear">&#9003;</button>`;
  $("p-grade").innerHTML = puzzle.grade
    ? `Graded <span class="lvl lvl-${puzzle.grade.level}">${puzzle.grade.name}</span> by the engine — needs ${escapeHtml(puzzle.grade.technique)}.`
    : "";
  clearInterval(P.timer);
  P.start = Date.now();
  P.timer = setInterval(() => {
    const s = Math.floor((Date.now() - P.start) / 1000);
    $("p-timer").textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  }, 500);
  if ($("p-pencil").checked) refreshPencil();
}

function playClick(r, c) {
  P.view.unmark("selected");
  if (P.givens.has(key(r, c))) { P.selected = null; return; }
  P.selected = [r, c];
  P.view.mark([[r, c]], "selected");
}

function playEntries() {
  return [...P.entries].map(([k, v]) => [...k.split(",").map(Number), v]);
}

function setEntry(r, c, v) {
  if (P.solved || P.givens.has(key(r, c))) return;
  P.view.unmark("hint-target");
  P.view.unmark("hint-reason");
  if (v) { P.entries.set(key(r, c), v); P.view.setValue(r, c, v, "entry"); }
  else { P.entries.delete(key(r, c)); P.view.clearValue(r, c); }
  afterPlayChange();
}

function afterPlayChange() {
  clearTimeout(P.pending);
  P.pending = setTimeout(async () => {
    const res = await api("/api/studio/check", { spec: P.puzzle.spec, entries: playEntries() });
    P.view.unmark("conflict");
    for (const conf of res.conflicts) P.view.mark(conf.cells, "conflict");
    if (res.solved) {
      P.solved = true;
      clearInterval(P.timer);
      P.view.grid.classList.add("solved-glow");
      $("p-banner").innerHTML = `<div class="banner">Solved in ${$("p-timer").textContent} with ${P.hints} hint${P.hints === 1 ? "" : "s"}. Every constraint is satisfied.</div>`;
    }
    if ($("p-pencil").checked) refreshPencil();
  }, 120);
}

async function refreshPencil() {
  const res = await api("/api/studio/candidates", { spec: P.puzzle.spec, entries: playEntries(), level: 1 });
  const n = P.puzzle.spec.size;
  for (let r = 0; r < n; r++) for (let c = 0; c < n; c++) {
    const k = key(r, c);
    if (k in res.candidates) P.view.showCands(r, c, res.candidates[k]);
  }
}

$("p-pencil").addEventListener("change", () => {
  if ($("p-pencil").checked) refreshPencil(); else P.view.hideAllCands();
});

document.addEventListener("keydown", (e) => {
  if (currentMode() === "play" && P.view) {
    if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT" || e.target.tagName === "TEXTAREA") return;
    const n = P.puzzle.spec.size;
    if (!P.selected) return;
    let [r, c] = P.selected;
    if (/^[1-9]$/.test(e.key) && +e.key <= n) { setEntry(r, c, +e.key); e.preventDefault(); }
    else if (["Backspace", "Delete", "0"].includes(e.key)) { setEntry(r, c, 0); e.preventDefault(); }
    else if (e.key.startsWith("Arrow")) {
      const d = { ArrowUp: [-1, 0], ArrowDown: [1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1] }[e.key];
      r = (r + d[0] + n) % n; c = (c + d[1] + n) % n;
      P.view.unmark("selected");
      P.selected = [r, c];
      P.view.mark([[r, c]], "selected");
      e.preventDefault();
    }
  } else if (currentMode() === "build") {
    buildKey(e);
  }
});

$("p-numpad").addEventListener("click", (e) => {
  const v = e.target.dataset.v;
  if (v !== undefined && P.selected) setEntry(P.selected[0], P.selected[1], +v);
});

$("p-hint").addEventListener("click", async () => {
  if (!P.puzzle || P.solved) return;
  P.view.unmark("hint-target");
  P.view.unmark("hint-reason");
  const coach = $("p-coach");
  coach.innerHTML = `<div class="spinner-line">Thinking…</div>`;
  try {
    const h = await api("/api/studio/hint", { spec: P.puzzle.spec, entries: playEntries() });
    P.hints += 1;
    $("p-hints").textContent = P.hints;
    const warn = ["conflict", "mistake", "unsolvable"].includes(h.kind);
    const badge = h.level ? `<span class="lvl lvl-${h.level}">${escapeHtml(h.level_name)}</span>` : "";
    coach.innerHTML = `<div class="bubble ${warn ? "warn" : ""}">${badge}<p>${escapeHtml(h.text)}</p>
      ${h.cell ? `<button class="ghost apply" id="p-apply">Fill it in</button>` : ""}</div>`;
    if (warn) P.view.mark(h.highlight || [], "conflict");
    else {
      P.view.mark(h.highlight || [], "hint-reason");
      if (h.cell) P.view.mark([h.cell], "hint-target");
    }
    if (h.cell) $("p-apply").addEventListener("click", () => setEntry(h.cell[0], h.cell[1], h.value));
  } catch (e) {
    coach.innerHTML = `<div class="error-box">${escapeHtml(e.message)}</div>`;
  }
});

$("p-reset").addEventListener("click", () => P.puzzle && loadPlay(P.puzzle));
$("p-solve").addEventListener("click", async () => {
  if (!P.puzzle) return;
  const res = await api("/api/studio/solve", { spec: P.puzzle.spec });
  if (!res.solution) { $("p-coach").innerHTML = `<div class="bubble warn"><p>No solution exists.</p></div>`; return; }
  P.solved = true;
  clearInterval(P.timer);
  P.view.unmark("conflict");
  for (const [r, c, v] of res.solution) if (!P.givens.has(key(r, c))) P.view.setValue(r, c, v, P.entries.get(key(r, c)) === v ? "entry" : "sol");
});
$("p-puzzle").addEventListener("change", () => loadPlay(puzzleById($("p-puzzle").value, false)));

// ===================================================== generate mode ====
function gradeCard(grade, spec, stats, seconds) {
  const by = grade.steps_by_level || {};
  const parts = [1, 2, 3].map((l) => +(by[l] || 0));
  const open = grade.open_left || 0;
  const total = parts.reduce((a, b) => a + b, 0) + open || 1;
  const seg = (n, cls) => n ? `<div class="${cls}" style="width:${(n / total) * 100}%"></div>` : "";
  const cells = spec.size * spec.size;
  return `
    <span class="lvl lvl-${grade.level}">${LEVEL[grade.level]}</span>
    <h3>${grade.name}</h3>
    <p class="why">Needs <strong>${escapeHtml(grade.technique)}</strong>.
      ${grade.solved_by_logic
        ? `A person can solve it with logic alone in ${grade.steps} steps.`
        : `Logic alone fills ${grade.steps} cells, then gets stuck with ${open} open — from there you'd have to guess.`}</p>
    <div class="steps-bar">${seg(parts[0], "s1")}${seg(parts[1], "s2")}${seg(parts[2], "s3")}${seg(open, "s4")}</div>
    <div class="steps-legend">
      <span>■ direct: ${parts[0]}</span><span>■ only place: ${parts[1]}</span>
      <span>■ advanced: ${parts[2]}</span>${open ? `<span>■ needs guessing: ${open}</span>` : ""}
    </div>
    <dl class="facts">
      <dt>givens</dt><dd>${(spec.givens || []).length} of ${cells} cells</dd>
      ${stats ? `<dt>uniqueness proofs</dt><dd>${stats.uniqueness_checks} re-solves, all unique</dd>
      <dt>attempts</dt><dd>${stats.attempts}</dd>` : ""}
      ${seconds ? `<dt>time</dt><dd>${seconds.toFixed(1)} s</dd>` : ""}
    </dl>`;
}

$("g-go").addEventListener("click", async () => {
  showError("g-error", "");
  const [type, size] = $("g-type").value.split(":");
  const btn = $("g-go");
  btn.disabled = true;
  btn.textContent = "Generating… proving uniqueness";
  const t0 = performance.now();
  try {
    const res = await api("/api/studio/generate", { type, size: +size, difficulty: $("g-level").value });
    const label = $("g-type").selectedOptions[0].textContent;
    S.current = { name: `Generated: ${label}`, kind: "grid", spec: res.spec, grade: res.grade };
    refreshSelects();
    $("g-result").hidden = false;
    const v = new GridView($("g-board"), res.spec, { max: 50 });
    for (const [r, c, val] of res.spec.givens || []) v.setValue(r, c, val, "given");
    $("g-card").innerHTML = gradeCard(res.grade, res.spec, res.stats, (performance.now() - t0) / 1000);
  } catch (e) {
    showError("g-error", e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "Generate";
  }
});
$("g-play").addEventListener("click", () => openCurrent("play"));
$("g-watch").addEventListener("click", () => openCurrent("watch"));

function openCurrent(mode) {
  if (!S.current) return;
  refreshSelects();
  setMode(mode);
  if (mode === "play") { $("p-puzzle").value = "current"; loadPlay(puzzleById("current", false)); }
  else { $("w-puzzle").value = "current"; previewWatch(); runWatch(); }
}

// ======================================================== build mode ====
const B = {
  size: 6, rules: { rows: true, cols: true, boxes: null, diagonals: false },
  regions: [], cages: [], inequalities: [], givens: new Map(),
  tool: "select", picked: new Set(), dragging: false, ineqFirst: null, cursor: null,
  view: null, solution: null,
};

const TOOL_HELP = {
  select: "Click or drag across cells to select them, then make a region or a cage from the selection.",
  given: "Click a cell, then type a number to fix it as a given (Backspace removes it).",
  ineq: "Click the SMALLER cell, then its larger neighbour (left/right/up/down).",
  erase: "Click a cell to remove every given, region, cage and inequality touching it.",
};

function buildSpec(withGivens = true) {
  const spec = {
    size: B.size,
    rules: { rows: B.rules.rows, cols: B.rules.cols, boxes: B.rules.boxes, diagonals: B.rules.diagonals },
    regions: B.regions, cages: B.cages, inequalities: B.inequalities,
    givens: withGivens ? [...B.givens].map(([k, v]) => [...k.split(",").map(Number), v]) : [],
  };
  if (!spec.rules.boxes) delete spec.rules.boxes;
  return spec;
}

function renderBuild() {
  B.view = new GridView($("b-board"), buildSpec(), {
    interactive: true, max: 58, onCell: buildClick,
    onEnter: (r, c) => { if (B.dragging && B.tool === "select") { B.picked.add(key(r, c)); B.view.mark([[r, c]], "picked"); } },
  });
  for (const [k, v] of B.givens) { const [r, c] = k.split(",").map(Number); B.view.setValue(r, c, v, "given"); }
  if (B.solution) for (const [r, c, v] of B.solution) if (!B.givens.has(key(r, c))) B.view.setValue(r, c, v, "sol");
  B.view.mark([...B.picked].map((k) => k.split(",").map(Number)), "picked");
  if (B.ineqFirst) B.view.mark([B.ineqFirst], "selected");
  if (B.cursor && B.tool === "given") B.view.mark([B.cursor], "selected");
  renderRuleList();
  $("b-tool-help").textContent = TOOL_HELP[B.tool];
}

function syncRuleChecks() {
  $("b-rows").checked = B.rules.rows;
  $("b-cols").checked = B.rules.cols;
  $("b-boxes").checked = !!B.rules.boxes;
  $("b-boxes").disabled = !BOX_SHAPES[B.size];
  $("b-diag").checked = B.rules.diagonals;
}

function structureChanged() {
  B.solution = null;
  $("b-analysis").innerHTML = "";
  renderBuild();
}

function applyTemplate() {
  const t = $("b-template").value;
  B.rules = {
    rows: t !== "blank", cols: t !== "blank",
    boxes: t === "sudoku" ? (BOX_SHAPES[B.size] || null) : null, diagonals: false,
  };
  syncRuleChecks();
}

$("b-size").addEventListener("change", () => {
  B.size = +$("b-size").value;
  B.regions = []; B.cages = []; B.inequalities = []; B.givens = new Map(); B.picked = new Set();
  applyTemplate();
  structureChanged();
});
$("b-template").addEventListener("change", () => { applyTemplate(); structureChanged(); });
$("b-rows").addEventListener("change", (e) => { B.rules.rows = e.target.checked; structureChanged(); });
$("b-cols").addEventListener("change", (e) => { B.rules.cols = e.target.checked; structureChanged(); });
$("b-diag").addEventListener("change", (e) => { B.rules.diagonals = e.target.checked; structureChanged(); });
$("b-boxes").addEventListener("change", (e) => { B.rules.boxes = e.target.checked ? BOX_SHAPES[B.size] : null; structureChanged(); });

document.querySelectorAll("#b-tools button").forEach((btn) => btn.addEventListener("click", () => {
  document.querySelectorAll("#b-tools button").forEach((b) => b.classList.remove("active"));
  btn.classList.add("active");
  B.tool = btn.dataset.tool;
  B.ineqFirst = null;
  B.cursor = null;
  $("b-select-actions").style.display = B.tool === "select" ? "" : "none";
  renderBuild();
}));

document.addEventListener("mouseup", () => (B.dragging = false));

function cellInList(cells, r, c) { return cells.some(([a, b]) => a === r && b === c); }

function buildClick(r, c) {
  const k = key(r, c);
  if (B.tool === "select") {
    B.dragging = true;
    if (B.picked.has(k)) B.picked.delete(k); else B.picked.add(k);
    renderBuild();
  } else if (B.tool === "given") {
    B.cursor = [r, c];
    renderBuild();
  } else if (B.tool === "ineq") {
    if (!B.ineqFirst) { B.ineqFirst = [r, c]; renderBuild(); return; }
    const [ar, ac] = B.ineqFirst;
    B.ineqFirst = null;
    if (Math.abs(ar - r) + Math.abs(ac - c) !== 1) {
      showError("b-error", "Inequalities connect neighbouring cells — pick a cell next to the first one.");
      renderBuild();
      return;
    }
    showError("b-error", "");
    B.inequalities = B.inequalities.filter(({ a, b }) =>
      !((a[0] === ar && a[1] === ac && b[0] === r && b[1] === c) || (a[0] === r && a[1] === c && b[0] === ar && b[1] === ac)));
    B.inequalities.push({ a: [ar, ac], b: [r, c] });
    structureChanged();
  } else if (B.tool === "erase") {
    B.givens.delete(k);
    B.regions = B.regions.filter((reg) => !cellInList(reg.cells, r, c));
    B.cages = B.cages.filter((cg) => !cellInList(cg.cells, r, c));
    B.inequalities = B.inequalities.filter(({ a, b }) => !((a[0] === r && a[1] === c) || (b[0] === r && b[1] === c)));
    structureChanged();
  }
}

function buildKey(e) {
  if (B.tool !== "given" || !B.cursor) return;
  if (["INPUT", "SELECT", "TEXTAREA"].includes(e.target.tagName)) return;
  const [r, c] = B.cursor;
  if (/^[1-9]$/.test(e.key) && +e.key <= B.size) { B.givens.set(key(r, c), +e.key); e.preventDefault(); structureChanged(); }
  else if (["Backspace", "Delete", "0"].includes(e.key)) { B.givens.delete(key(r, c)); e.preventDefault(); structureChanged(); }
}

function pickedCells() {
  return [...B.picked].map((k) => k.split(",").map(Number)).sort((x, y) => x[0] - y[0] || x[1] - y[1]);
}

function takenByCage(cells) {
  return cells.some(([r, c]) => B.cages.some((cg) => cellInList(cg.cells, r, c)));
}

$("b-region").addEventListener("click", () => {
  const cells = pickedCells();
  if (cells.length < 2) return showError("b-error", "Select at least 2 cells for a region.");
  if (cells.length > B.size) return showError("b-error", `A region can't have more than ${B.size} cells — there are only ${B.size} different values.`);
  showError("b-error", "");
  B.regions.push({ cells, label: `region ${B.regions.length + 1}` });
  B.picked = new Set();
  structureChanged();
});

$("b-cage").addEventListener("click", () => {
  const cells = pickedCells();
  const op = $("b-op").value;
  const target = parseInt($("b-target").value, 10);
  if (!cells.length) return showError("b-error", "Select the cage's cells first.");
  if (!Number.isFinite(target)) return showError("b-error", "Give the cage a target number.");
  if ((op === "-" || op === "/") && cells.length !== 2) return showError("b-error", "Difference and ratio cages need exactly 2 cells.");
  if (takenByCage(cells)) return showError("b-error", "Some of those cells are already in a cage.");
  showError("b-error", "");
  const cage = { cells, op: cells.length === 1 ? "=" : op, target };
  if ($("b-distinct").checked) cage.distinct = true;
  B.cages.push(cage);
  B.picked = new Set();
  structureChanged();
});
$("b-clear-sel").addEventListener("click", () => { B.picked = new Set(); renderBuild(); });

function renderRuleList() {
  const items = [];
  B.regions.forEach((reg, i) => items.push([`Region ${i + 1}: ${reg.cells.length} cells all different`, () => B.regions.splice(i, 1)]));
  B.cages.forEach((cg, i) => items.push([`Cage ${cg.target}${OP_SYMBOL[cg.op]} over ${cg.cells.length} cell${cg.cells.length > 1 ? "s" : ""}${cg.distinct ? ", no repeats" : ""}`, () => B.cages.splice(i, 1)]));
  B.inequalities.forEach(({ a, b }, i) => items.push([`R${a[0] + 1}C${a[1] + 1} < R${b[0] + 1}C${b[1] + 1}`, () => B.inequalities.splice(i, 1)]));
  const ul = $("b-rules");
  ul.innerHTML = items.length ? "" : `<li style="color:var(--muted)">No regions, cages or inequalities yet.</li>`;
  items.forEach(([text, remove]) => {
    const li = document.createElement("li");
    li.innerHTML = `<span>${escapeHtml(text)}</span>`;
    const x = document.createElement("button");
    x.textContent = "✕";
    x.title = "remove";
    x.addEventListener("click", () => { remove(); structureChanged(); });
    li.appendChild(x);
    ul.appendChild(li);
  });
}

function analysisHtml(res) {
  const byType = Object.entries(res.compiled.by_type).map(([t, n]) => `<li>${n} × ${escapeHtml(t)}</li>`).join("");
  let verdict;
  if (res.solutions === 0) verdict = `<div class="verdict bad">No solution — these rules contradict each other.</div>`;
  else if (res.solutions === 1) verdict = `<div class="verdict ok">Exactly one solution — this is a valid puzzle.</div>`;
  else if (res.solutions === null) verdict = `<div class="verdict warn">Couldn't finish counting solutions within the search budget.</div>`;
  else verdict = `<div class="verdict warn">More than one solution — add givens or rules (or press "Make it a puzzle").</div>`;
  const grade = res.grade ? `<p>Difficulty: <span class="lvl lvl-${res.grade.level}">${res.grade.name}</span> — needs ${escapeHtml(res.grade.technique)}.</p>` : "";
  return `${verdict}${grade}
    <p style="color:var(--muted);margin:6px 0 2px">Your rules compiled into ${res.compiled.variables} variables and
    ${res.compiled.constraints} constraints — built only from the engine's two primitives:</p>
    <ul style="margin:4px 0 0 18px;padding:0">${byType}</ul>`;
}

$("b-analyze").addEventListener("click", async () => {
  showError("b-error", "");
  $("b-analysis").innerHTML = `<div class="spinner-line">Compiling and counting solutions…</div>`;
  try {
    const res = await api("/api/studio/analyze", { spec: buildSpec() });
    $("b-analysis").innerHTML = analysisHtml(res);
  } catch (e) { $("b-analysis").innerHTML = ""; showError("b-error", e.message); }
});

$("b-show-sol").addEventListener("click", async () => {
  showError("b-error", "");
  if (B.solution) { B.solution = null; renderBuild(); $("b-show-sol").textContent = "Show a solution"; return; }
  try {
    const res = await api("/api/studio/solve", { spec: buildSpec() });
    if (!res.solution) return showError("b-error", "No solution exists for these rules.");
    B.solution = res.solution;
    $("b-show-sol").textContent = "Hide solution";
    renderBuild();
  } catch (e) { showError("b-error", e.message); }
});

$("b-make").addEventListener("click", async () => {
  showError("b-error", "");
  const btn = $("b-make");
  btn.disabled = true;
  btn.textContent = "Generating…";
  try {
    const res = await api("/api/studio/make", { spec: buildSpec(), difficulty: $("b-level").value });
    B.givens = givensMap(res.spec);
    B.solution = null;
    $("b-show-sol").textContent = "Show a solution";
    S.current = { name: "Your invented puzzle", kind: "grid", spec: res.spec, grade: res.grade };
    refreshSelects();
    renderBuild();
    $("b-analysis").innerHTML = `<div class="verdict ok">Done — a uniquely solvable puzzle using your rules.</div>
      <p>Difficulty: <span class="lvl lvl-${res.grade.level}">${res.grade.name}</span> — needs ${escapeHtml(res.grade.technique)}.
      ${res.spec.givens.length} givens, ${res.stats.uniqueness_checks} uniqueness proofs.</p>`;
  } catch (e) { showError("b-error", e.message); }
  finally { btn.disabled = false; btn.textContent = "Make it a puzzle"; }
});

function currentFromBuild() {
  S.current = { name: "Your invented puzzle", kind: "grid", spec: buildSpec(), grade: null };
}
$("b-play").addEventListener("click", () => { currentFromBuild(); openCurrent("play"); });
$("b-watch").addEventListener("click", () => { currentFromBuild(); openCurrent("watch"); });

$("b-export").addEventListener("click", () => {
  const ta = $("b-json");
  ta.hidden = !ta.hidden;
  $("b-import").hidden = ta.hidden;
  if (!ta.hidden) ta.value = JSON.stringify(buildSpec(), null, 1);
});
$("b-import").addEventListener("click", () => {
  try {
    const spec = JSON.parse($("b-json").value);
    if (!BOX_SHAPES[spec.size] && spec.rules?.boxes) delete spec.rules.boxes;
    B.size = spec.size;
    $("b-size").value = String(spec.size);
    B.rules = { rows: !!spec.rules?.rows, cols: !!spec.rules?.cols, boxes: spec.rules?.boxes || null, diagonals: !!spec.rules?.diagonals };
    B.regions = spec.regions || []; B.cages = spec.cages || []; B.inequalities = spec.inequalities || [];
    B.givens = givensMap(spec);
    syncRuleChecks();
    showError("b-error", "");
    structureChanged();
  } catch (e) { showError("b-error", "Invalid JSON: " + e.message); }
});

// ============================================================ modes ====
function currentMode() {
  return document.querySelector("#modes button.active").dataset.mode;
}

function setMode(mode) {
  document.querySelectorAll("#modes button").forEach((b) => b.classList.toggle("active", b.dataset.mode === mode));
  document.querySelectorAll(".mode").forEach((m) => m.classList.toggle("active", m.id === "mode-" + mode));
  if (mode !== "watch") setPlaying(false);
  if (mode === "build" && !B.view) { applyTemplate(); renderBuild(); }
  if (mode === "play" && !P.puzzle) loadPlay(puzzleById($("p-puzzle").value, false));
}

document.querySelectorAll("#modes button").forEach((b) => b.addEventListener("click", () => setMode(b.dataset.mode)));

function refreshSelects() {
  fillSelect($("w-puzzle"), true);
  fillSelect($("p-puzzle"), false);
}

(async function init() {
  try {
    S.presets = await api("/api/studio/presets");
  } catch (e) {
    showError("w-error", "Couldn't load presets: " + e.message);
    return;
  }
  refreshSelects();
  $("w-puzzle").value = "preset:sudoku-expert";
  $("p-puzzle").value = "preset:sudoku-easy";
  previewWatch();
})();
