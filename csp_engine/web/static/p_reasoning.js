"use strict";
(() => {
const { h, api, busy, census, stats, metricPairs, showError, bubble, algoSelect, labeled, COLORS } = Kit;

function tabs(root, names) {
  const bar = h("div", { class: "tabs2" });
  const panes = {};
  names.forEach((n, i) => {
    const b = h("button", { class: i === 0 ? "on" : "" }, n);
    const p = h("div", { style: { display: i === 0 ? "" : "none" } });
    b.addEventListener("click", () => {
      bar.querySelectorAll("button").forEach((x) => x.classList.remove("on"));
      b.classList.add("on");
      Object.values(panes).forEach((x) => (x.style.display = "none"));
      p.style.display = "";
    });
    bar.appendChild(b);
    panes[n] = p;
  });
  root.appendChild(bar);
  Object.values(panes).forEach((p) => root.appendChild(p));
  return panes;
}

/* =============================================================== Zebra === */
Kit.register("zebra", (root) => {
  let inst = null;
  const houses = h("select", {}, ...[5, 4, 3].map((n) => h("option", { value: n }, `${n} houses`)));
  const cats = h("select", {}, ...[5, 4, 3].map((n) => h("option", { value: n }, `${n} categories`)));
  const classic = h("button", { class: "btn ghost" }, "Einstein's riddle");
  const fresh = h("button", { class: "btn" }, "Invent a new riddle");
  const err = h("div");
  const clues = h("ol", { class: "list" });
  const question = h("p", { class: "info" });
  root.append(h("div", { class: "toolbar" }, classic, fresh, houses, cats), err);
  const panes = tabs(root, ["Solve it yourself", "Watch two solvers race"]);
  const table = h("div", { class: "stage" });
  const coach = h("div");
  const st = h("div");
  const algo = algoSelect("smart");
  const hintBtn = h("button", { class: "btn green" }, "Hint");
  const checkBtn = h("button", { class: "btn ghost" }, "Check");
  const solveBtn = h("button", { class: "btn ghost" }, "Solve with");
  panes["Solve it yourself"].append(h("div", { class: "row2" },
    h("div", {}, h("h3", {}, "Clues"), clues, question),
    h("div", {}, table, h("div", { class: "toolbar", style: { marginTop: "10px" } }, hintBtn, checkBtn, solveBtn, algo), coach, st)));
  const raceBox = h("div");
  panes["Watch two solvers race"].append(raceBox);

  const label = { nation: "Nationality", colour: "Colour", drink: "Drink", smoke: "Smoke", pet: "Pet" };
  let selects = {};

  function render() {
    clues.innerHTML = "";
    inst.texts.forEach((t) => clues.appendChild(h("li", {}, t)));
    const [qc, qv] = inst.question;
    question.innerHTML = `<strong>Question:</strong> where does ${inst.phrases[qc + "|" + qv]} live — and who is it?`;
    selects = {};
    const n = inst.houses;
    const tbl = h("table", { class: "t" }, h("tr", {}, h("th", {}, ""), ...Array.from({ length: n }, (_, i) => h("th", {}, `House ${i + 1}`))));
    for (const [cat, vals] of Object.entries(inst.categories)) {
      const tr = h("tr", {}, h("th", {}, label[cat] || cat));
      for (let hs = 1; hs <= n; hs++) {
        const s = h("select", {}, h("option", { value: "" }, "?"), ...vals.map((v) => h("option", { value: v }, v)));
        s.addEventListener("change", () => {
          if (s.value) for (let o = 1; o <= n; o++) if (o !== hs && selects[cat][o].value === s.value) selects[cat][o].value = "";
          paint();
        });
        selects[cat] = selects[cat] || {};
        selects[cat][hs] = s;
        tr.appendChild(h("td", {}, s));
      }
      tbl.appendChild(tr);
    }
    table.innerHTML = "";
    table.appendChild(tbl);
    coach.innerHTML = ""; st.innerHTML = "";
    raceBox.innerHTML = "";
    Kit.race(raceBox, { body: () => ({ inst }), makeView: zebraView, defaults: ["naive", "smart"] });
  }

  function paint(marks = {}) {
    for (const cat in selects) for (const hs in selects[cat]) {
      const s = selects[cat][hs];
      s.style.outline = marks[`${cat}|${s.value}`] || "";
    }
  }

  function entries() {
    const out = [];
    for (const cat in selects) for (const hs in selects[cat]) if (selects[cat][hs].value) out.push([cat, selects[cat][hs].value, +hs]);
    return out;
  }

  function zebraView(el, t) {
    const n = inst.houses;
    return {
      draw(state) {
        const grid = {};
        for (const [k, house] of state.assign) { const [c, v] = k.split("|"); grid[c + "@" + house] = v; }
        const rows = Object.keys(inst.categories).map((c) => `<tr><th>${label[c] || c}</th>${Array.from({ length: n }, (_, i) => {
          const v = grid[c + "@" + (i + 1)] || "";
          const cur = state.current && state.current.startsWith(c + "|") && state.assign.get(state.current) === i + 1;
          return `<td style="min-width:62px;${cur ? "background:rgba(250,190,40,.25)" : ""}${state.solved ? ";color:var(--accent-2)" : ""}">${Kit.esc(v)}</td>`;
        }).join("")}</tr>`).join("");
        el.innerHTML = `<table class="t"><tr><th></th>${Array.from({ length: n }, (_, i) => `<th>${i + 1}</th>`).join("")}</tr>${rows}</table>`;
      },
    };
  }

  async function load(body) {
    showError(err, "");
    try {
      const r = await api("new", body);
      inst = r.inst;
      census(r.census);
      render();
    } catch (e) { showError(err, e.message); }
  }

  classic.addEventListener("click", busy(classic, () => load({ mode: "classic" })));
  fresh.addEventListener("click", busy(fresh, () => load({ houses: +houses.value, categories: +cats.value }), "Inventing…"));
  hintBtn.addEventListener("click", busy(hintBtn, async () => {
    const hint = await api("hint", { inst, entries: entries() });
    coach.innerHTML = "";
    coach.appendChild(bubble(hint));
    const marks = {};
    (hint.highlight || []).forEach((k) => (marks[k] = "2px solid var(--warn)"));
    if (hint.var) {
      const [c, v] = hint.var.split("|");
      const s = selects[c][hint.value];
      coach.appendChild(h("button", { class: "btn ghost", onclick: () => { s.value = v; s.dispatchEvent(new Event("change")); } }, "Fill it in"));
      marks[hint.var] = "2px solid var(--accent-2)";
    }
    paint(marks);
  }));
  checkBtn.addEventListener("click", busy(checkBtn, async () => {
    const r = await api("check", { inst, entries: entries() });
    coach.innerHTML = "";
    if (r.conflicts.length) coach.appendChild(bubble({ kind: "conflict", text: `Broken: ${r.conflicts.map((c) => c.label).join("; ")}` }));
    else coach.appendChild(bubble({ kind: "ok", text: r.solved ? "Solved — every clue holds." : "Nothing contradicts the clues so far." }));
  }));
  solveBtn.addEventListener("click", busy(solveBtn, async () => {
    const r = await api("solve", { inst, algorithm: algo.value });
    if (!r.solution) { coach.innerHTML = ""; coach.appendChild(bubble({ kind: "mistake", text: "No solution." })); return; }
    for (const [k, house] of Object.entries(r.solution)) { const [c, v] = k.split("|"); selects[c][house].value = v; }
    const [qc, qv] = inst.question;
    const hq = r.solution[qc + "|" + qv];
    const who = Object.entries(r.solution).find(([k, hs]) => k.startsWith("nation|") && hs === hq);
    coach.innerHTML = "";
    coach.appendChild(bubble({ kind: "ok", text: `Answer: ${inst.phrases[qc + "|" + qv]} lives in house ${hq}${who ? ` — the ${who[0].split("|")[1]}.` : "."}` }));
    stats(st, metricPairs(r.metrics));
    census(r.census);
  }));
  load({ mode: "classic" });
});

/* ===================================================== Cryptarithmetic === */
Kit.register("crypto", (root) => {
  let inst = null, classics = [];
  const pick = h("select");
  const loadBtn = h("button", { class: "btn ghost" }, "Load");
  const invent = h("button", { class: "btn" }, "Invent a new one");
  const custom = h("input", { type: "text", placeholder: "e.g. TO + GO = OUT", style: { width: "180px" } });
  const useBtn = h("button", { class: "btn ghost" }, "Use mine");
  const err = h("div");
  root.append(h("div", { class: "toolbar" }, pick, loadBtn, invent, custom, useBtn), err);
  const panes = tabs(root, ["Solve it yourself", "Watch two solvers race"]);
  const eq = h("div", { class: "stage" });
  const letters = h("div", { class: "stat-row" });
  const coach = h("div"), st = h("div");
  const algo = algoSelect("full");
  const hintBtn = h("button", { class: "btn green" }, "Hint");
  const solveBtn = h("button", { class: "btn ghost" }, "Solve with");
  panes["Solve it yourself"].append(eq, h("p", { class: "info" }, "Give every letter a different digit so the sum works. Revealed letters are fixed clues."),
    letters, h("div", { class: "toolbar" }, hintBtn, solveBtn, algo), coach, st);
  const raceBox = h("div");
  panes["Watch two solvers race"].append(raceBox);
  let sel = {};

  function drawEq(values = {}) {
    const words = [...inst.addends, inst.result];
    const width = Math.max(...words.map((w) => w.length)) + 1;
    const line = (w, prefix) => {
      const pad = " ".repeat(width - w.length);
      const top = prefix + pad + w;
      const bot = " " + pad + [...w].map((L) => (values[L] ?? "·")).join("");
      return `<div>${top.replace(/ /g, "&nbsp;")}</div><div style="color:var(--accent-2)">${bot.replace(/ /g, "&nbsp;")}</div>`;
    };
    let html = "";
    inst.addends.forEach((w, i) => (html += line(w, i === inst.addends.length - 1 ? "+" : " ")));
    html += `<div style="border-top:2px solid var(--muted);width:${(width + 1) * 0.62}em"></div>` + line(inst.result, " ");
    eq.innerHTML = `<div class="mono" style="font-size:1.6rem;line-height:1.25">${html}</div>`;
  }

  function current() {
    const out = {};
    for (const [L, s] of Object.entries(sel)) if (s.value !== "") out[L] = +s.value;
    return out;
  }

  function render() {
    const ls = [...new Set([...inst.addends.join(""), ...inst.result])].sort();
    letters.innerHTML = "";
    sel = {};
    for (const L of ls) {
      const s = h("select", {}, h("option", { value: "" }, "?"), ...Array.from({ length: 10 }, (_, d) => h("option", { value: d }, d)));
      if (inst.givens && L in inst.givens) { s.value = inst.givens[L]; s.disabled = true; }
      s.addEventListener("change", () => drawEq(current()));
      sel[L] = s;
      letters.appendChild(h("div", { class: "stat" }, h("div", { class: "k" }, L), s));
    }
    drawEq(current());
    coach.innerHTML = ""; st.innerHTML = "";
    Kit.race(raceBox, {
      body: () => ({ inst }), defaults: ["fc", "full"],
      makeView: (el) => ({ draw(s) {
        const vals = {};
        for (const [k, v] of s.assign) if (!k.startsWith("carry")) vals[k] = v;
        el.innerHTML = `<div class="mono" style="font-size:1.05rem">${[...inst.addends, inst.result].map((w) => `${w} = ${[...w].map((L) => vals[L] ?? "·").join("")}`).join("<br>")}</div>`;
      } }),
    });
  }

  async function load(body) {
    showError(err, "");
    try {
      const r = await api("new", body);
      inst = r.inst;
      if (!classics.length) { classics = r.classics; pick.innerHTML = classics.map((c, i) => `<option value="${i}">${c}</option>`).join(""); }
      census(r.census);
      render();
    } catch (e) { showError(err, e.message); }
  }

  loadBtn.addEventListener("click", busy(loadBtn, () => load({ mode: "classic", index: +pick.value })));
  invent.addEventListener("click", busy(invent, () => load({ mode: "generate" }), "Inventing…"));
  useBtn.addEventListener("click", busy(useBtn, () => load({ mode: "custom", words: custom.value })));
  hintBtn.addEventListener("click", busy(hintBtn, async () => {
    const entries = Object.entries(current()).filter(([L]) => !(inst.givens && L in inst.givens));
    const hint = await api("hint", { inst, entries });
    coach.innerHTML = "";
    coach.appendChild(bubble(hint));
    if (hint.var && sel[hint.var]) coach.appendChild(h("button", { class: "btn ghost", onclick: () => { sel[hint.var].value = hint.value; drawEq(current()); } }, "Fill it in"));
  }));
  solveBtn.addEventListener("click", busy(solveBtn, async () => {
    const r = await api("solve", { inst, algorithm: algo.value });
    if (!r.solution) { coach.innerHTML = ""; coach.appendChild(bubble({ kind: "mistake", text: "This puzzle has no solution." })); return; }
    for (const [L, s] of Object.entries(sel)) s.value = r.solution[L];
    drawEq(current());
    const carries = Object.entries(r.solution).filter(([k]) => k.startsWith("carry")).map(([k, v]) => `column ${k.slice(5)}: ${v}`).join(", ");
    coach.innerHTML = "";
    coach.appendChild(bubble({ kind: "ok", text: `Solved. Hidden carries — ${carries}.` }));
    stats(st, metricPairs(r.metrics));
    census(r.census);
  }));
  load({ mode: "classic", index: 0 });
});

/* ================================================= Knights and Knaves === */
Kit.register("knights", (root) => {
  let inst = null;
  const n = h("select", {}, ...[3, 4, 5, 2, 6].map((k) => h("option", { value: k }, `${k} islanders`)));
  const classic = h("button", { class: "btn ghost" }, "Classic two-person puzzle");
  const fresh = h("button", { class: "btn" }, "New puzzle");
  const err = h("div"), says = h("div"), people = h("div", { class: "stat-row" }), coach = h("div"), st = h("div");
  const hintBtn = h("button", { class: "btn green" }, "Hint");
  const checkBtn = h("button", { class: "btn ghost" }, "Check");
  const solveBtn = h("button", { class: "btn ghost" }, "Solve");
  root.append(h("div", { class: "toolbar" }, classic, fresh, n), err,
    h("p", { class: "info" }, "Knights always tell the truth. Knaves always lie. Decide who is who."),
    says, people, h("div", { class: "toolbar" }, hintBtn, checkBtn, solveBtn), coach, st);
  let choice = {};

  function render() {
    says.innerHTML = "";
    inst.texts.forEach(([p, t]) => says.appendChild(h("div", { class: "speech" }, h("b", {}, p), ` says: “${t}”`)));
    people.innerHTML = "";
    choice = {};
    for (const p of inst.people) {
      const group = h("div", {});
      const card = h("div", { class: "stat" }, h("div", { class: "k" }, p), group);
      ["knight", "knave", "?"].forEach((k) => {
        const b = h("button", { class: "btn ghost", style: { padding: "4px 9px", margin: "2px" } }, k);
        b.addEventListener("click", () => { choice[p] = k === "?" ? undefined : k; paint(); });
        group.appendChild(b);
      });
      card.dataset.p = p;
      people.appendChild(card);
    }
    coach.innerHTML = ""; st.innerHTML = "";
    paint();
  }

  function paint(marks = {}) {
    people.querySelectorAll(".stat").forEach((card) => {
      const p = card.dataset.p;
      card.querySelectorAll("button").forEach((b) => {
        const on = (choice[p] || "?") === b.textContent;
        b.style.background = on ? "var(--accent)" : "";
        b.style.color = on ? "#0b1020" : "";
      });
      card.style.outline = marks[p] || "";
    });
  }

  const entries = () => Object.entries(choice).filter(([, v]) => v);

  async function load(body) {
    showError(err, "");
    try { const r = await api("new", body); inst = r.inst; census(r.census); render(); }
    catch (e) { showError(err, e.message); }
  }
  classic.addEventListener("click", busy(classic, () => load({ mode: "classic" })));
  fresh.addEventListener("click", busy(fresh, () => load({ people: +n.value }), "Inventing…"));
  hintBtn.addEventListener("click", busy(hintBtn, async () => {
    const hint = await api("hint", { inst, entries: entries() });
    coach.innerHTML = "";
    coach.appendChild(bubble(hint));
    const marks = {};
    (hint.highlight || []).forEach((p) => (marks[p] = "2px solid var(--warn)"));
    if (hint.var) {
      marks[hint.var] = "2px solid var(--accent-2)";
      coach.appendChild(h("button", { class: "btn ghost", onclick: () => { choice[hint.var] = hint.value; paint(); } }, "Fill it in"));
    }
    paint(marks);
  }));
  checkBtn.addEventListener("click", busy(checkBtn, async () => {
    const r = await api("check", { inst, entries: entries() });
    coach.innerHTML = "";
    coach.appendChild(r.conflicts.length ? bubble({ kind: "conflict", text: `That breaks ${r.conflicts[0].label}.` })
      : bubble({ kind: "ok", text: r.solved ? "Correct — every statement fits." : "Consistent so far." }));
  }));
  solveBtn.addEventListener("click", busy(solveBtn, async () => {
    const r = await api("solve", { inst, algorithm: "smart" });
    choice = { ...r.solution };
    paint();
    stats(st, metricPairs(r.metrics));
    census(r.census);
  }));
  load({ people: 3 });
});

/* ========================================================= Minesweeper === */
Kit.register("minesweeper", (root) => {
  const LEVELS = { beginner: [9, 9, 10], intermediate: [16, 16, 40], expert: [16, 30, 99] };
  const level = h("select", {}, ...Object.keys(LEVELS).map((k) => h("option", { value: k }, k)));
  const fresh = h("button", { class: "btn" }, "New game");
  const show = h("input", { type: "checkbox" });
  const hintBtn = h("button", { class: "btn green" }, "Ask the assistant");
  const auto = h("button", { class: "btn ghost" }, "Let the AI play a game");
  const status = h("div", { class: "stat-row" }), coach = h("div"), stage = h("div", { class: "stage" });
  root.append(h("div", { class: "toolbar" }, level, fresh, h("label", { style: { flexDirection: "row", alignItems: "center", gap: "6px" } }, show, "show what the AI knows"), hintBtn, auto),
    h("p", { class: "info" }, "Left-click reveals, right-click flags. The assistant reasons with one constraint per number: “exactly N mines around me”."),
    status, stage, coach);

  let G = null, overlay = null, cv = null, cs = 28;
  const key = (r, c) => `${r},${c}`;

  function newGame() {
    const [rows, cols, mines] = LEVELS[level.value];
    G = { rows, cols, total: mines, mines: null, revealed: new Map(), flags: new Set(), over: null, playing: true };
    overlay = null;
    coach.innerHTML = "";
    cs = Kit.fitSize(stage, cols, rows, 34, 18);
    const c = Kit.canvas(cols * cs, rows * cs);
    cv = c;
    stage.innerHTML = "";
    stage.appendChild(c.cv);
    c.cv.addEventListener("click", (e) => clickAt(e, false));
    c.cv.addEventListener("contextmenu", (e) => { e.preventDefault(); clickAt(e, true); });
    draw();
  }

  function nb(r, c) {
    const out = [];
    for (let dr = -1; dr <= 1; dr++) for (let dc = -1; dc <= 1; dc++) {
      const rr = r + dr, cc = c + dc;
      if ((dr || dc) && rr >= 0 && rr < G.rows && cc >= 0 && cc < G.cols) out.push([rr, cc]);
    }
    return out;
  }

  function reveal(r, c) {
    if (G.mines.has(key(r, c))) { G.over = "lost"; G.boom = key(r, c); return; }
    const stack = [[r, c]];
    while (stack.length) {
      const [a, b] = stack.pop();
      if (G.revealed.has(key(a, b))) continue;
      const n = nb(a, b).filter(([x, y]) => G.mines.has(key(x, y))).length;
      G.revealed.set(key(a, b), n);
      G.flags.delete(key(a, b));
      if (n === 0) stack.push(...nb(a, b));
    }
    if (G.revealed.size === G.rows * G.cols - G.total) G.over = "won";
  }

  async function clickAt(e, flag) {
    if (!G || G.over) return;
    const rect = cv.cv.getBoundingClientRect();
    const c = Math.floor((e.clientX - rect.left) / cs), r = Math.floor((e.clientY - rect.top) / cs);
    if (r < 0 || c < 0 || r >= G.rows || c >= G.cols || G.revealed.has(key(r, c))) return;
    if (flag) { G.flags.has(key(r, c)) ? G.flags.delete(key(r, c)) : G.flags.add(key(r, c)); draw(); return; }
    if (G.flags.has(key(r, c))) return;
    if (!G.mines) {
      const res = await api("new", { rows: G.rows, cols: G.cols, mines: G.total, first: [r, c] });
      G.mines = new Set(res.mines.map(([a, b]) => key(a, b)));
    }
    reveal(r, c);
    await refresh();
  }

  async function refresh() {
    overlay = null;
    if (show.checked && G.mines && !G.over) overlay = await assist();
    draw();
  }

  async function assist() {
    const revealed = [...G.revealed].map(([k, n]) => [...k.split(",").map(Number), n]);
    const r = await api("assist", { rows: G.rows, cols: G.cols, mines: G.total, revealed, flags: [...G.flags].map((k) => k.split(",").map(Number)) });
    census(r.census);
    return r;
  }

  function draw() {
    const { ctx } = cv;
    ctx.clearRect(0, 0, cv.w, cv.h);
    ctx.font = `bold ${cs * 0.55}px monospace`;
    ctx.textAlign = "center"; ctx.textBaseline = "middle";
    const numColor = ["", "#5b6cff", "#12a58a", "#e5484d", "#c792ea", "#f08c2b", "#4dd0e1", "#2a2d3a", "#7a7f90"];
    for (let r = 0; r < G.rows; r++) for (let c = 0; c < G.cols; c++) {
      const k = key(r, c), x = c * cs, y = r * cs;
      const open = G.revealed.has(k);
      ctx.fillStyle = open ? "#f2efe7" : "#d9dee9";
      ctx.fillRect(x + 1, y + 1, cs - 2, cs - 2);
      if (open) {
        const n = G.revealed.get(k);
        if (n) { ctx.fillStyle = numColor[n]; ctx.fillText(n, x + cs / 2, y + cs / 2 + 1); }
      } else if (G.over && G.mines && G.mines.has(k)) {
        ctx.fillStyle = k === G.boom ? "#e5484d" : "#2a2d3a";
        ctx.beginPath(); ctx.arc(x + cs / 2, y + cs / 2, cs * 0.22, 0, 7); ctx.fill();
      } else if (G.flags.has(k)) {
        ctx.fillStyle = "#e5484d";
        ctx.beginPath(); ctx.moveTo(x + cs * 0.35, y + cs * 0.2); ctx.lineTo(x + cs * 0.72, y + cs * 0.35); ctx.lineTo(x + cs * 0.35, y + cs * 0.5); ctx.fill();
        ctx.fillRect(x + cs * 0.33, y + cs * 0.2, 2, cs * 0.6);
      } else if (overlay && overlay.probabilities && k in overlay.probabilities) {
        const p = overlay.probabilities[k];
        ctx.fillStyle = p < 1e-9 ? "rgba(18,165,138,.55)" : p > 1 - 1e-9 ? "rgba(229,72,77,.6)" : `rgba(240,140,43,${0.15 + p * 0.6})`;
        ctx.fillRect(x + 1, y + 1, cs - 2, cs - 2);
        if (cs >= 24 && p > 1e-9 && p < 1 - 1e-9) { ctx.fillStyle = "#2a2d3a"; ctx.font = `${cs * 0.3}px monospace`; ctx.fillText(Math.round(p * 100) + "%", x + cs / 2, y + cs / 2); ctx.font = `bold ${cs * 0.55}px monospace`; }
      }
      if (overlay && overlay.cell && overlay.cell[0] === r && overlay.cell[1] === c) {
        ctx.strokeStyle = overlay.mine ? "#e5484d" : "#12a58a"; ctx.lineWidth = 3; ctx.strokeRect(x + 2, y + 2, cs - 4, cs - 4);
      }
    }
    stats(status, [["mines", G.total], ["flags", G.flags.size], ["revealed", G.revealed.size],
      ["status", G.over === "won" ? "won!" : G.over === "lost" ? "boom" : G.mines ? "playing" : "click to start"]]);
  }

  hintBtn.addEventListener("click", busy(hintBtn, async () => {
    if (!G.mines || G.over) return;
    overlay = await assist();
    coach.innerHTML = "";
    coach.appendChild(bubble({ kind: overlay.kind === "guess" ? "warn" : "ok", text: overlay.text }));
    if (overlay.cell) coach.appendChild(h("button", { class: "btn ghost", onclick: async () => {
      const [r, c] = overlay.cell;
      if (overlay.mine) G.flags.add(key(r, c)); else reveal(r, c);
      coach.innerHTML = "";
      await refresh();
    } }, overlay.mine ? "Flag it" : "Reveal it"));
    draw();
  }));
  show.addEventListener("change", refresh);
  fresh.addEventListener("click", newGame);
  level.addEventListener("change", newGame);
  auto.addEventListener("click", busy(auto, async () => {
    const game = await api("autoplay", { rows: G.rows, cols: G.cols, mines: G.total });
    newGame();
    G.mines = new Set(game.mines.map(([a, b]) => key(a, b)));
    for (const mv of game.moves) {
      const [r, c] = mv.cell;
      if (mv.kind === "flag") G.flags.add(key(r, c)); else reveal(r, c);
      coach.innerHTML = "";
      if (mv.reason) coach.appendChild(bubble({ kind: mv.kind === "guess" ? "warn" : "ok", text: (mv.kind === "guess" ? "Guess: " : "") + mv.reason }));
      draw();
      await Kit.sleep(mv.kind === "guess" ? 900 : 160);
      if (G.over) break;
    }
    coach.appendChild(bubble({ kind: game.won ? "ok" : "warn", text: game.won ? "The AI cleared the board." : "The AI hit a mine on a forced guess — even perfect reasoning can't avoid every 50/50." }));
  }, "Playing…"));
  newGame();
});

/* =========================================== Sudoku → Puzzle Studio === */
Kit.register("sudoku", (root) => {
  root.append(h("p", {}, "Sudoku and its whole family live in the Puzzle Studio."),
    h("a", { class: "btn", href: "/studio", style: { textDecoration: "none", display: "inline-block" } }, "Open the Puzzle Studio →"));
});
})();
