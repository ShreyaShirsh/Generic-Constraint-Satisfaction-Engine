"use strict";
/* Shared toolkit for the problem pages: DOM builder, API, census panel,
   canvas helper, frame player, algorithm race, coach bubble. */
const Kit = (() => {
  const registry = {};
  let META = null;

  const ALGOS = [
    ["naive", "Naive backtracking"], ["fc", "Forward checking"], ["mac", "Arc consistency (MAC)"],
    ["mac_mrv", "MAC + MRV"], ["full", "MAC + MRV + degree + LCV"], ["smart", "MAC + MRV + pigeonhole"],
  ];
  const COLORS = ["#e4572e", "#29a7d6", "#f3c13a", "#5cb85c", "#c792ea", "#ff8fa3", "#4dd0e1",
                  "#ffb74d", "#9ccc65", "#90a4ae", "#f06292", "#7986cb"];

  function register(id, mount) { registry[id] = mount; }

  function start(meta) {
    META = meta;
    const root = document.getElementById("app");
    const mount = registry[meta.id];
    if (!mount) { root.textContent = "This problem has no interactive page yet."; return; }
    try { mount(root, meta); } catch (e) { root.appendChild(errorBox(e.message)); console.error(e); }
  }

  async function api(action, body = {}, pid) {
    const res = await fetch(`/api/p/${pid || META.id}/${action}`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "request failed");
    return data;
  }

  function h(tag, attrs, ...kids) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === undefined || v === null || v === false) continue;
      if (k === "class") el.className = v;
      else if (k === "style" && typeof v === "object") Object.assign(el.style, v);
      else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
      else if (k === "html") el.innerHTML = v;
      else el.setAttribute(k, v === true ? "" : v);
    }
    for (const kid of kids.flat()) {
      if (kid === null || kid === undefined || kid === false) continue;
      el.appendChild(kid instanceof Node ? kid : document.createTextNode(String(kid)));
    }
    return el;
  }

  function esc(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function census(c) {
    const box = document.getElementById("census");
    if (!box || !c) return;
    const rows = c.kinds.map((k) => `<tr><td>${esc(k.name)}<div class="shape">${k.shape}${k.arity ? ` · ${k.arity} vars` : ""}</div></td><td class="n">${k.count.toLocaleString()}</td></tr>`).join("");
    const share = c.not_equal ? `<div><span class="big">${c.not_equal_share}%</span> of them are ≠</div>` : "";
    box.innerHTML = `<h3>This instance compiled into</h3>
      <div><span class="big">${c.variables.toLocaleString()}</span> variable${c.variables === 1 ? "" : "s"} ·
      <span class="big">${c.constraints.toLocaleString()}</span> constraint${c.constraints === 1 ? "" : "s"}</div>${share}
      <table>${rows}</table>
      <p class="muted" style="margin:8px 0 0">Every row is a BinaryRelation or a Predicate — the same abstraction, different predicates.</p>`;
  }

  function stats(el, pairs) {
    el.innerHTML = "";
    el.classList.add("stat-row");
    for (const [k, v] of pairs) {
      if (v === undefined || v === null) continue;
      el.appendChild(h("div", { class: "stat" }, h("div", { class: "k" }, k), h("div", { class: "v" }, String(v))));
    }
    return el;
  }

  function metricPairs(m) {
    if (!m) return [];
    return [["nodes", (m.nodes ?? 0).toLocaleString()], ["backtracks", (m.backtracks ?? 0).toLocaleString()],
            ["pruned", (m.pruned ?? 0).toLocaleString()], ["time", `${m.elapsed_ms} ms`]];
  }

  function errorBox(msg) { return h("div", { class: "err" }, msg); }

  function showError(el, msg) { el.innerHTML = ""; if (msg) el.appendChild(errorBox(msg)); }

  function busy(btn, fn, label = "Working…") {
    return async (...args) => {
      const old = btn.textContent;
      btn.disabled = true;
      btn.textContent = label;
      try { return await fn(...args); }
      finally { btn.disabled = false; btn.textContent = old; }
    };
  }

  function canvas(w, h_) {
    const cv = document.createElement("canvas");
    const dpr = window.devicePixelRatio || 1;
    cv.width = Math.round(w * dpr);
    cv.height = Math.round(h_ * dpr);
    cv.style.width = w + "px";
    cv.style.height = h_ + "px";
    const ctx = cv.getContext("2d");
    ctx.scale(dpr, dpr);
    return { cv, ctx, w, h: h_ };
  }

  function fitSize(container, cols, rows, max = 44, min = 14) {
    const avail = Math.max(260, (container.clientWidth || 640) - 8);
    return Math.max(min, Math.min(max, Math.floor(avail / cols), Math.floor(560 / rows)));
  }

  function algoSelect(def = "smart") {
    const s = h("select", {}, ...ALGOS.map(([k, l]) => h("option", { value: k }, l)));
    s.value = def;
    return s;
  }

  function labeled(text, el) { return h("label", {}, text, el); }

  function bubble(hint) {
    const warn = ["conflict", "mistake", "unsolvable"].includes(hint.kind);
    const lvl = hint.level ? h("span", { class: `lvl lvl-${hint.level}` }, hint.level_name) : null;
    return h("div", { class: "bubble" + (warn ? " warn" : "") }, lvl, hint.text);
  }

  /* A frame player: calls onFrame(i) for i in 0..count-1. */
  function player(count, onFrame, { fps = 4 } = {}) {
    let i = 0, timer = null, rate = fps;
    const label = h("span", {}, "");
    const playBtn = h("button", { class: "btn ghost" }, "▶ Play");
    const update = () => { label.textContent = `step ${i} / ${count - 1}`; onFrame(i); };
    const stop = () => { clearInterval(timer); timer = null; playBtn.textContent = "▶ Play"; };
    const play = () => {
      if (i >= count - 1) i = 0;
      playBtn.textContent = "❚❚ Pause";
      timer = setInterval(() => { if (i >= count - 1) { stop(); return; } i++; update(); }, 1000 / rate);
    };
    playBtn.addEventListener("click", () => (timer ? stop() : play()));
    const speed = h("input", { type: "range", min: 1, max: 30, value: fps });
    speed.addEventListener("input", () => { rate = +speed.value; if (timer) { stop(); play(); } });
    const el = h("div", { class: "player" },
      h("button", { class: "btn ghost", onclick: () => { stop(); i = 0; update(); } }, "⏮"),
      playBtn,
      h("button", { class: "btn ghost", onclick: () => { stop(); i = Math.min(count - 1, i + 1); update(); } }, "Step"),
      h("button", { class: "btn ghost", onclick: () => { stop(); i = count - 1; update(); } }, "End"),
      "speed", speed, label);
    update();
    return { el, play, stop, set: (k) => { i = k; update(); } };
  }

  /* Two copies of the solver race on the same CSP (trace endpoint). The
     problem supplies view = makeView(container, trace) with draw(state). */
  function race(container, { action = "trace", body, makeView, defaults = ["naive", "smart"] }) {
    container.innerHTML = "";
    const lanes = defaults.map((d) => {
      const sel = algoSelect(d);
      const st = h("span", { class: "st" });
      const view = h("div", { class: "stage" });
      const sts = h("div");
      const el = h("div", { class: "lane2" }, h("div", { class: "lh" }, sel, st), view, sts);
      return { sel, st, view, sts, el };
    });
    const speed = h("input", { type: "range", min: 0, max: 100, value: 40 });
    const go = h("button", { class: "btn" }, "Run both");
    const err = h("div");
    container.append(h("div", { class: "toolbar" }, go, h("label", {}, "speed", speed)), err,
                     h("div", { class: "lanes" }, ...lanes.map((l) => l.el)));
    let timer = null;
    const rate = () => Math.max(1, Math.round(Math.pow(10, (+speed.value / 100) * 3.6)));

    go.addEventListener("click", busy(go, async () => {
      clearTimeout(timer);
      showError(err, "");
      let traces;
      try {
        traces = await Promise.all(lanes.map((l) => api(action, { ...body(), algorithm: l.sel.value })));
      } catch (e) { showError(err, e.message); return; }
      lanes.forEach((l, k) => {
        const t = traces[k];
        l.t = t; l.i = 0; l.done = false;
        l.state = { assign: new Map(), dom: new Map(), current: null, bad: null, guesses: 0, backs: 0, crossed: 0 };
        t.vars.forEach((key) => l.state.dom.set(key, new Set(t.initial[key].map((v) => JSON.stringify(v)))));
        l.view.innerHTML = "";
        l.v = makeView(l.view, t);
        l.v.draw(l.state);
        l.st.textContent = ""; l.st.className = "st";
      });
      let last = performance.now(), budget = 0;
      const tick = () => {
        const now = performance.now();
        budget += rate() * Math.min(0.25, (now - last) / 1000);
        last = now;
        const k = Math.floor(budget);
        budget -= k;
        let all = true;
        for (const l of lanes) {
          if (!l.done && k > 0) {
            const ev = l.t.events, end = Math.min(ev.length, l.i + k);
            for (; l.i < end; l.i++) applyEvent(l, ev[l.i]);
            if (l.i >= ev.length) finish(l);
            l.v.draw(l.state);
          }
          stats(l.sts, [["guesses", l.state.guesses], ["backtracks", l.state.backs], ["crossed out", l.state.crossed],
                        ["progress", `${Math.round((l.i / Math.max(1, l.t.events.length)) * 100)}%`]]);
          all = all && l.done;
        }
        if (!all) timer = setTimeout(tick, 16);
      };
      tick();
    }, "Thinking…"));

    function applyEvent(l, [code, idx, value]) {
      const s = l.state, key = l.t.vars[idx];
      const vk = JSON.stringify(value);
      if (code === "a") { s.assign.set(key, value); s.current = key; s.guesses++; s.bad = null; }
      else if (code === "u") { s.assign.delete(key); s.bad = key; s.backs++; }
      else if (code === "p") { s.dom.get(key)?.delete(vk); s.crossed++; }
      else if (code === "r") { s.dom.get(key)?.add(vk); }
      else if (code === "s") { s.solved = true; s.current = null; }
    }
    function finish(l) {
      l.done = true;
      const m = l.t.metrics;
      if (m.solved) { l.st.textContent = `Solved — ${m.nodes.toLocaleString()} guesses`; l.st.className = "st ok"; }
      else { l.st.textContent = l.t.truncated ? "Replay limit reached — still searching" : "No solution"; l.st.className = "st bad"; }
    }
  }

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  /* "You play" / "Engine solves" switch: returns {panes, set(name)} */
  function modes(root, names, onChange) {
    const bar = h("div", { class: "mode-switch" }), panes = {}, btns = {};
    const set = (n) => {
      for (const k of names) { btns[k].classList.toggle("on", k === n); panes[k].style.display = k === n ? "" : "none"; }
      if (onChange) onChange(n);
    };
    for (const n of names) {
      btns[n] = h("button", { onclick: () => set(n) }, n);
      bar.appendChild(btns[n]);
      panes[n] = h("div");
    }
    root.append(bar, ...names.map((n) => panes[n]));
    set(names[0]);
    return { panes, set };
  }

  function banner(el, text, lose = false) {
    el.innerHTML = "";
    if (text) el.appendChild(h("div", { class: "win-banner" + (lose ? " lose" : "") }, text));
  }

  return { register, start, api, h, esc, census, stats, metricPairs, errorBox, showError, busy, canvas,
           fitSize, algoSelect, labeled, bubble, player, race, sleep, modes, banner, COLORS, ALGOS,
           get meta() { return META; } };
})();
