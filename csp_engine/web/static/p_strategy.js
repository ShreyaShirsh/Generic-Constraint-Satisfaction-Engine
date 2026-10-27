"use strict";
(() => {
const { h, api, busy, stats, showError, labeled, bubble, banner } = Kit;

function depthSelect(opts, def) {
  const s = h("select", {}, ...opts.map((d) => h("option", { value: d }, `look ${d} moves ahead`)));
  s.value = def;
  return s;
}

/* ========================================================= Connect Four === */
Kit.register("connect4", (root) => {
  const depth = depthSelect([2, 4, 6, 8], 6);
  const fresh = h("button", { class: "btn" }, "New game");
  const aiFirst = h("button", { class: "btn ghost" }, "Let the engine start");
  const status = h("p", { class: "info" }), stage = h("div", { class: "stage" }), st = h("div");
  root.append(h("div", { class: "toolbar" }, fresh, aiFirst, depth),
    h("p", { class: "info" }, "You are red. Click a column. The engine plays yellow by solving ∃ my move ∀ your reply ∃ … with alpha-beta pruning."),
    status, stage, st);
  const CS = 64, cv = Kit.canvas(7 * CS, 6 * CS);
  stage.appendChild(cv.cv);
  let cols, over, thinking = false, lastAI = null;

  const at = (r, c) => (r < cols[c].length ? cols[c][r] : 0);
  function winner() {
    const dirs = [[0, 1], [1, 0], [1, 1], [1, -1]];
    for (let r = 0; r < 6; r++) for (let c = 0; c < 7; c++) {
      const p = at(r, c);
      if (!p) continue;
      for (const [dr, dc] of dirs) {
        let k = 1;
        while (k < 4 && r + dr * k >= 0 && r + dr * k < 6 && c + dc * k >= 0 && c + dc * k < 7 && at(r + dr * k, c + dc * k) === p) k++;
        if (k === 4) return p;
      }
    }
    return cols.every((col) => col.length === 6) ? "draw" : null;
  }
  function draw() {
    const { ctx } = cv;
    ctx.fillStyle = "#4c6ef5"; ctx.fillRect(0, 0, cv.w, cv.h);
    for (let c = 0; c < 7; c++) for (let r = 0; r < 6; r++) {
      const p = at(r, c), y = (5 - r) * CS + CS / 2, x = c * CS + CS / 2;
      ctx.fillStyle = p === 1 ? "#e4572e" : p === 2 ? "#f3c13a" : "#ffffff";
      ctx.beginPath(); ctx.arc(x, y, CS * 0.4, 0, 7); ctx.fill();
      if (lastAI && lastAI[0] === r && lastAI[1] === c) { ctx.strokeStyle = "#fff"; ctx.lineWidth = 3; ctx.stroke(); }
    }
  }
  function setStatus() {
    const w = winner();
    over = !!w;
    status.textContent = w === 1 ? "You win!" : w === 2 ? "The engine wins." : w === "draw" ? "Draw." : thinking ? "Engine is thinking…" : "Your move.";
  }
  async function aiMove() {
    thinking = true; setStatus();
    const r = await api("move", { cols, to_move: 2, depth: +depth.value });
    thinking = false;
    if (r.move !== null) { cols[r.move].push(2); lastAI = [cols[r.move].length - 1, r.move]; }
    const verdict = r.score >= 999000 ? "it sees a forced win" : r.score <= -999000 ? "it sees you can force a win" : `position score ${Math.round(r.score)}`;
    stats(st, [["searched", `${r.depth} moves deep`], ["positions", r.nodes.toLocaleString()], ["time", `${r.ms} ms`], ["verdict", verdict]]);
    draw(); setStatus();
  }
  cv.cv.addEventListener("click", async (e) => {
    if (over || thinking) return;
    const c = Math.floor((e.clientX - cv.cv.getBoundingClientRect().left) / CS);
    if (cols[c].length >= 6) return;
    cols[c].push(1); lastAI = null; draw(); setStatus();
    if (!over) await aiMove();
  });
  const reset = () => { cols = Array.from({ length: 7 }, () => []); over = false; lastAI = null; st.innerHTML = ""; draw(); setStatus(); };
  fresh.addEventListener("click", reset);
  aiFirst.addEventListener("click", async () => { reset(); await aiMove(); });
  reset();
});

/* ======================================================== Chess tactics === */
Kit.register("chess", (root) => {
  const GLYPH = { K: "♔", Q: "♕", R: "♖", B: "♗", N: "♘", P: "♙", k: "♚", q: "♛", r: "♜", b: "♝", n: "♞", p: "♟" };
  const pick = h("select");
  const reset = h("button", { class: "btn" }, "Restart puzzle");
  const reveal = h("button", { class: "btn ghost" }, "Show the engine's proof");
  const info = h("p", { class: "info" }), stage = h("div", { class: "stage" }), coach = h("div"), log = h("div"), st = h("div");
  root.append(h("div", { class: "toolbar" }, pick, reset, reveal),
    h("p", { class: "info" }, "You are White. Click a piece, then its destination. If your move still forces mate, the engine replies with Black's toughest defence and you continue — mate the king to win."),
    info, stage, log, coach, st);
  const CS = 60, cv = Kit.canvas(8 * CS, 8 * CS);
  stage.appendChild(cv.cv);
  let puzzles = [], P = null, fen = null, left = 0, board = null, sel = null, hl = [], moves = [], over = false;

  function parse(f) {
    return f.split(" ")[0].split("/").map((row) => { const out = []; for (const ch of row) /\d/.test(ch) ? out.push(...Array(+ch).fill("")) : out.push(ch); return out; });
  }
  const sq = (r, c) => "abcdefgh"[c] + (8 - r);
  function draw() {
    const { ctx } = cv;
    for (let r = 0; r < 8; r++) for (let c = 0; c < 8; c++) {
      ctx.fillStyle = (r + c) % 2 ? "#c9ab84" : "#f0e6d6";
      if (hl.some(([a, b]) => a === r && b === c)) ctx.fillStyle = (r + c) % 2 ? "#d8c46a" : "#f3e7a0";
      if (sel && sel[0] === r && sel[1] === c) ctx.fillStyle = "#9fe3c7";
      ctx.fillRect(c * CS, r * CS, CS, CS);
      const p = board[r][c];
      if (p) {
        ctx.font = `${CS * 0.78}px serif`; ctx.textAlign = "center"; ctx.textBaseline = "middle";
        const white = p === p.toUpperCase();
        ctx.fillStyle = white ? "#ffffff" : "#2a2d3a"; ctx.strokeStyle = white ? "#2a2d3a" : "#2a2d3a"; ctx.lineWidth = 1.2;
        ctx.fillText(GLYPH[p], c * CS + CS / 2, r * CS + CS / 2 + 3);
        if (white) ctx.strokeText(GLYPH[p], c * CS + CS / 2, r * CS + CS / 2 + 3);
      }
    }
  }
  function moveSquares(uci) { return [[8 - +uci[1], uci.charCodeAt(0) - 97], [8 - +uci[3], uci.charCodeAt(2) - 97]]; }
  function showLog() { log.innerHTML = moves.length ? `<p class="info mono">${moves.map((m, i) => (i % 2 ? m : `${i / 2 + 1}. ${m}`)).join("  ")}</p>` : ""; }
  function load() {
    P = puzzles[+pick.value];
    fen = P.fen; left = P.moves; board = parse(fen); sel = null; hl = []; moves = []; over = false;
    coach.innerHTML = ""; st.innerHTML = ""; showLog();
    info.innerHTML = `<strong>${P.name}</strong> — White to play and mate in ${P.moves}.`;
    draw();
  }
  cv.cv.addEventListener("click", async (e) => {
    if (over) return;
    const rect = cv.cv.getBoundingClientRect();
    const c = Math.floor((e.clientX - rect.left) / CS), r = Math.floor((e.clientY - rect.top) / CS), p = board[r][c];
    if (!sel || (p && p === p.toUpperCase())) { if (p && p === p.toUpperCase()) { sel = [r, c]; draw(); } return; }
    let uci = sq(sel[0], sel[1]) + sq(r, c);
    if (board[sel[0]][sel[1]] === "P" && r === 0) uci += "q";
    sel = null;
    const res = await api("play", { fen, moves_left: left, move: uci });
    coach.innerHTML = "";
    if (!res.legal) { coach.appendChild(bubble({ kind: "mistake", text: "That isn't a legal move — try another." })); draw(); return; }
    moves.push(res.san); fen = res.fen; board = parse(fen); hl = moveSquares(uci); draw(); showLog();
    if (res.mate) { over = true; banner(coach, `Checkmate! ${res.san} — puzzle solved.`); return; }
    if (!res.wins) { over = true; banner(coach, `${res.san} lets Black escape — no forced mate any more. Press Restart and try again.`, true); return; }
    await Kit.sleep(500);
    moves.push(res.reply); left = res.moves_left; showLog();
    coach.appendChild(bubble({ kind: "ok", text: `Good move! Black's best defence is ${res.reply}. Now finish it — mate in ${left}.` }));
  });
  reveal.addEventListener("click", busy(reveal, async () => {
    load();
    const r = await api("solve", { fen: P.fen, moves: P.moves });
    stats(st, [["proved", r.win ? `mate in ${Math.ceil(r.depth / 2)}` : "no forced mate"], ["positions", r.nodes.toLocaleString()], ["time", `${r.ms} ms`]]);
    coach.appendChild(bubble({ kind: "ok", text: `∃ ∀ ∃ proof — White: ${r.san.filter((_, i) => !(i % 2)).join(", ")}; whatever Black tries, mate follows. Line: ${r.san.join("  ")}` }));
  }, "Proving…"));
  reset.addEventListener("click", load);
  pick.addEventListener("change", load);
  api("puzzles").then((r) => { puzzles = r.puzzles; pick.innerHTML = puzzles.map((p, i) => `<option value="${i}">${p.name} (mate in ${p.moves})</option>`).join(""); load(); });
});

/* ================================================================== Nim === */
Kit.register("nim", (root) => {
  const heapsIn = h("input", { type: "text", value: "3 4 5", style: { width: "120px" } });
  const fresh = h("button", { class: "btn" }, "New game (you start)");
  const analyse = h("button", { class: "btn ghost" }, "Ask the engine");
  const info = h("p", { class: "info" }), stage = h("div"), coach = h("div"), st = h("div");
  root.append(h("div", { class: "toolbar" }, labeled("heaps", heapsIn), fresh, analyse),
    h("p", { class: "info" }, "Take any number of stones from ONE heap (click a stone to take it and everything to its right). Whoever takes the last stone wins."),
    info, stage, coach, st);
  let heaps = [], turn = "you", over = false;

  function draw() {
    stage.innerHTML = "";
    heaps.forEach((n, i) => {
      const row = h("div", { style: { display: "flex", gap: "6px", alignItems: "center", margin: "8px 0" } }, h("span", { class: "tag" }, `heap ${i + 1}`));
      for (let k = 0; k < n; k++) {
        const s = h("span", { style: { width: "26px", height: "26px", borderRadius: "50%", background: Kit.COLORS[i % 12], cursor: over || turn !== "you" ? "default" : "pointer", display: "inline-block" } });
        s.addEventListener("click", () => take(i, n - k));
        row.appendChild(s);
      }
      stage.appendChild(row);
    });
    const ns = heaps.reduce((a, b) => a ^ b, 0);
    info.innerHTML = over ? `<strong>${turn === "you" ? "The engine took the last stone — it wins." : "You took the last stone — you win!"}</strong>`
      : `Turn: <strong>${turn === "you" ? "you" : "engine"}</strong> · nim-sum (XOR of the heaps) = <span class="mono">${ns}</span>`;
  }
  async function take(i, k) {
    if (over || turn !== "you" || k <= 0) return;
    heaps[i] -= k;
    if (heaps.every((x) => x === 0)) { over = true; turn = "engine"; draw(); return; }
    turn = "engine"; draw();
    await Kit.sleep(400);
    const r = await api("analyse", { heaps });
    let mv = r.winning_moves[0];
    if (!mv) { const big = heaps.indexOf(Math.max(...heaps)); mv = [big, 1]; }
    heaps[mv[0]] -= mv[1];
    coach.innerHTML = "";
    coach.appendChild(bubble({ kind: "ok", text: r.position_won
      ? `Engine took ${mv[1]} from heap ${mv[0] + 1}. Its quantified search proved this move wins (${r.nodes.toLocaleString()} positions).`
      : `Engine took ${mv[1]} from heap ${mv[0] + 1} — it has proved it is losing if you play perfectly, so it stalls.` }));
    if (heaps.every((x) => x === 0)) { over = true; turn = "you"; draw(); return; }
    turn = "you"; draw();
  }
  analyse.addEventListener("click", busy(analyse, async () => {
    const r = await api("analyse", { heaps });
    coach.innerHTML = "";
    coach.appendChild(bubble({ kind: "ok", text: r.position_won
      ? `The player to move WINS. Winning moves: ${r.winning_moves.map(([i, k]) => `take ${k} from heap ${i + 1}`).join("; ")}. Note the nim-sum is ${r.nim_sum} ≠ 0 — the engine rediscovered the classic theory without being told it.`
      : `The player to move LOSES against perfect play. The nim-sum is 0 — exactly what the theory predicts.` }));
    stats(st, [["positions searched", r.nodes.toLocaleString()], ["time", `${r.ms} ms`]]);
  }));
  fresh.addEventListener("click", () => {
    heaps = heapsIn.value.trim().split(/[\s,]+/).map(Number).filter((x) => x > 0 && x <= 15).slice(0, 6);
    turn = "you"; over = false; coach.innerHTML = ""; st.innerHTML = ""; draw();
  });
  fresh.click();
});

/* ============================================================== Othello === */
Kit.register("othello", (root) => {
  const depth = depthSelect([1, 2, 3, 4, 5], 4);
  const fresh = h("button", { class: "btn" }, "New game");
  const status = h("p", { class: "info" }), stage = h("div", { class: "stage" }), st = h("div");
  root.append(h("div", { class: "toolbar" }, fresh, depth),
    h("p", { class: "info" }, "You are black. Green dots mark your legal moves. The engine plays white with quantified (minimax) search."),
    status, stage, st);
  const N = 8, CS = 58, cv = Kit.canvas(N * CS, N * CS);
  stage.appendChild(cv.cv);
  let b, thinking = false, last = null;
  const D8 = [[-1, -1], [-1, 0], [-1, 1], [0, -1], [0, 1], [1, -1], [1, 0], [1, 1]];

  function flips(i, p) {
    const r0 = Math.floor(i / N), c0 = i % N, out = [];
    if (b[i]) return out;
    for (const [dr, dc] of D8) {
      let r = r0 + dr, c = c0 + dc; const run = [];
      while (r >= 0 && r < N && c >= 0 && c < N && b[r * N + c] === 3 - p) { run.push(r * N + c); r += dr; c += dc; }
      if (run.length && r >= 0 && r < N && c >= 0 && c < N && b[r * N + c] === p) out.push(...run);
    }
    return out;
  }
  const legal = (p) => b.map((_, i) => i).filter((i) => flips(i, p).length);
  function play(i, p) { for (const j of flips(i, p)) b[j] = p; b[i] = p; last = i; }
  function draw() {
    const { ctx } = cv;
    ctx.fillStyle = "#1e6b45"; ctx.fillRect(0, 0, cv.w, cv.h);
    ctx.strokeStyle = "#0e3f28";
    for (let k = 0; k <= N; k++) { ctx.beginPath(); ctx.moveTo(k * CS, 0); ctx.lineTo(k * CS, cv.h); ctx.moveTo(0, k * CS); ctx.lineTo(cv.w, k * CS); ctx.stroke(); }
    const mine = thinking ? [] : legal(1);
    b.forEach((v, i) => {
      const x = (i % N) * CS + CS / 2, y = Math.floor(i / N) * CS + CS / 2;
      if (v) { ctx.fillStyle = v === 1 ? "#111" : "#f3f3f3"; ctx.beginPath(); ctx.arc(x, y, CS * 0.4, 0, 7); ctx.fill();
        if (i === last) { ctx.strokeStyle = "#f3c13a"; ctx.lineWidth = 3; ctx.stroke(); } }
      else if (mine.includes(i)) { ctx.fillStyle = "rgba(18,165,138,.7)"; ctx.beginPath(); ctx.arc(x, y, CS * 0.1, 0, 7); ctx.fill(); }
    });
    const bl = b.filter((x) => x === 1).length, wh = b.filter((x) => x === 2).length;
    const done = !legal(1).length && !legal(2).length;
    status.textContent = done ? (bl > wh ? `You win ${bl}–${wh}!` : wh > bl ? `Engine wins ${wh}–${bl}.` : "Draw.")
      : `Black (you) ${bl} · White (engine) ${wh} · ${thinking ? "engine thinking…" : "your move"}`;
  }
  async function engine() {
    while (true) {
      if (!legal(2).length) break;
      thinking = true; draw();
      const r = await api("move", { board: b, to_move: 2, depth: +depth.value, n: N });
      thinking = false;
      if (r.move !== null && r.move !== "pass") play(r.move, 2);
      stats(st, [["searched", `${r.depth} moves deep`], ["positions", (r.nodes || 0).toLocaleString()], ["time", `${r.ms} ms`]]);
      draw();
      if (legal(1).length) break;
      if (!legal(2).length) break;
      await Kit.sleep(500);
    }
  }
  cv.cv.addEventListener("click", async (e) => {
    if (thinking) return;
    const rect = cv.cv.getBoundingClientRect();
    const i = Math.floor((e.clientY - rect.top) / CS) * N + Math.floor((e.clientX - rect.left) / CS);
    if (!flips(i, 1).length) return;
    play(i, 1); draw();
    await Kit.sleep(250);
    await engine();
    if (!legal(1).length && legal(2).length) await engine();
  });
  fresh.addEventListener("click", () => {
    b = Array(N * N).fill(0);
    b[27] = b[36] = 2; b[28] = b[35] = 1; last = null; st.innerHTML = ""; draw();
  });
  fresh.click();
});

/* ================================================================= Hex === */
Kit.register("hex", (root) => {
  const size = h("select", {}, ...[3, 4, 5, 6, 7].map((n) => h("option", { value: n }, `${n}×${n}`)));
  size.value = 5;
  const fresh = h("button", { class: "btn" }, "New game");
  const prove = h("button", { class: "btn ghost" }, "Prove who wins (3×3 / 4×4)");
  const status = h("p", { class: "info" }), stage = h("div", { class: "stage" }), coach = h("div"), st = h("div");
  root.append(h("div", { class: "toolbar" }, size, fresh, prove),
    h("p", { class: "info" }, "You are red: connect TOP to BOTTOM. The engine is blue: LEFT to RIGHT. On small boards it plays proven winning moves."),
    status, stage, coach, st);
  let n, b, cv, R, over, thinking, winMarks = [];
  const NB = [[-1, 0], [-1, 1], [0, -1], [0, 1], [1, -1], [1, 0]];
  const centre = (r, c) => [R * 1.6 + c * R * 1.732 + r * R * 0.866, R * 1.6 + r * R * 1.5];

  function connected(p) {
    const start = [];
    for (let k = 0; k < n; k++) { const i = p === 1 ? k : k * n; if (b[i] === p) start.push(i); }
    const seen = new Set(start), q = [...start];
    while (q.length) {
      const i = q.shift(), r = Math.floor(i / n), c = i % n;
      if ((p === 1 && r === n - 1) || (p === 2 && c === n - 1)) return true;
      for (const [dr, dc] of NB) { const rr = r + dr, cc = c + dc, j = rr * n + cc;
        if (rr >= 0 && rr < n && cc >= 0 && cc < n && !seen.has(j) && b[j] === p) { seen.add(j); q.push(j); } }
    }
    return false;
  }
  function hexPath(ctx, x, y, rad) { ctx.beginPath(); for (let k = 0; k < 6; k++) { const a = Math.PI / 6 + k * Math.PI / 3; ctx.lineTo(x + rad * Math.cos(a), y + rad * Math.sin(a)); } ctx.closePath(); }
  function draw() {
    const { ctx } = cv;
    ctx.clearRect(0, 0, cv.w, cv.h);
    for (let r = 0; r < n; r++) for (let c = 0; c < n; c++) {
      const [x, y] = centre(r, c), v = b[r * n + c];
      hexPath(ctx, x, y, R * 0.98);
      ctx.fillStyle = v === 1 ? "#e4572e" : v === 2 ? "#29a7d6" : winMarks.includes(r * n + c) ? "rgba(18,165,138,.45)" : "#e6e9f2";
      ctx.fill(); ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 2; ctx.stroke();
    }
    const [x0, y0] = centre(0, 0), [x1] = centre(0, n - 1), [, yb] = centre(n - 1, 0), [xb1] = centre(n - 1, n - 1);
    ctx.lineWidth = 5;
    ctx.strokeStyle = "#e4572e"; ctx.beginPath(); ctx.moveTo(x0 - R * 0.8, y0 - R * 1.2); ctx.lineTo(x1 + R * 0.8, y0 - R * 1.2); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(centre(n - 1, 0)[0] - R * 0.8, yb + R * 1.2); ctx.lineTo(xb1 + R * 0.8, yb + R * 1.2); ctx.stroke();
    ctx.strokeStyle = "#29a7d6"; ctx.beginPath(); ctx.moveTo(x0 - R * 1.3, y0 - R * 0.4); ctx.lineTo(centre(n - 1, 0)[0] - R * 1.3, yb + R * 0.4); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(x1 + R * 1.3, y0 - R * 0.4); ctx.lineTo(xb1 + R * 1.3, yb + R * 0.4); ctx.stroke();
    status.textContent = connected(1) ? "You connected top and bottom — you win!" : connected(2) ? "The engine connected left and right." : thinking ? "Engine thinking…" : "Your move.";
    over = connected(1) || connected(2);
  }
  function reset() {
    n = +size.value; b = Array(n * n).fill(0); over = false; thinking = false; winMarks = [];
    R = Math.min(30, 520 / (n * 2.6));
    cv = Kit.canvas(R * (3.2 + (n - 1) * 1.732 + (n - 1) * 0.866), R * (3.2 + (n - 1) * 1.5));
    stage.innerHTML = ""; stage.appendChild(cv.cv);
    cv.cv.addEventListener("click", click);
    coach.innerHTML = ""; st.innerHTML = "";
    draw();
  }
  async function click(e) {
    if (over || thinking) return;
    const rect = cv.cv.getBoundingClientRect(), px = e.clientX - rect.left, py = e.clientY - rect.top;
    let best = -1, bd = 1e9;
    for (let i = 0; i < n * n; i++) { const [x, y] = centre(Math.floor(i / n), i % n), d = (x - px) ** 2 + (y - py) ** 2; if (d < bd) { bd = d; best = i; } }
    if (bd > R * R || b[best]) return;
    b[best] = 1; winMarks = []; draw();
    if (over) return;
    thinking = true; draw();
    const r = await api("move", { n, board: b, to_move: 2, depth: 3 });
    thinking = false;
    if (r.move !== null && r.move !== undefined) b[r.move] = 2;
    coach.innerHTML = "";
    if (r.proved) coach.appendChild(bubble({ kind: "ok", text: `Engine: ${r.note} (${r.nodes.toLocaleString()} positions).` }));
    stats(st, [["positions", (r.nodes || 0).toLocaleString()], ["time", `${r.ms} ms`]]);
    draw();
  }
  prove.addEventListener("click", busy(prove, async () => {
    const k = Math.min(4, +size.value < 4 ? 3 : 4);
    size.value = k; reset();
    const r = await api("prove", { n: k });
    winMarks = r.winning_first_moves;
    coach.innerHTML = "";
    coach.appendChild(bubble({ kind: "ok", text: `Exhaustive quantified search over ${r.nodes.toLocaleString()} positions (${r.ms} ms): the FIRST player has a forced win on ${k}×${k}. ${r.all ? "Every winning opening is" : "A winning opening is"} shaded green — the classic theorem that Hex is a first-player win, proved for this board.` }));
    draw();
  }, "Proving…"));
  fresh.addEventListener("click", reset);
  size.addEventListener("change", reset);
  reset();
});
})();
