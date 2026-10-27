"""Correctness of the planning / optimisation / quantified-game extensions
and the gallery problems, each checked against an independent answer
(brute force, Dijkstra, or a known mathematical fact)."""
import itertools
import math
import random
from functools import reduce
from operator import xor

import pytest

from csp_engine.core.planning import solve_plan, plan_csp
from csp_engine.core.adversarial import prove_win, winning_moves, best_move
from csp_engine.core.census import census
from csp_engine.core.generator import count_solutions
from csp_engine.core.backtracking import backtracking_search
from csp_engine.core.inference import mac
from csp_engine.core.heuristics import mrv
from csp_engine.core.explain import grade
from csp_engine.problems import search_puzzles as SP, games as G, graph_problems as GP
from csp_engine.problems import planning_problems as PP, spatial as SPA, logic_puzzles as LP
from csp_engine.problems import cryptarithmetic as CR, minesweeper as MS


# ---- planning as CSP --------------------------------------------------------

@pytest.mark.parametrize("n", [1, 2, 3, 4, 6])
def test_hanoi_optimal_is_2n_minus_1(n):
    assert len(solve_plan(SP.Hanoi(n), max_steps=200)["plan"]) == 2 ** n - 1


def test_hanoi_heuristic_does_not_change_the_answer():
    plans = {h: len(solve_plan(SP.Hanoi(3, heuristic=h))["plan"]) for h in ("none", "simple", "exact")}
    assert set(plans.values()) == {7}


def test_river_crossings_known_optima():
    assert len(solve_plan(SP.FarmerWolfGoatCabbage())["plan"]) == 7
    assert len(solve_plan(SP.MissionariesCannibals(3, 3, 2))["plan"]) == 11


def test_eight_puzzle_plan_is_valid_and_optimal_vs_bfs():
    board = SP.sliding_scramble(14, 3, random.Random(5))
    p = SP.SlidingPuzzle(board)
    r = solve_plan(p)
    # breadth-first search gives the true optimum to compare against
    frontier, seen, depth = {p.initial}, {p.initial}, 0
    while p.goal not in frontier:
        nxt = set()
        for s in frontier:
            for a in p.alphabet:
                n = p.result(s, a)
                if n is not None and n not in seen:
                    seen.add(n)
                    nxt.add(n)
        frontier, depth = nxt, depth + 1
    assert len(r["plan"]) == depth
    assert r["states"][-1] == p.goal


def test_planning_csp_is_one_predicate():
    c = census(plan_csp(SP.Hanoi(3), 7, 7)[0])
    assert c["variables"] == 7 and c["constraints"] == 1


def test_pocket_cube_solves_scrambles():
    for seed in range(3):
        state, seq = SP.cube_scramble(6, random.Random(seed))
        r = solve_plan(SP.PocketCube(state), max_steps=14)
        assert len(r["plan"]) <= 6 and r["states"][-1] == SP.SOLVED_CUBE


def test_sokoban_levels_all_solve():
    for name, level in SP.SOKOBAN_LEVELS.items():
        p = SP.Sokoban(level)
        r = solve_plan(p, max_steps=80)
        assert r["plan"] is not None, name
        assert p.is_goal(r["states"][-1])


# ---- optimisation as CSP + one bound predicate ---------------------------------

def test_tsp_matches_brute_force():
    cities = GP.tsp_instance(7, random.Random(2))
    n = len(cities)
    best = min(sum(math.dist(cities[p[i]], cities[p[(i + 1) % n]]) for i in range(n))
               for p in ([0] + list(q) for q in itertools.permutations(range(1, n))))
    assert abs(GP.solve_tsp(cities)["length"] - best) < 1e-6


def test_knapsack_matches_brute_force():
    k = GP.knapsack_instance(12, random.Random(4))
    items, cap = k["items"], k["capacity"]
    best = max(sum(items[i]["value"] for i in range(12) if m >> i & 1) for m in range(1 << 12)
               if sum(items[i]["weight"] for i in range(12) if m >> i & 1) <= cap)
    assert GP.solve_knapsack(items, cap)["value"] == best


def test_shortest_path_matches_dijkstra():
    g = GP.random_road_graph(20, random.Random(6))
    r = GP.solve_road(g["points"], g["edges"], 0, 19)
    _, d = GP.dijkstra(g["points"], g["edges"], 0, 19)
    assert abs(r["cost"] - d) < 1e-6


def test_project_schedule_respects_every_rule():
    inst = PP.project_instance(7, random.Random(3))
    r = PP.solve_project(inst)
    s, tasks = r["starts"], inst["tasks"]
    for a, b in inst["precedence"]:
        assert s[a] + tasks[a]["duration"] <= s[b]
    for res, cap in inst["capacity"].items():
        for t in range(r["makespan"]):
            assert sum(x.get(res, 0) for i, x in enumerate(tasks) if s[i] <= t < s[i] + x["duration"]) <= cap


def test_mapf_paths_never_collide():
    inst = PP.mapf_instance(6, 6, 4, random.Random(2))
    r = PP.solve_mapf(inst)
    paths = r["paths"]
    for t in range(r["makespan"] + 1):
        cells = [tuple(p[t]) for p in paths]
        assert len(set(cells)) == len(cells)
    for a, p in enumerate(paths):
        assert p[0] == inst["starts"][a] and p[-1] == inst["goals"][a]


# ---- games as quantified CSPs ----------------------------------------------------

@pytest.mark.parametrize("heaps", [(1, 2, 3), (3, 4, 5), (2, 2), (1, 4, 6), (5, 5, 1)])
def test_nim_engine_agrees_with_nim_sum_theory(heaps):
    nim = G.Nim()
    r = prove_win(nim, nim.initial_from(heaps), sum(heaps))
    assert r["win"] == (reduce(xor, heaps) != 0)


def test_hex_3x3_first_player_wins():
    h = G.Hex(3)
    assert prove_win(h, h.initial(), 9)["win"]


def test_chess_puzzles_are_forced_mates():
    ct = G.ChessTactics()
    for p in G.CHESS_PUZZLES:
        r = prove_win(ct, p["fen"], 2 * p["moves"] - 1, max_nodes=400_000)
        assert r["win"] and r["depth"] == 2 * p["moves"] - 1, p["id"]
        assert ct.san_line(p["fen"], r["line"])[-1].endswith("#")


def test_connect_four_takes_an_immediate_win():
    c4 = G.ConnectFour()
    state = c4.initial()
    for col in (0, 6, 1, 6, 2, 5):          # red has 0,1,2 on the bottom row
        state = c4.result(state, col)
    assert best_move(c4, state, 3)["move"] == 3


# ---- reasoning puzzles -------------------------------------------------------------

def test_generated_zebra_is_unique_and_logical():
    g = LP.generate_zebra(4, 4, seed=3)
    csp = LP.zebra_from_instance(g)
    assert count_solutions(csp, limit=2) == 1
    assert grade(csp, {}).solved_by_logic


def test_generated_knights_are_unique():
    for n in (2, 3, 4):
        k = LP.generate_knights(n, seed=n)
        assert count_solutions(LP.knights_csp(k["people"], k["statements"]), limit=2) == 1


def test_crypt_classics_unique_and_generator_unique():
    for adds, res in CR.CLASSICS:
        assert count_solutions(CR.crypt_csp(adds, res), limit=2, budget=200_000) == 1
    g = CR.generate_crypt(seed=1)
    assert count_solutions(CR.crypt_csp(g["addends"], g["result"], g["givens"]), limit=2) == 1


def test_minesweeper_probabilities_are_consistent():
    rng = random.Random(1)
    mines = set(MS.new_board(9, 9, 10, (4, 4), rng))
    revealed = {}
    MS.reveal((4, 4), mines, revealed, 9, 9)
    probs = MS.analyse(revealed, 9, 9, 10)["probabilities"]
    assert abs(sum(probs.values()) - 10) < 1e-6           # expected mines = total mines
    assert all(0 <= p <= 1 for p in probs.values())


def test_minesweeper_certain_moves_are_correct():
    for seed in range(5):
        g = MS.autoplay(9, 9, 10, seed)
        layout = {tuple(m) for m in g["mines"]}
        for mv in g["moves"]:
            if mv["kind"] == "flag":
                assert tuple(mv["cell"]) in layout
            if mv["kind"] == "reveal":
                assert tuple(mv["cell"]) not in layout


# ---- spatial ---------------------------------------------------------------------------

def test_exactly_eleven_hexominoes_fold_into_a_cube():
    shapes = SPA.hexominoes()
    assert len(shapes) == 35
    folds = sum(1 for s in shapes if backtracking_search(SPA.net_csp(s), select_var=mrv, inference=mac)[0])
    assert folds == 11


def test_tangram_square_and_triangle_solve():
    for shape in SPA.tangram_shapes().values():
        csp, _ = SPA.tangram_csp(shape)
        assert backtracking_search(csp, select_var=mrv, inference=mac)[0] is not None


def test_tiling_presets_and_random_shapes_solve():
    for p in list(SPA.TILING_PRESETS.values()) + [SPA.random_tiling_puzzle(6, random.Random(s)) for s in range(3)]:
        csp, _ = SPA.tiling_csp(p["region"], {k: SPA.PENTOMINOES[k] for k in p["pieces"]})
        assert backtracking_search(csp, select_var=mrv, inference=mac, max_nodes=50_000)[0] is not None


def test_jigsaw_solution_is_unique_and_fits():
    inst = SPA.jigsaw_instance(5, random.Random(9))
    assert count_solutions(SPA.jigsaw_csp(inst), limit=2) == 1
