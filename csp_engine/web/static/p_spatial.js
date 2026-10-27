"use strict";
(() => {
const { h, api, busy, census, stats, metricPairs, showError, bubble, algoSelect, labeled, banner, COLORS } = Kit;

/* ============================================================= Tangram === */
Kit.register("tangram", (root) => {
  const pick = h("select");
  const fresh = h("button", { class: "btn" }, "Load shape");
  const solve = h("button", { class: "btn ghost" }, "Let the engine solve it");
  const rotate = h("button", { class: "btn ghost" }, "Rotate / flip (R)");
  const palette = h("div", { class: "toolbar" }), stage = h("div", { class: "stage", tabindex: 0 }), info = h("div"), st = h("div");
  root.append(h("div", { class: "toolbar" }, pick, fresh, solve),
    h("p", { class: "info" }, "Pick a tan below, press R to turn it, then click inside the grey silhouette to drop it. Click a placed tan to pick it back up. Fill the whole shape!"),
    palette, h("div", { class: "toolbar" }, rotate), stage, info, st);
  let shape = [], S = 34, maxX = 1, maxY = 1, inShape = new Set(), placed = {}, orients = null, sel = null, ori = 0, ghost = null, cv = null;
  const names = () => Object.keys(orients);
  const key = (x, y, q) => `${x},${y},${q}`;

  function tri(ctx, x, y, q) {
    const Y = (v) => (maxY - v) * S + 10, X = (v) => v * S + 10;
    const c = [x + 0.5, y + 0.5], pts = [[[x, y], [x + 1, y]], [[x + 1, y], [x + 1, y + 1]], [[x + 1, y + 1], [x, y + 1]], [[x, y + 1], [x, y]]][q];
    ctx.beginPath(); ctx.moveTo(X(pts[0][0]), Y(pts[0][1])); ctx.lineTo(X(pts[1][0]), Y(pts[1][1])); ctx.lineTo(X(c[0]), Y(c[1])); ctx.closePath();
  }
  function draw() {
    const ctx = cv.ctx;
    ctx.clearRect(0, 0, cv.w, cv.h);
    for (const [x, y, q] of shape) { tri(ctx, x, y, q); ctx.fillStyle = "#d9dee9"; ctx.fill(); }
    names().forEach((name, i) => {
      if (!placed[name]) return;
      for (const [x, y, q] of placed[name]) { tri(ctx, x, y, q); ctx.fillStyle = COLORS[i]; ctx.fill(); ctx.strokeStyle = COLORS[i]; ctx.lineWidth = 0.8; ctx.stroke(); }
    });
    if (ghost) for (const [x, y, q] of ghost.cells) { tri(ctx, x, y, q); ctx.fillStyle = ghost.ok ? "rgba(91,108,255,.35)" : "rgba(229,72,77,.3)"; ctx.fill(); }
    renderPalette();
  }
  function renderPalette() {
    palette.innerHTML = "";
    names().forEach((name, i) => {
      const b = h("button", { class: "btn ghost", style: { borderColor: COLORS[i], opacity: placed[name] ? 0.35 : 1, background: sel === name ? COLORS[i] : "#fff", color: sel === name ? "#fff" : "inherit" } }, name);
      b.addEventListener("click", () => { if (!placed[name]) { sel = name; ori = 0; draw(); stage.focus(); } });
      palette.appendChild(b);
    });
  }
  function occupied() { const s = new Set(); for (const cells of Object.values(placed)) if (cells) cells.forEach(([x, y, q]) => s.add(key(x, y, q))); return s; }
  function at(e) {
    const rc = cv.cv.getBoundingClientRect();
    return [Math.floor((e.clientX - rc.left - 10) / S), Math.floor(maxY - (e.clientY - rc.top - 10) / S)];
  }
  function candidate(mx, my) {
    const o = orients[sel][ori % orients[sel].length];
    const cx = Math.round((Math.max(...o.map((p) => p[0])) + 1) / 2 - 0.5), cy = Math.round((Math.max(...o.map((p) => p[1])) + 1) / 2 - 0.5);
    const cells = o.map(([x, y, q]) => [x + mx - cx, y + my - cy, q]);
    const occ = occupied();
    return { cells, ok: cells.every(([x, y, q]) => inShape.has(key(x, y, q)) && !occ.has(key(x, y, q))) };
  }
  function attach() {
    cv.cv.addEventListener("mousemove", (e) => { if (!sel) return; ghost = candidate(...at(e)); draw(); });
    cv.cv.addEventListener("mouseleave", () => { ghost = null; draw(); });
    cv.cv.addEventListener("click", (e) => {
      const [mx, my] = at(e);
      if (!sel) {                                   // pick a placed tan back up
        for (const [name, cells] of Object.entries(placed)) if (cells && cells.some(([x, y]) => x === mx && y === my)) { placed[name] = null; sel = name; draw(); return; }
        return;
      }
      const c = candidate(mx, my);
      if (!c.ok) return;
      placed[sel] = c.cells; sel = null; ghost = null; draw();
      if (names().every((n) => placed[n])) banner(info, "Solved! Every tan fits and the silhouette is full.");
    });
  }
  function setup() {
    maxX = Math.max(...shape.map((q) => q[0])) + 1; maxY = Math.max(...shape.map((q) => q[1])) + 1;
    S = Math.min(48, Math.floor(520 / Math.max(maxX, maxY)));
    cv = Kit.canvas(maxX * S + 20, maxY * S + 20);
    stage.innerHTML = ""; stage.appendChild(cv.cv);
    inShape = new Set(shape.map(([x, y, q]) => key(x, y, q)));
    placed = Object.fromEntries(names().map((n) => [n, null])); sel = null; ghost = null; info.innerHTML = ""; st.innerHTML = "";
    attach(); draw();
  }
  async function load() {
    if (!orients) orients = (await api("pieces")).pieces;
    const r = await api("new", { mode: pick.value || "Square" });
    shape = r.shape;
    if (!pick.options.length) pick.innerHTML = r.shapes.map((s) => `<option>${s}</option>`).join("");
    setup();
  }
  const turn = () => { if (sel) { ori++; draw(); } };
  rotate.addEventListener("click", turn);
  stage.addEventListener("keydown", (e) => { if (e.key === "r" || e.key === "R") { e.preventDefault(); turn(); } });
  fresh.addEventListener("click", busy(fresh, load));
  pick.addEventListener("change", load);
  solve.addEventListener("click", busy(solve, async () => {
    const r = await api("solve", { shape, algorithm: "smart" });
    placed = r.pieces; sel = null; draw();
    banner(info, "The engine's solution: seven pieces, no overlaps.");
    stats(st, [...metricPairs(r.metrics), ["placements considered", Object.values(r.domain_sizes).reduce((a, b) => a + b, 0)]]);
    census(r.census);
  }));
  load();
});

/* ============================================================ Rubik 2x2 === */
Kit.register("rubiks", (root) => {
  const depth = h("select", {}, ...[3, 5, 7, 9, 11].map((k) => h("option", { value: k }, `${k} random turns`)));
  depth.value = 7;
  const scramble = h("button", { class: "btn ghost" }, "Scramble");
  const solve = h("button", { class: "btn" }, "Solve optimally");
  const turns = h("div", { class: "toolbar" }, h("span", { class: "muted" }, "Turn it yourself:"),
    ...["U", "U'", "U2", "R", "R'", "R2", "F", "F'", "F2"].map((m) => h("button", { class: "btn ghost", onclick: () => turn(m) }, m)));
  const stage = h("div", { class: "stage" }), info = h("p", { class: "info" }), play = h("div"), rep = h("div");
  root.append(h("div", { class: "toolbar" }, depth, scramble, solve), turns, stage, info, play, rep);
  const COL = { U: "#f4f4f4", D: "#f3c13a", F: "#3fb950", B: "#2f81f7", R: "#e5484d", L: "#f0883e" };
  const POS = { U: [1, 0], L: [0, 1], F: [1, 1], R: [2, 1], B: [3, 1], D: [1, 2] };
  let state = null, faces = null;
  const cv = Kit.canvas(4 * 2 * 40 + 20, 3 * 2 * 40 + 20);
  stage.appendChild(cv.cv);
  function draw(f) {
    const { ctx } = cv, s = 40;
    ctx.clearRect(0, 0, cv.w, cv.h);
    for (const [face, [fx, fy]] of Object.entries(POS)) for (let i = 0; i < 4; i++) {
      const x = 10 + fx * 2 * s + (i % 2) * s, y = 10 + fy * 2 * s + Math.floor(i / 2) * s;
      ctx.fillStyle = COL[f[face][i]]; ctx.beginPath(); ctx.roundRect(x + 2, y + 2, s - 4, s - 4, 6); ctx.fill();
    }
    ctx.fillStyle = "#7a7f90"; ctx.font = "11px sans-serif";
    for (const [face, [fx, fy]] of Object.entries(POS)) ctx.fillText(face, 12 + fx * 2 * s, 8 + fy * 2 * s + 2 * s + 10);
  }
  async function turn(m) {
    const r = await api("turn", { state, move: m });
    state = r.state; faces = r.faces; draw(faces);
    info.textContent = r.solved ? "Solved!" : "";
  }
  scramble.addEventListener("click", busy(scramble, async () => {
    const r = await api("new", { moves: +depth.value });
    state = r.state; faces = r.faces; draw(faces);
    info.textContent = `Scramble: ${r.scramble.join(" ")}`; play.innerHTML = ""; rep.innerHTML = "";
  }));
  solve.addEventListener("click", busy(solve, async () => {
    const r = await api("solve", { state });
    if (!r.plan) { rep.innerHTML = ""; rep.appendChild(Kit.errorBox("Not solved within the search budget.")); return; }
    info.textContent = `Optimal solution (${r.plan.length} turns): ${r.plan.join(" ")}`;
    const p = Kit.player(r.faces.length, (i) => draw(r.faces[i]), { fps: 2 });
    play.innerHTML = ""; play.appendChild(p.el); p.play();
    rep.innerHTML = "";
    rep.appendChild(stats(h("div"), [["turns", r.plan.length], ["search nodes", r.metrics.nodes.toLocaleString()], ["time", `${r.metrics.elapsed_ms} ms`]]));
    rep.appendChild(h("p", { class: "info" }, "Pattern databases (exact turn counts for just the corner positions, and for just the twists) feed the 'can still finish in time' bound of the planning predicate."));
    census(r.census);
    state = null;
  }, "Searching…"));
  scramble.click();
});

/* ============================================================== Jigsaw === */
Kit.register("jigsaw", (root) => {
  const n = h("select", {}, ...[3, 4, 5, 6].map((k) => h("option", { value: k }, `${k}×${k}`)));
  n.value = 3;
  const fresh = h("button", { class: "btn" }, "New jigsaw");
  const solve = h("button", { class: "btn ghost" }, "Let the engine assemble it");
  const rotate = h("button", { class: "btn ghost" }, "Rotate selected (R)");
  const tray = h("div", { class: "stage", tabindex: 0 }), frame = h("div", { class: "stage" }), info = h("div"), st = h("div"), raceBox = h("div");
  root.append(h("div", { class: "toolbar" }, n, fresh, rotate, solve),
    h("p", { class: "info" }, "Click a piece in the box, turn it with R, then click a square in the frame. A bump must meet the same-coloured notch; flat edges go on the outside. Click a placed piece to take it back."),
    h("div", { class: "row2" }, h("div", {}, h("h3", {}, "The box"), tray), h("div", {}, h("h3", {}, "Your frame"), frame)), info, st,
    h("h3", {}, "Watch two solvers race"), raceBox);
  let J = null, rotOf = [], at = {}, sel = null;
  const SZ = 60;
  const rot = (e, k) => [0, 1, 2, 3].map((i) => e[((i - k) % 4 + 4) % 4]);
  function piece(ctx, x, y, s, e, hl, bad = []) {
    ctx.fillStyle = hl ? "#e7ebff" : "#ffffff";
    ctx.strokeStyle = hl ? "#5b6cff" : "#d9d6cf"; ctx.lineWidth = hl ? 3 : 1.5;
    ctx.beginPath(); ctx.roundRect(x + 3, y + 3, s - 6, s - 6, 8); ctx.fill(); ctx.stroke();
    const mids = [[x + s / 2, y + 3], [x + s - 3, y + s / 2], [x + s / 2, y + s - 3], [x + 3, y + s / 2]];
    e.forEach((code, side) => {
      const [mx, my] = mids[side];
      if (!code) { ctx.strokeStyle = "#8a90a3"; ctx.lineWidth = 3; ctx.beginPath();
        if (side % 2 === 0) { ctx.moveTo(x + 8, my); ctx.lineTo(x + s - 8, my); } else { ctx.moveTo(mx, y + 8); ctx.lineTo(mx, y + s - 8); } ctx.stroke(); return; }
      ctx.fillStyle = COLORS[(Math.abs(code) - 1) % 12];
      ctx.beginPath(); ctx.arc(mx, my, s * 0.17, 0, 7); ctx.fill();
      if (code < 0) { ctx.fillStyle = "#ffffff"; ctx.beginPath(); ctx.arc(mx, my, s * 0.08, 0, 7); ctx.fill(); }
      if (bad.includes(side)) { ctx.strokeStyle = "#e5484d"; ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(mx, my, s * 0.22, 0, 7); ctx.stroke(); }
    });
  }
  const used = () => new Set(Object.values(at).map((p) => p[0]));
  function edgesAt(r, c) { const p = at[`${r}|${c}`]; return p ? rot(J.pieces[p[0]], p[1]) : null; }
  function drawAll() {
    const k = J.n, cols = Math.min(k * k, 6), rows = Math.ceil((k * k) / cols);
    const t = Kit.canvas(cols * SZ, rows * SZ), u = used();
    J.pieces.forEach((p, i) => { if (!u.has(i)) piece(t.ctx, (i % cols) * SZ, Math.floor(i / cols) * SZ, SZ, rot(p, rotOf[i]), sel === i); });
    t.cv.addEventListener("click", (e) => {
      const rc = t.cv.getBoundingClientRect(), i = Math.floor((e.clientY - rc.top) / SZ) * cols + Math.floor((e.clientX - rc.left) / SZ);
      if (i < J.pieces.length && !used().has(i)) { sel = i; drawAll(); tray.focus(); }
    });
    tray.innerHTML = ""; tray.appendChild(t.cv);

    const f = Kit.canvas(k * SZ, k * SZ);
    f.ctx.fillStyle = "#f2efe7"; f.ctx.beginPath(); f.ctx.roundRect(0, 0, k * SZ, k * SZ, 12); f.ctx.fill();
    let good = 0, total = 0;
    for (let r = 0; r < k; r++) for (let c = 0; c < k; c++) {
      const e = edgesAt(r, c);
      if (!e) { f.ctx.strokeStyle = "#d9d6cf"; f.ctx.setLineDash([4, 4]); f.ctx.strokeRect(c * SZ + 4, r * SZ + 4, SZ - 8, SZ - 8); f.ctx.setLineDash([]); continue; }
      const bad = [];
      const nb = [[r - 1, c, 2], [r, c + 1, 3], [r + 1, c, 0], [r, c - 1, 1]];
      nb.forEach(([rr, cc, opp], side) => {
        const outside = rr < 0 || cc < 0 || rr >= k || cc >= k;
        if (outside) { total++; if (e[side] === 0) good++; else bad.push(side); return; }
        if (e[side] === 0) { bad.push(side); total++; return; }
        const o = edgesAt(rr, cc);
        if (o) { total++; if (o[opp] === -e[side]) good++; else bad.push(side); }
      });
      piece(f.ctx, c * SZ, r * SZ, SZ, e, false, bad);
    }
    f.cv.addEventListener("click", (e) => {
      const rc = f.cv.getBoundingClientRect(), r = Math.floor((e.clientY - rc.top) / SZ), c = Math.floor((e.clientX - rc.left) / SZ), key = `${r}|${c}`;
      if (at[key]) { const [pi, rr] = at[key]; delete at[key]; sel = pi; rotOf[pi] = rr; drawAll(); return; }
      if (sel === null) return;
      at[key] = [sel, rotOf[sel]]; sel = null; drawAll();
    });
    frame.innerHTML = ""; frame.appendChild(f.cv);
    const placed = Object.keys(at).length;
    if (placed === k * k && good === total) banner(info, "Assembled! Every edge fits.");
    else info.innerHTML = `<p class="info">Placed ${placed} of ${k * k} pieces. Red rings mark edges that don't fit.</p>`;
  }
  function draw(el, assign) {
    const k = J.n, c = Kit.canvas(k * SZ, k * SZ);
    for (const [key, val] of Object.entries(assign)) { const [r, q] = key.split("|").map(Number); piece(c.ctx, q * SZ, r * SZ, SZ, rot(J.pieces[val[0]], val[1])); }
    el.innerHTML = ""; el.appendChild(c.cv);
  }
  const turn = () => { if (sel !== null) { rotOf[sel] = (rotOf[sel] + 1) % 4; drawAll(); } };
  rotate.addEventListener("click", turn);
  tray.addEventListener("keydown", (e) => { if (e.key === "r" || e.key === "R") { e.preventDefault(); turn(); } });
  async function load() {
    J = await api("new", { n: +n.value }); rotOf = J.pieces.map(() => 0); at = {}; sel = null; st.innerHTML = "";
    drawAll();
    Kit.race(raceBox, { body: () => ({ inst: J }), defaults: ["fc", "smart"], makeView: (el) => ({ draw: (s) => draw(el, Object.fromEntries(s.assign)) }) });
  }
  fresh.addEventListener("click", busy(fresh, load));
  n.addEventListener("change", load);
  solve.addEventListener("click", busy(solve, async () => {
    const r = await api("solve", { inst: J, algorithm: "smart" });
    at = r.solution || {}; sel = null; drawAll();
    stats(st, metricPairs(r.metrics)); census(r.census);
  }));
  load();
});

/* =================================================== Polyomino tiling === */
Kit.register("polyomino", (root) => {
  const SHAPES = { F: [[0,1],[0,2],[1,0],[1,1],[2,1]], I: [[0,0],[1,0],[2,0],[3,0],[4,0]], L: [[0,0],[1,0],[2,0],[3,0],[3,1]],
    N: [[0,1],[1,1],[2,0],[2,1],[3,0]], P: [[0,0],[0,1],[1,0],[1,1],[2,0]], T: [[0,0],[0,1],[0,2],[1,1],[2,1]],
    U: [[0,0],[0,2],[1,0],[1,1],[1,2]], V: [[0,0],[1,0],[2,0],[2,1],[2,2]], W: [[0,0],[1,0],[1,1],[2,1],[2,2]],
    X: [[0,1],[1,0],[1,1],[1,2],[2,1]], Y: [[0,1],[1,0],[1,1],[2,1],[3,1]], Z: [[0,0],[0,1],[1,1],[2,1],[2,2]] };
  const norm = (cs) => { const mr = Math.min(...cs.map((c) => c[0])), mc = Math.min(...cs.map((c) => c[1])); return cs.map(([r, c]) => [r - mr, c - mc]).sort((a, b) => a[0] - b[0] || a[1] - b[1]); };
  function orientations(cells) {
    const out = [], seen = new Set();
    let cur = cells;
    for (let f = 0; f < 2; f++) {
      for (let k = 0; k < 4; k++) { cur = cur.map(([r, c]) => [c, -r]); const n = norm(cur), key = JSON.stringify(n); if (!seen.has(key)) { seen.add(key); out.push(n); } }
      cur = cur.map(([r, c]) => [r, -c]);
    }
    return out;
  }
  const pick = h("select");
  const count = h("select", {}, ...[4, 6, 8, 10].map((k) => h("option", { value: k }, `${k} pieces`)));
  count.value = 4;
  const fresh = h("button", { class: "btn" }, "Load");
  const solve = h("button", { class: "btn ghost" }, "Let the engine tile it");
  const turnBtn = h("button", { class: "btn ghost" }, "Rotate / flip (R)");
  const palette = h("div", { class: "toolbar" }), stage = h("div", { class: "stage", tabindex: 0 }), info = h("div"), st = h("div"), raceBox = h("div");
  root.append(h("div", { class: "toolbar" }, pick, count, fresh, solve),
    h("p", { class: "info" }, "Pick a piece, press R to turn or flip it, then click on the grey shape to drop it. Click a placed piece to pick it up again. Cover every square!"),
    palette, h("div", { class: "toolbar" }, turnBtn), stage, info, st, h("h3", {}, "Watch two solvers race"), raceBox);
  let P = null, placed = {}, sel = null, ori = 0, ghost = null, cs = 40, cv = null, region = new Set();
  const k2 = (r, c) => `${r},${c}`;
  function render(el, pieces, gh, interactive) {
    const cells = P.region, rows = Math.max(...cells.map((c) => c[0])) + 1, cols = Math.max(...cells.map((c) => c[1])) + 1;
    cs = Kit.fitSize(el, cols, rows, 46, 16);
    const c = Kit.canvas(cols * cs, rows * cs), ctx = c.ctx;
    for (const [r, q] of cells) { ctx.fillStyle = "#d9dee9"; ctx.beginPath(); ctx.roundRect(q * cs + 1, r * cs + 1, cs - 2, cs - 2, 5); ctx.fill(); }
    Object.entries(pieces || {}).forEach(([name, cl]) => {
      if (!cl) return;
      const i = P.pieces.indexOf(name);
      for (const [r, q] of cl) { ctx.fillStyle = COLORS[i % 12]; ctx.beginPath(); ctx.roundRect(q * cs + 1, r * cs + 1, cs - 2, cs - 2, 5); ctx.fill(); }
      const [r, q] = cl[0];
      ctx.fillStyle = "#fff"; ctx.font = `800 ${cs * 0.45}px Nunito, sans-serif`; ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText(name, q * cs + cs / 2, r * cs + cs / 2);
    });
    if (gh) for (const [r, q] of gh.cells) { ctx.fillStyle = gh.ok ? "rgba(91,108,255,.4)" : "rgba(229,72,77,.35)"; ctx.fillRect(q * cs + 2, r * cs + 2, cs - 4, cs - 4); }
    el.innerHTML = ""; el.appendChild(c.cv);
    if (interactive) { cv = c; attach(); }
  }
  function occupied() { const s = new Set(); for (const cl of Object.values(placed)) if (cl) cl.forEach(([r, c]) => s.add(k2(r, c))); return s; }
  function candidate(r0, c0) {
    const o = orientations(SHAPES[sel])[ori % orientations(SHAPES[sel]).length];
    const cells = o.map(([r, c]) => [r + r0 - o[0][0], c + c0 - o[0][1]]), occ = occupied();
    return { cells, ok: cells.every(([r, c]) => region.has(k2(r, c)) && !occ.has(k2(r, c))) };
  }
  const cellAt = (e) => { const rc = cv.cv.getBoundingClientRect(); return [Math.floor((e.clientY - rc.top) / cs), Math.floor((e.clientX - rc.left) / cs)]; };
  function attach() {
    cv.cv.addEventListener("mousemove", (e) => { if (!sel) return; ghost = candidate(...cellAt(e)); redraw(); });
    cv.cv.addEventListener("mouseleave", () => { ghost = null; redraw(); });
    cv.cv.addEventListener("click", (e) => {
      const [r, c] = cellAt(e);
      if (!sel) { for (const [name, cl] of Object.entries(placed)) if (cl && cl.some(([a, b]) => a === r && b === c)) { placed[name] = null; sel = name; ori = 0; redraw(); return; } return; }
      const cand = candidate(r, c);
      if (!cand.ok) return;
      placed[sel] = cand.cells; sel = null; ghost = null; redraw();
      if (P.pieces.every((p) => placed[p])) banner(info, "Tiled! Every square is covered with no overlaps.");
    });
  }
  function redraw() { render(stage, placed, ghost, true); renderPalette(); }
  function renderPalette() {
    palette.innerHTML = "";
    P.pieces.forEach((p, i) => {
      const b = h("button", { class: "btn ghost", style: { borderColor: COLORS[i % 12], opacity: placed[p] ? 0.35 : 1, background: sel === p ? COLORS[i % 12] : "#fff", color: sel === p ? "#fff" : "inherit", fontWeight: 800 } }, p);
      b.addEventListener("click", () => { if (!placed[p]) { sel = p; ori = 0; renderPalette(); stage.focus(); } });
      palette.appendChild(b);
    });
  }
  const turn = () => { if (sel) { ori++; if (ghost) ghost = null; redraw(); } };
  turnBtn.addEventListener("click", turn);
  stage.addEventListener("keydown", (e) => { if (e.key === "r" || e.key === "R") { e.preventDefault(); turn(); } });
  async function load() {
    const mode = pick.value || "Random shape";
    P = await api("new", { mode, pieces: +count.value });
    if (!pick.options.length) { pick.innerHTML = P.presets.map((p) => `<option>${p}</option>`).join(""); pick.value = "3×5 rectangle"; return load(); }
    region = new Set(P.region.map(([r, c]) => k2(r, c)));
    placed = Object.fromEntries(P.pieces.map((p) => [p, null])); sel = null; ghost = null; info.innerHTML = ""; st.innerHTML = "";
    redraw();
    Kit.race(raceBox, { body: () => ({ region: P.region, pieces: P.pieces }), defaults: ["naive", "smart"], makeView: (el, t) => ({ draw(s) {
      const pl = {};
      for (const [name, mask] of s.assign) pl[name] = t.placements[name][String(mask)];
      render(el, pl, null, false);
    } }) });
  }
  fresh.addEventListener("click", busy(fresh, load));
  pick.addEventListener("change", load);
  solve.addEventListener("click", busy(solve, async () => {
    const r = await api("solve", { region: P.region, pieces: P.pieces, algorithm: "smart" });
    if (!r.pieces) { st.innerHTML = ""; st.appendChild(Kit.errorBox("These pieces can't tile this shape.")); return; }
    placed = r.pieces; sel = null; redraw(); stats(st, metricPairs(r.metrics)); census(r.census);
  }));
  load();
});

/* ========================================================== Cube nets === */
Kit.register("folding", (root) => {
  const check = h("button", { class: "btn" }, "Will it fold into a cube?");
  const clear = h("button", { class: "btn ghost" }, "Clear");
  const all = h("button", { class: "btn ghost" }, "Test all 35 hexominoes");
  const editor = h("div", { class: "stage" }), verdict = h("div"), st = h("div"), gallery = h("div", { class: "stat-row" });
  root.append(h("div", { class: "toolbar" }, check, clear, all),
    h("p", { class: "info" }, "Click squares to draw a net (6 squares for a cube). The engine rolls a cube across your net: each square must land under a different face."),
    h("div", { class: "row2" }, editor, h("div", {}, verdict, st)), gallery);
  const N = 6, CS = 52;
  const FACE_COL = { bottom: "#f3c13a", top: "#f4f4f4", front: "#3fb950", back: "#2f81f7", right: "#e5484d", left: "#f0883e" };
  let cells = new Set(["1,1", "1,2", "1,3", "1,4", "0,2", "2,2"]), faces = null;
  const cv = Kit.canvas(N * CS, N * CS);
  editor.appendChild(cv.cv);
  cv.cv.addEventListener("click", (e) => {
    const rc = cv.cv.getBoundingClientRect(), k = `${Math.floor((e.clientY - rc.top) / CS)},${Math.floor((e.clientX - rc.left) / CS)}`;
    cells.has(k) ? cells.delete(k) : cells.add(k); faces = null; verdict.innerHTML = ""; draw();
  });
  function draw() {
    const { ctx } = cv;
    ctx.clearRect(0, 0, cv.w, cv.h);
    for (let r = 0; r < N; r++) for (let c = 0; c < N; c++) {
      const k = `${r},${c}`, on = cells.has(k);
      ctx.fillStyle = on ? (faces && faces[`${r}|${c}`] ? FACE_COL[faces[`${r}|${c}`]] : "#5b6cff") : "#f2efe7";
      ctx.fillRect(c * CS + 2, r * CS + 2, CS - 4, CS - 4);
      if (on && faces && faces[`${r}|${c}`]) { ctx.fillStyle = "#0b1020"; ctx.font = "bold 11px sans-serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText(faces[`${r}|${c}`], c * CS + CS / 2, r * CS + CS / 2); }
    }
  }
  function mini(shape, ok) {
    const s = 12, rows = Math.max(...shape.map((c) => c[0])) + 1, cols = Math.max(...shape.map((c) => c[1])) + 1;
    const c = Kit.canvas(cols * s + 8, rows * s + 8);
    for (const [r, q] of shape) { c.ctx.fillStyle = ok ? "#12a58a" : "#a3a9bb"; c.ctx.fillRect(4 + q * s, 4 + r * s, s - 1, s - 1); }
    const wrap = h("div", { class: "stat", style: { cursor: "pointer", borderColor: ok ? "var(--accent-2)" : "var(--border)" } }, c.cv);
    wrap.addEventListener("click", () => { cells = new Set(shape.map(([r, q]) => `${r + 1},${q + 1}`)); faces = null; verdict.innerHTML = ""; draw(); });
    return wrap;
  }
  check.addEventListener("click", busy(check, async () => {
    const r = await api("check", { cells: [...cells].map((k) => k.split(",").map(Number)) });
    faces = r.faces; draw();
    verdict.innerHTML = "";
    verdict.appendChild(bubble({ kind: r.folds ? "ok" : "mistake", text: r.folds
      ? "Yes — it folds into a cube. Each square is labelled with the cube face that lands on it."
      : cells.size !== 6 ? `A cube has 6 faces; this net has ${cells.size} squares.` : "No — rolling the cube across this net makes two squares land under the same face." }));
    stats(st, metricPairs(r.metrics)); census(r.census);
  }));
  clear.addEventListener("click", () => { cells = new Set(); faces = null; verdict.innerHTML = ""; draw(); });
  all.addEventListener("click", busy(all, async () => {
    const r = await api("all");
    const nets = r.hexominoes.filter((x) => x.folds).length;
    gallery.innerHTML = "";
    gallery.appendChild(h("div", { class: "bubble", style: { width: "100%" } }, `The engine generated all ${r.hexominoes.length} hexominoes and solved one CSP for each: exactly ${nets} fold into a cube (green) — the known answer. Click any to load it.`));
    r.hexominoes.forEach((x) => gallery.appendChild(mini(x.cells, x.folds)));
  }, "Testing…"));
  draw();
});
})();
