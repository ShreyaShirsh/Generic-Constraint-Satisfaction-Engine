"""HTTP plumbing for the problem gallery: /api/p/<problem>/<action>.

Shared helpers do the CSP work every page needs -- solve with a chosen
algorithm, record a replayable trace, give a justified hint, list broken
constraints, take a constraint census -- so each problem only has to say how
to build its CSP and how to describe the answer.
"""
from __future__ import annotations
import math
import random
from flask import Blueprint, jsonify, request

from ..core.backtracking import backtracking_search, SearchAborted
from ..core.census import census
from ..core.explain import Reasoner, LEVEL_NAMES
from ..core.planning import plan_csp, solve_plan
from ..core.adversarial import best_move, prove_win, winning_moves
from ..core.inference import mac_plus
from ..core.heuristics import mrv
from .studio import ALGORITHMS
from .catalog import P, CATEGORIES, BY_ID
from ..problems import logic_puzzles as LP
from ..problems import cryptarithmetic as CR
from ..problems import minesweeper as MS
from ..problems import search_puzzles as SP
from ..problems import games as G
from ..problems import graph_problems as GP
from ..problems import planning_problems as PP
from ..problems import spatial as SPA
from ..problems.graph_colouring import graph_colouring_csp, AUSTRALIA
from ..problems.exam_scheduling import conflict_graph, exam_scheduling_csp
from ..contrast.q_learning import q_learning

bp = Blueprint("problems", __name__, url_prefix="/api/p")
HANDLERS: dict = {}


class Bad(ValueError):
    pass


@bp.errorhandler(ValueError)
def _bad(e):
    return jsonify({"error": str(e)}), 400


def handler(pid, action):
    def deco(fn):
        HANDLERS[(pid, action)] = fn
        return fn
    return deco


@bp.route("/catalog")
def catalog():
    return jsonify({"categories": [{"id": c, "name": n, "blurb": b} for c, n, b in CATEGORIES],
                    "problems": P})


@bp.route("/<pid>/<action>", methods=["POST"])
def dispatch(pid, action):
    fn = HANDLERS.get((pid, action))
    if fn is None:
        return jsonify({"error": f"unknown action {pid}/{action}"}), 404
    return jsonify(fn(request.get_json(force=True) or {}))


# ============================================================ shared helpers ====

def J(x):
    """Make anything JSON-able (tuples -> lists, sets -> sorted lists)."""
    if isinstance(x, dict):
        return {(k if isinstance(k, str) else key_of(k)): J(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [J(v) for v in x]
    if isinstance(x, (set, frozenset)):
        return sorted(J(v) for v in x)
    if isinstance(x, float) and (math.isinf(x) or math.isnan(x)):
        return None
    return x


def key_of(v) -> str:
    return "|".join(str(x) for x in v) if isinstance(v, tuple) else str(v)


def num(body, name, default, lo, hi):
    try:
        v = int(body.get(name, default))
    except (TypeError, ValueError):
        raise Bad(f"{name} must be a whole number")
    if not lo <= v <= hi:
        raise Bad(f"{name} must be between {lo} and {hi}")
    return v


def rng_of(body):
    seed = body.get("seed")
    return random.Random(seed if seed not in (None, "") else None)


def metrics_dict(m) -> dict:
    return {"solved": m.solved, "timed_out": m.timed_out, "nodes": m.nodes,
            "backtracks": m.backtracks, "pruned": m.pruned, "elapsed_ms": round(m.elapsed * 1000, 2)}


def algo(body):
    key = body.get("algorithm") or "smart"
    if key not in ALGORITHMS:
        raise Bad(f"unknown algorithm '{key}'")
    return ALGORITHMS[key]


def solve_csp(csp, body, max_nodes=200_000):
    label, sv, ov, inf = algo(body)
    sol, m = backtracking_search(csp, select_var=sv, order_values=ov, inference=inf, max_nodes=max_nodes)
    md = metrics_dict(m)
    md["algorithm"] = label
    return sol, md


def trace_csp(csp, body, limit=30_000) -> dict:
    label, sv, ov, inf = algo(body)
    index = {v: i for i, v in enumerate(csp.variables)}
    initial = {key_of(v): J(sorted(csp.domains[v], key=str)) for v in csp.variables}
    codes = {"assign": "a", "prune": "p", "restore": "r", "unassign": "u", "solution": "s"}
    events = []

    def tracer(e, var, value):
        if len(events) >= limit:
            raise SearchAborted()
        events.append([codes[e], index.get(var, -1), J(value)])

    sol, m = backtracking_search(csp, select_var=sv, order_values=ov, inference=inf,
                                 tracer=tracer, max_nodes=200_000)
    md = metrics_dict(m)
    md["algorithm"] = label
    return {"vars": [key_of(v) for v in csp.variables], "initial": initial, "events": events,
            "truncated": m.timed_out, "metrics": md}


def violations(csp, assignment) -> list:
    out, seen = [], set()
    for c in csp.constraints:
        if not c.is_satisfied(assignment):
            vs = [key_of(v) for v in c.variables if v in assignment]
            k = (c.label, tuple(vs))
            if k not in seen:
                seen.add(k)
                out.append({"vars": vs, "label": getattr(c, "label", None) or c.name})
    return out


def hint_csp(csp, assignment, name_of, fmt_value=str, value_of=None, hidden_fmt=None) -> dict:
    bad = violations(csp, assignment)
    if bad:
        return {"kind": "conflict", "highlight": bad[0]["vars"],
                "text": f"Something already breaks {bad[0]['label']} — fix the highlighted entries first."}
    trial = type(csp)(csp.variables, {v: ([assignment[v]] if v in assignment else csp.domains[v].values)
                                      for v in csp.variables}, csp.constraints, groups=csp.groups)
    sol, _ = backtracking_search(trial, select_var=mrv, inference=mac_plus, max_nodes=200_000)
    if sol is None:
        return {"kind": "mistake", "highlight": [key_of(v) for v in assignment],
                "text": "Nothing clashes yet, but these entries can't all be part of a solution — "
                        "one of them leads to a dead end."}
    step = Reasoner(csp, assignment, name_of, value_of, hidden_fmt).next_step(3)
    if step and step.kind != "contradiction":
        return {"kind": step.kind, "var": key_of(step.var), "value": J(step.value), "level": step.level,
                "level_name": LEVEL_NAMES[step.level], "text": step.text,
                "highlight": [key_of(v) for v in step.highlight]}
    open_vars = [v for v in csp.variables if v not in assignment]
    if not open_vars:
        return {"kind": "done", "text": "Everything is filled in and every constraint holds."}
    v = open_vars[0]
    return {"kind": "reveal", "var": key_of(v), "value": J(sol[v]), "level": 4,
            "level_name": LEVEL_NAMES[4], "highlight": [],
            "text": f"No logical step exists from here — the engine itself would have to guess. "
                    f"Its search says {name_of(v)} is {fmt_value(sol[v])}."}


def csp_actions(pid, build, name_of=str, fmt_value=str, decode=None, value_of=None, hidden_fmt=None):
    """Register solve / trace / hint / check for a CSP-shaped problem.
    build(inst) -> CSP; decode(inst, entries) -> {var: value}."""
    decode = decode or (lambda inst, entries: {})

    @handler(pid, "solve")
    def _solve(b):
        csp = build(b["inst"])
        sol, md = solve_csp(csp, b)
        return {"solution": J({key_of(k): v for k, v in sol.items()}) if sol else None,
                "metrics": md, "census": census(build(b["inst"]))}

    @handler(pid, "trace")
    def _trace(b):
        return trace_csp(build(b["inst"]), b)

    @handler(pid, "hint")
    def _hint(b):
        csp = build(b["inst"])
        return hint_csp(csp, decode(b["inst"], b.get("entries", [])), name_of, fmt_value,
                        value_of, hidden_fmt)

    @handler(pid, "check")
    def _check(b):
        csp = build(b["inst"])
        a = decode(b["inst"], b.get("entries", []))
        bad = violations(csp, a)
        return {"conflicts": bad, "complete": len(a) == len(csp.variables),
                "solved": len(a) == len(csp.variables) and not bad}


def census_opt(csp) -> dict:
    """Census of an optimisation CSP including the branch-and-bound predicate
    that core/optimize.py adds while it searches."""
    c = census(csp)
    c["kinds"].append({"shape": "Predicate", "name": "Bound", "count": 1, "arity": c["variables"],
                       "example": "better than the best solution found so far"})
    c["constraints"] += 1
    c["not_equal_share"] = round(100 * c["not_equal"] / c["constraints"], 1)
    return c


def plan_answer(problem, result, extra=None):
    out = {"plan": J(result["plan"]), "states": J(result["states"]), "cost": result["cost"],
           "iterations": result["iterations"], "metrics": metrics_dict(result["metrics"])}
    if result["plan"] is not None:
        T = max(1, len(result["plan"]))
        csp, _ = plan_csp(problem, T, T)
        out["census"] = census(csp)
    out.update(extra or {})
    return out


# =============================================================== reasoning ====

def _zebra_build(inst):
    return LP.zebra_from_instance(inst)


def _zebra_decode(inst, entries):
    return {(cat, val): int(h) for cat, val, h in entries}


csp_actions("zebra", _zebra_build, LP.zebra_name, lambda h: f"in house {h}", _zebra_decode,
            LP.zebra_value, LP.ZEBRA_HIDDEN)


@handler("zebra", "new")
def zebra_new(b):
    if b.get("mode") == "classic":
        inst = LP.classic_zebra()
    else:
        houses = num(b, "houses", 5, 3, 5)
        cats = num(b, "categories", 5, 3, 5)
        inst = LP.generate_zebra(houses, cats, b.get("seed"))
    inst["texts"] = [LP.clue_text(c, inst["houses"]) for c in inst["clues"]]
    inst["phrases"] = {key_of((c, v)): LP.phrase(c, v) for c, vals in inst["categories"].items() for v in vals}
    return {"inst": inst, "census": census(_zebra_build(inst))}


def _crypt_build(inst):
    return CR.crypt_csp(inst["addends"], inst["result"], inst.get("givens") or {})


csp_actions("crypto", _crypt_build, CR.crypt_name, str,
            lambda inst, entries: {L: int(d) for L, d in entries})


@handler("crypto", "new")
def crypto_new(b):
    mode = b.get("mode", "classic")
    if mode == "classic":
        i = num(b, "index", 0, 0, len(CR.CLASSICS) - 1)
        adds, res = CR.CLASSICS[i]
        inst = {"addends": adds, "result": res, "givens": {}}
    elif mode == "generate":
        inst = CR.generate_crypt(b.get("seed"))
        if inst is None:
            raise Bad("couldn't invent a puzzle in time — try again")
    else:
        words = [w.strip().upper() for w in str(b.get("words", "")).replace("=", "+").split("+") if w.strip()]
        if len(words) < 3:
            raise Bad("write it like SEND + MORE = MONEY")
        inst = {"addends": words[:-1], "result": words[-1], "givens": {}}
    csp = _crypt_build(inst)
    return {"inst": inst, "classics": [" + ".join(a) + " = " + r for a, r in CR.CLASSICS],
            "census": census(csp)}


def _knights_build(inst):
    return LP.knights_csp(inst["people"], inst["statements"])


csp_actions("knights", _knights_build, str, str, lambda inst, entries: {p: k for p, k in entries})


@handler("knights", "new")
def knights_new(b):
    if b.get("mode") == "classic":
        inst = dict(LP.CLASSIC_KNIGHTS)
    else:
        inst = LP.generate_knights(num(b, "people", 3, 2, 6), b.get("seed"))
    inst["texts"] = [[s, LP.statement_text(st, s)] for s, st in inst["statements"]]
    return {"inst": inst, "census": census(_knights_build(inst))}


@handler("minesweeper", "new")
def mines_new(b):
    rows, cols = num(b, "rows", 9, 5, 20), num(b, "cols", 9, 5, 30)
    mines = num(b, "mines", 10, 1, rows * cols - 10)
    first = tuple(b.get("first") or (rows // 2, cols // 2))
    return {"mines": [list(m) for m in MS.new_board(rows, cols, mines, first, rng_of(b))]}


@handler("minesweeper", "assist")
def mines_assist(b):
    rows, cols = num(b, "rows", 9, 5, 20), num(b, "cols", 9, 5, 30)
    total = num(b, "mines", 10, 1, rows * cols)
    revealed = {(r, c): n for r, c, n in b.get("revealed", [])}
    flags = [tuple(f) for f in b.get("flags", [])]
    advice = MS.next_move(revealed, rows, cols, total, flags)
    if "probabilities" not in advice:
        a = MS.analyse(revealed, rows, cols, total)
        if a.get("probabilities"):
            advice["probabilities"] = MS._jsonp(a["probabilities"])
    csp = MS.mines_csp(revealed, rows, cols)
    advice["census"] = census(csp)
    return advice


@handler("minesweeper", "autoplay")
def mines_autoplay(b):
    rows, cols = num(b, "rows", 9, 5, 20), num(b, "cols", 9, 5, 30)
    mines = num(b, "mines", 10, 1, rows * cols - 10)
    return MS.autoplay(rows, cols, mines, b.get("seed"))


# ================================================================== search ====

@handler("maze", "new")
def maze_new(b):
    rows, cols = num(b, "rows", 15, 5, 41), num(b, "cols", 21, 5, 61)
    grid, s, g = SP.generate_maze(rows, cols, rng_of(b), loops=float(b.get("loops", 0.06)))
    return {"grid": grid, "start": list(s), "goal": list(g)}


@handler("maze", "solve")
def maze_solve(b):
    p = SP.Maze(b["grid"], b["start"], b["goal"])
    return plan_answer(p, solve_plan(p, max_steps=len(b["grid"]) * len(b["grid"][0])))


@handler("eight", "new")
def eight_new(b):
    size = num(b, "size", 3, 3, 4)
    moves = num(b, "moves", 20, 1, 80)
    return {"board": list(SP.sliding_scramble(moves, size, rng_of(b))), "size": size}


@handler("eight", "solve")
def eight_solve(b):
    size = num(b, "size", 3, 3, 4)
    board = [int(x) for x in b["board"]]
    if sorted(board) != list(range(size * size)):
        raise Bad("the board must contain each tile once")
    if not SP.sliding_solvable(board, size):
        return {"plan": None, "unsolvable": True, "metrics": None, "iterations": []}
    p = SP.SlidingPuzzle(board, size)
    return plan_answer(p, solve_plan(p, max_steps=60, max_nodes=600_000))


@handler("hanoi", "solve")
def hanoi_solve(b):
    n = num(b, "disks", 4, 1, 10)
    h = b.get("heuristic", "exact")
    if h not in ("none", "simple", "exact"):
        raise Bad("heuristic must be none, simple or exact")
    limits = {"none": 4, "simple": 5, "exact": 10}
    if n > limits[h]:
        raise Bad(f"with the '{h}' heuristic, at most {limits[h]} disks finish in reasonable time")
    start = b.get("start")
    p = SP.Hanoi(n, start, h)
    return plan_answer(p, solve_plan(p, max_steps=(1 << n) + 2, max_nodes=800_000))


@handler("river", "solve")
def river_solve(b):
    if b.get("variant", "fwgc") == "fwgc":
        p = SP.FarmerWolfGoatCabbage()
    else:
        p = SP.MissionariesCannibals(num(b, "m", 3, 1, 8), num(b, "c", 3, 1, 8), num(b, "boat", 2, 2, 4))
    return plan_answer(p, solve_plan(p, max_steps=40))


@handler("sokoban", "levels")
def sokoban_levels(b):
    return {"levels": [{"name": k, "map": v.strip("\n")} for k, v in SP.SOKOBAN_LEVELS.items()]}


@handler("sokoban", "solve")
def sokoban_solve(b):
    level = b.get("map") or ""
    if len(level) > 400:
        raise Bad("level too large")
    p = SP.Sokoban(level)
    r = solve_plan(p, max_steps=80, max_nodes=500_000)
    return plan_answer(p, r)


# ================================================================ strategy ====

def _move_answer(r, fmt=lambda m: m):
    return {"move": J(fmt(r["move"])) if r.get("move") is not None else None, "score": r.get("score"),
            "depth": r.get("depth"), "nodes": r.get("nodes"), "ms": r.get("ms")}


@handler("connect4", "move")
def c4_move(b):
    g = G.ConnectFour()
    cols = tuple(tuple(int(x) for x in col) for col in b["cols"])
    state = (cols, int(b.get("to_move", 2)), None)
    depth = num(b, "depth", 6, 1, 9)
    r = best_move(g, state, depth, time_budget=float(b.get("time", 2.5)))
    return _move_answer(r)


@handler("nim", "analyse")
def nim_analyse(b):
    heaps = [int(h) for h in b.get("heaps", [3, 4, 5])]
    if not heaps or any(h < 0 or h > 15 for h in heaps) or len(heaps) > 6:
        raise Bad("up to 6 heaps of 0–15 stones")
    g = G.Nim()
    state = g.initial_from(heaps)
    w = winning_moves(g, state, sum(heaps))
    nimsum = 0
    for h in heaps:
        nimsum ^= h
    good = [list(m) for m, ok in (w["moves"] or {}).items() if ok]
    return {"winning_moves": good, "position_won": bool(good), "nodes": w["nodes"], "ms": w["ms"],
            "nim_sum": nimsum}


@handler("othello", "move")
def othello_move(b):
    n = num(b, "n", 8, 6, 8)
    g = G.Othello(n)
    board = tuple(int(x) for x in b["board"])
    state = (board, int(b.get("to_move", 2)), 0)
    legal = g.moves(state)
    if not legal:
        return {"move": None, "legal": []}
    r = best_move(g, state, num(b, "depth", 4, 1, 6), time_budget=float(b.get("time", 2.5)))
    return {**_move_answer(r), "legal": legal}


@handler("othello", "legal")
def othello_legal(b):
    n = num(b, "n", 8, 6, 8)
    g = G.Othello(n)
    board = tuple(int(x) for x in b["board"])
    p = int(b.get("to_move", 1))
    return {"legal": g.legal(board, p), "flips": {i: g._flips(board, i, p) for i in g.legal(board, p)},
            "winner": g.winner((board, p, 0))}


@handler("hex", "move")
def hex_move(b):
    n = num(b, "n", 5, 3, 9)
    g = G.Hex(n)
    board = tuple(int(x) for x in b["board"])
    state = (board, int(b.get("to_move", 2)))
    empties = board.count(0)
    if n <= 3 or (n == 4 and empties <= 12):
        r = prove_win(g, state, empties, max_nodes=300_000)
        if r["win"] and r["line"]:
            return {"move": r["line"][0], "proved": True, "nodes": r["nodes"], "ms": r["ms"],
                    "note": "a forced win — proved by exhaustive quantified search"}
    r = best_move(g, state, num(b, "depth", 3, 1, 5), time_budget=float(b.get("time", 2.5)))
    return {**_move_answer(r), "proved": False}


@handler("hex", "prove")
def hex_prove(b):
    """3x3: list every winning opening. 4x4: prove one (listing all 16
    openings would mean 16 separate proofs)."""
    n = num(b, "n", 3, 3, 4)
    g = G.Hex(n)
    if n == 3:
        w = winning_moves(g, g.initial(), 9)
        return {"winning_first_moves": [m for m, ok in w["moves"].items() if ok],
                "nodes": w["nodes"], "ms": w["ms"], "all": True}
    r = prove_win(g, g.initial(), 16, max_nodes=3_000_000)
    return {"winning_first_moves": r["line"][:1], "nodes": r["nodes"], "ms": r["ms"], "all": False}


@handler("chess", "puzzles")
def chess_puzzles(b):
    return {"puzzles": G.CHESS_PUZZLES}


@handler("chess", "solve")
def chess_solve(b):
    g = G.ChessTactics()
    fen, moves = b["fen"], num(b, "moves", 2, 1, 3)
    r = prove_win(g, fen, 2 * moves - 1, max_nodes=400_000)
    return {"win": r["win"], "depth": r["depth"], "line": r["line"],
            "san": g.san_line(fen, r["line"]) if r["line"] else [], "nodes": r["nodes"], "ms": r["ms"]}


@handler("chess", "try")
def chess_try(b):
    g = G.ChessTactics()
    fen, moves, uci = b["fen"], num(b, "moves", 2, 1, 3), b["move"]
    if uci not in g.moves(fen):
        return {"legal": False}
    after = g.result(fen, uci)
    if g.winner(after) == g.to_move(fen):
        return {"legal": True, "wins": True, "mate": True, "san": g.san_line(fen, [uci])[0]}
    w = winning_moves(g, fen, 2 * moves - 1, max_nodes=400_000)
    wins = bool(w["moves"] and w["moves"].get(uci))
    return {"legal": True, "wins": wins, "mate": False, "san": g.san_line(fen, [uci])[0], "nodes": w["nodes"]}


@handler("chess", "play")
def chess_play(b):
    """You play White's move; if it still forces mate, the engine answers
    with Black's most stubborn defence and you continue."""
    g = G.ChessTactics()
    fen, left, uci = b["fen"], num(b, "moves_left", 2, 1, 3), b["move"]
    if uci not in g.moves(fen):
        return {"legal": False}
    san = g.san_line(fen, [uci])[0]
    after = g.result(fen, uci)
    if g.winner(after) == g.to_move(fen):
        return {"legal": True, "mate": True, "wins": True, "san": san, "fen": after}
    if left == 1:
        return {"legal": True, "mate": False, "wins": False, "san": san, "fen": after}
    w = winning_moves(g, fen, 2 * left - 1, max_nodes=400_000)
    if not (w["moves"] and w["moves"].get(uci)):
        return {"legal": True, "mate": False, "wins": False, "san": san, "fen": after}
    best, best_d = None, -1
    for r in g.moves(after):
        res = g.result(after, r)
        d = prove_win(g, res, 2 * left - 3, max_nodes=200_000)["depth"]
        if d > best_d:
            best, best_d = r, d
    return {"legal": True, "mate": False, "wins": True, "san": san,
            "reply": g.san_line(after, [best])[0], "fen": g.result(after, best), "moves_left": left - 1}


# ================================================================== graphs ====

def _map_build(inst):
    return graph_colouring_csp(inst["adjacency"], inst["colours"])


csp_actions("map", _map_build, str, str, lambda inst, entries: {k: v for k, v in entries})


@handler("map", "new")
def map_new(b):
    colours = b.get("colours") or ["#e4572e", "#29a7d6", "#f3c13a", "#5cb85c"]
    if b.get("mode") == "australia":
        return {"inst": {"adjacency": AUSTRALIA, "colours": colours, "layout": GP.AUSTRALIA_LAYOUT}}
    rows, cols = num(b, "rows", 12, 4, 30), num(b, "cols", 16, 4, 40)
    regions = num(b, "regions", 14, 2, 60)
    m = GP.random_map(rows, cols, regions, rng_of(b))
    return {"inst": {"adjacency": m["adjacency"], "grid": m["grid"], "colours": colours}}


@handler("map", "chromatic")
def map_chromatic(b):
    k, sol, attempts = GP.min_slots(b["inst"]["adjacency"], max_k=6)
    return {"k": k, "solution": sol, "attempts": attempts}


@handler("tsp", "new")
def tsp_new(b):
    return {"cities": GP.tsp_instance(num(b, "n", 9, 3, 11), rng_of(b))}


@handler("tsp", "solve")
def tsp_solve(b):
    cities = b["cities"]
    if not 3 <= len(cities) <= 11:
        raise Bad("3 to 11 cities")
    r = GP.solve_tsp(cities)
    return {"tour": r["tour"], "length": r["length"], "optimal": r["optimal"],
            "improvements": r["improvements"], "metrics": metrics_dict(r["metrics"]),
            "nearest_neighbour": r["nearest_neighbour"], "census": census_opt(r["census_csp"])}


@handler("shortest", "new")
def shortest_new(b):
    g = GP.random_road_graph(num(b, "n", 24, 5, 60), rng_of(b))
    return {**g, "source": 0, "target": len(g["points"]) - 1}


@handler("shortest", "solve")
def shortest_solve(b):
    pts, edges, s, t = b["points"], b["edges"], int(b["source"]), int(b["target"])
    r = GP.solve_road(pts, edges, s, t)
    dpath, dcost = GP.dijkstra(pts, edges, s, t)
    p = GP.RoadTrip(pts, edges, s, t)
    csp, _ = plan_csp(p, max(1, len(r["path"] or []) - 1), r["cost"] or 0, allow_done=True)
    return {"path": r["path"], "cost": r["cost"], "iterations": r["iterations"],
            "metrics": metrics_dict(r["metrics"]), "dijkstra": {"path": dpath, "cost": dcost},
            "census": census(csp)}


def _exam_build(inst):
    return exam_scheduling_csp(inst["enrollments"], int(inst["slots"]))


csp_actions("exam", _exam_build, str, lambda v: f"slot {v}",
            lambda inst, entries: {e: int(s) for e, s in entries})


@handler("exam", "new")
def exam_new(b):
    e = GP.random_enrollments(num(b, "students", 14, 2, 40), num(b, "exams", 8, 2, 16),
                              num(b, "per", 3, 1, 6), rng_of(b))
    adj = conflict_graph(e)
    k, _, attempts = GP.min_slots(adj)
    return {"inst": {"enrollments": e, "slots": k}, "adjacency": adj, "min_slots": k,
            "attempts": attempts, "census": census(exam_scheduling_csp(e, k))}


@handler("knapsack", "new")
def knapsack_new(b):
    return knapsack_instance_dict(num(b, "n", 14, 2, 30), rng_of(b))


def knapsack_instance_dict(n, rng):
    return GP.knapsack_instance(n, rng)


@handler("knapsack", "solve")
def knapsack_solve(b):
    items, cap = b["items"], int(b["capacity"])
    if not 1 <= len(items) <= 30:
        raise Bad("1 to 30 items")
    r = GP.solve_knapsack(items, cap)
    return {"chosen": r["chosen"], "value": r["value"], "weight": r["weight"], "optimal": r["optimal"],
            "improvements": r["improvements"], "metrics": metrics_dict(r["metrics"]),
            "greedy": r["greedy"], "census": census_opt(r["census_csp"])}


# ================================================================ planning ====

@handler("treasure", "new")
def treasure_new(b):
    return PP.treasure_instance(num(b, "rows", 9, 5, 16), num(b, "cols", 12, 5, 20),
                                num(b, "treasures", 5, 1, 7), rng_of(b))


@handler("treasure", "solve")
def treasure_solve(b):
    r = PP.solve_treasure(b)
    return {"order": r["order"], "path": r["path"], "length": r["length"],
            "metrics": metrics_dict(r["metrics"]), "leg_nodes": r["leg_nodes"],
            "census": census_opt(r["census_csp"])}


@handler("gridworld", "new")
def gridworld_new(b):
    return PP.gridworld_instance(num(b, "rows", 6, 4, 12), num(b, "cols", 8, 4, 14), rng_of(b))


@handler("gridworld", "plan")
def gridworld_plan(b):
    r = PP.solve_gridworld(b)
    out = {"best": r["best"], "tried": r["tried"]}
    if r["best"]:
        p = PP.GridworldPlan(b["grid"], b["pits"], b["start"], r["best"]["gem"])
        T = max(1, len(r["best"]["path"]) - 1)
        out["census"] = census(plan_csp(p, T, T)[0])
    return out


@handler("gridworld", "learn")
def gridworld_learn(b):
    return q_learning(b["inst"], episodes=num(b, "episodes", 300, 1, 5000),
                      alpha=float(b.get("alpha", 0.5)), gamma=float(b.get("gamma", 0.95)),
                      epsilon=float(b.get("epsilon", 0.2)), slip=float(b.get("slip", 0.0)),
                      seed=b.get("seed"))


@handler("resource", "new")
def resource_new(b):
    return PP.project_instance(num(b, "tasks", 8, 2, 12), rng_of(b))


@handler("resource", "solve")
def resource_solve(b):
    r = PP.solve_project(b, max_nodes=60_000)
    return {"starts": r["starts"], "makespan": r["makespan"], "optimal": r["optimal"],
            "improvements": r["improvements"], "metrics": metrics_dict(r["metrics"]),
            "critical_path": r["critical_path"], "census": census_opt(r["census_csp"])}


@handler("mapf", "new")
def mapf_new(b):
    return PP.mapf_instance(num(b, "rows", 7, 4, 12), num(b, "cols", 7, 4, 12),
                            num(b, "agents", 3, 1, 6), rng_of(b))


@handler("mapf", "solve")
def mapf_solve(b):
    r = PP.solve_mapf(b)
    out = {k: v for k, v in r.items() if k != "census_csp"}
    if r.get("census_csp") is not None:
        out["census"] = census(r["census_csp"])
    return out


# ================================================================= spatial ====

def _tan_target(b):
    return frozenset(tuple(q) for q in b["shape"])


@handler("tangram", "new")
def tangram_new(b):
    mode = b.get("mode", "Square")
    shapes = SPA.tangram_shapes()
    shape = shapes[mode] if mode in shapes else SPA.random_tangram(rng_of(b))
    return {"shape": sorted(map(list, shape)), "shapes": list(shapes) + ["Random"]}


@handler("tangram", "solve")
def tangram_solve(b):
    csp, placements = SPA.tangram_csp(_tan_target(b))
    sol, md = solve_csp(csp, b)
    pieces = {name: placements[name][mask] for name, mask in sol.items()} if sol else None
    return {"pieces": J(pieces), "metrics": md, "census": census(csp),
            "domain_sizes": {v: len(csp.domains[v]) for v in csp.variables}}


@handler("tangram", "pieces")
def tangram_pieces(b):
    """Every orientation of every tan, as quarter-triangle sets anchored at 0,0."""
    return {"pieces": {name: [sorted(map(list, o)) for o in SPA._tan_orientations(poly)]
                       for name, poly in SPA.TAN_POLYGONS.items()}}


@handler("rubiks", "new")
def rubiks_new(b):
    state, seq = SP.cube_scramble(num(b, "moves", 7, 1, 14), rng_of(b))
    return {"state": J(state), "scramble": seq, "faces": SP.cube_faces(state)}


@handler("rubiks", "solve")
def rubiks_solve(b):
    st = b["state"]
    state = (tuple(st[0]), tuple(st[1]))
    p = SP.PocketCube(state)
    r = solve_plan(p, max_steps=14, max_nodes=600_000)
    faces = [SP.cube_faces(s) for s in (r["states"] or [])]
    return plan_answer(p, r, {"faces": faces})


@handler("rubiks", "turn")
def rubiks_turn(b):
    st = b["state"]
    state = SP.cube_turn((tuple(st[0]), tuple(st[1])), b["move"])
    return {"state": J(state), "faces": SP.cube_faces(state), "solved": state == SP.SOLVED_CUBE}


def _jigsaw_build(inst):
    return SPA.jigsaw_csp(inst)


@handler("jigsaw", "new")
def jigsaw_new(b):
    return SPA.jigsaw_instance(num(b, "n", 4, 2, 7), rng_of(b))


@handler("jigsaw", "solve")
def jigsaw_solve(b):
    csp = _jigsaw_build(b["inst"])
    sol, md = solve_csp(csp, b)
    return {"solution": J({key_of(k): v for k, v in sol.items()}) if sol else None,
            "metrics": md, "census": census(_jigsaw_build(b["inst"]))}


@handler("jigsaw", "trace")
def jigsaw_trace(b):
    return trace_csp(_jigsaw_build(b["inst"]), b)


@handler("polyomino", "new")
def poly_new(b):
    mode = b.get("mode", "random")
    if mode in SPA.TILING_PRESETS:
        p = SPA.TILING_PRESETS[mode]
    else:
        p = SPA.random_tiling_puzzle(num(b, "pieces", 6, 2, 10), rng_of(b))
    return {**p, "presets": list(SPA.TILING_PRESETS) + ["Random shape"]}


@handler("polyomino", "solve")
def poly_solve(b):
    pieces = {name: SPA.PENTOMINOES[name] for name in b["pieces"]}
    csp, placements = SPA.tiling_csp(b["region"], pieces)
    sol, md = solve_csp(csp, b)
    return {"pieces": J({n: placements[n][m] for n, m in sol.items()}) if sol else None,
            "metrics": md, "census": census(csp)}


@handler("polyomino", "trace")
def poly_trace(b):
    pieces = {name: SPA.PENTOMINOES[name] for name in b["pieces"]}
    csp, placements = SPA.tiling_csp(b["region"], pieces)
    t = trace_csp(csp, b)
    t["placements"] = {n: {str(m): cells for m, cells in pl.items()} for n, pl in placements.items()}
    return J(t)


@handler("folding", "check")
def folding_check(b):
    cells = [tuple(c) for c in b["cells"]]
    if not 1 <= len(cells) <= 12:
        raise Bad("draw between 1 and 12 squares")
    csp = SPA.net_csp(cells)
    sol, md = solve_csp(csp, b)
    faces = {key_of(c): SPA.FACE_NAME[o[0]] for c, o in sol.items()} if sol else None
    return {"folds": sol is not None and len(cells) == 6, "consistent": sol is not None,
            "faces": faces, "metrics": md, "census": census(SPA.net_csp(cells))}


@handler("folding", "all")
def folding_all(b):
    out = []
    for shape in SPA.hexominoes():
        sol, _ = backtracking_search(SPA.net_csp(shape), select_var=mrv, inference=mac_plus)
        out.append({"cells": [list(c) for c in shape], "folds": sol is not None})
    return {"hexominoes": out}
