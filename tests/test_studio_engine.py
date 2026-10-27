"""Tests for the engine pieces behind the Puzzle Studio: the grid-puzzle
compiler, n-ary propagation, pigeonhole reasoning, the search tracer, the
human-style reasoner/grader and the generic generator."""
import random
import pytest

from csp_engine.core.backtracking import backtracking_search, find_all_solutions, SearchAborted
from csp_engine.core.inference import mac, mac_plus, ac3
from csp_engine.core.heuristics import mrv
from csp_engine.core.explain import next_step, grade, candidates
from csp_engine.core.generator import generate, count_solutions
from csp_engine.problems.grid_puzzle import (grid_puzzle_csp, sudoku_rules, latin_rules, givens_of,
                                             cell_name, generate_puzzle, rules_for)
from csp_engine.problems.sudoku import EASY_9x9
from csp_engine.problems import puzzle_presets
from csp_engine.problems.cryptarithmetic import cryptarithmetic_csp


def easy_spec():
    spec = sudoku_rules(9)
    spec["givens"] = [[r, c, EASY_9x9[r][c]] for r in range(9) for c in range(9) if EASY_9x9[r][c]]
    return spec


def preset(pid):
    return next(p for p in puzzle_presets.load() if p["id"] == pid)


# ---- grid-puzzle compiler ----------------------------------------------------

def test_sudoku_spec_compiles_and_solves():
    csp = grid_puzzle_csp(easy_spec())
    assert len(csp.variables) == 81
    assert len(csp.groups) == 27
    solution, _ = backtracking_search(csp, select_var=mrv, inference=mac)
    assert csp.is_solution(solution)
    for r, c, v in easy_spec()["givens"]:
        assert solution[(r, c)] == v


@pytest.mark.parametrize("bad", [
    {"size": 1},
    {"size": 6, "rules": {"boxes": [4, 4]}},
    {"size": 4, "cages": [{"cells": [[0, 0]], "op": "^", "target": 1}]},
    {"size": 4, "cages": [{"cells": [[0, 0], [0, 1], [0, 2]], "op": "-", "target": 1}]},
    {"size": 4, "givens": [[5, 5, 1]]},
    {"size": 4, "inequalities": [{"a": [0, 0], "b": [9, 9]}]},
])
def test_invalid_specs_rejected(bad):
    with pytest.raises(ValueError):
        grid_puzzle_csp(bad)


@pytest.mark.parametrize("op,target,cells_vals,ok", [
    ("+", 5, [2, 3], True), ("+", 5, [2, 2], False),
    ("*", 6, [2, 3], True), ("*", 6, [1, 3], False),
    ("-", 2, [1, 3], True), ("-", 2, [2, 3], False),
    ("/", 3, [1, 3], True), ("/", 3, [2, 3], False),
])
def test_cage_arithmetic(op, target, cells_vals, ok):
    spec = {"size": 4, "cages": [{"cells": [[0, 0], [0, 1]], "op": op, "target": target}],
            "givens": [[0, 0, cells_vals[0]], [0, 1, cells_vals[1]]]}
    csp = grid_puzzle_csp(spec)
    cage = next(c for c in csp.constraints if c.name == "Cage")
    assert cage.is_satisfied({(0, 0): cells_vals[0], (0, 1): cells_vals[1]}) is ok


def test_partial_sum_cage_prunes_early():
    spec = {"size": 4, "cages": [{"cells": [[0, 0], [0, 1], [0, 2]], "op": "+", "target": 4}]}
    cage = next(c for c in grid_puzzle_csp(spec).constraints if c.name == "Cage")
    assert cage.is_satisfied({(0, 0): 1}) is True          # 1 + at least 1 + 1 <= 4
    assert cage.is_satisfied({(0, 0): 3}) is False         # 3 + 1 + 1 > 4 already


# ---- propagation --------------------------------------------------------------

def test_nary_arc_consistency_prunes_cage_values():
    spec = {"size": 4, "cages": [{"cells": [[0, 0], [0, 1]], "op": "+", "target": 3}]}
    csp = grid_puzzle_csp(spec)
    ok, _ = ac3(csp)
    assert ok
    assert set(csp.domains[(0, 0)]) == {1, 2}              # only 1+2 / 2+1 make 3


def test_mac_plus_solves_expert_without_backtracking_much():
    csp = grid_puzzle_csp(preset("sudoku-expert")["spec"])
    plain_csp = grid_puzzle_csp(preset("sudoku-expert")["spec"])
    solution, m_plus = backtracking_search(csp, select_var=mrv, inference=mac_plus)
    _, m_mac = backtracking_search(plain_csp, select_var=mrv, inference=mac)
    assert csp.is_solution(solution)
    assert m_plus.backtracks <= m_mac.backtracks


def test_cryptarithmetic_fast_with_generalised_arc_consistency():
    csp = cryptarithmetic_csp("SEND", "MORE", "MONEY")
    solution, metrics = backtracking_search(csp, select_var=mrv, inference=mac)
    assert solution is not None and metrics.nodes < 500


# ---- search hygiene and tracing --------------------------------------------------

def test_finished_search_leaves_domains_untouched():
    csp = grid_puzzle_csp(easy_spec())
    before = {v: set(csp.domains[v]) for v in csp.variables}
    backtracking_search(csp, select_var=mrv, inference=mac)
    find_all_solutions(csp, select_var=mrv, inference=mac, max_solutions=2)
    assert {v: set(csp.domains[v]) for v in csp.variables} == before


def test_trace_replays_to_the_solution():
    csp = grid_puzzle_csp(preset("sudoku-medium")["spec"])
    events = []
    solution, _ = backtracking_search(csp, select_var=mrv, inference=mac,
                                      tracer=lambda e, v, x: events.append((e, v, x)))
    board = {}
    for e, v, x in events:
        if e == "assign":
            board[v] = x
        elif e == "unassign":
            del board[v]
    assert events[-1][0] == "solution"
    assert board == solution


def test_tracer_can_abort_search():
    csp = grid_puzzle_csp(easy_spec())
    count = [0]

    def tracer(e, v, x):
        count[0] += 1
        if count[0] > 10:
            raise SearchAborted()

    solution, metrics = backtracking_search(csp, tracer=tracer)
    assert solution is None and metrics.timed_out


# ---- human-style reasoning ---------------------------------------------------------

def test_first_hint_on_easy_is_a_direct_single_and_correct():
    spec = easy_spec()
    rules = grid_puzzle_csp(spec, include_givens=False)
    step = next_step(rules, givens_of(spec), cell_name)
    solution, _ = backtracking_search(grid_puzzle_csp(spec), select_var=mrv, inference=mac)
    assert step.level == 1 and step.kind == "single"
    assert solution[step.var] == step.value
    assert cell_name(step.var) in step.text


def test_every_logical_step_matches_the_unique_solution():
    p = preset("sudoku-hard")
    spec = p["spec"]
    solution, _ = backtracking_search(grid_puzzle_csp(spec), select_var=mrv, inference=mac_plus)
    rules = grid_puzzle_csp(spec, include_givens=False)
    board = givens_of(spec)
    while len(board) < 81:
        step = next_step(rules, board, cell_name)
        if step is None:
            break
        assert solution[step.var] == step.value, step.text
        board[step.var] = step.value


def test_grades():
    rules = grid_puzzle_csp(easy_spec(), include_givens=False)
    g = grade(rules, givens_of(easy_spec()))
    assert g.name == "Easy" and g.solved_by_logic and g.open_left == 0

    expert = preset("sudoku-expert")["spec"]
    g = grade(grid_puzzle_csp(expert, include_givens=False), givens_of(expert))
    assert g.level == 4 and not g.solved_by_logic


def test_candidates_are_pencil_marks():
    spec = easy_spec()
    cands = candidates(grid_puzzle_csp(spec, include_givens=False), givens_of(spec))
    assert cands[(4, 4)] == {5}                 # R5C5 is forced
    assert all((r, c) not in cands for r, c, _ in spec["givens"])


# ---- generator ----------------------------------------------------------------------

@pytest.mark.parametrize("kind,size", [("sudoku", 4), ("sudoku", 6), ("futoshiki", 4),
                                       ("kenken", 4), ("killer", 4), ("x-sudoku", 4)])
def test_generated_puzzles_are_unique(kind, size):
    result = generate_puzzle(kind, size, seed=3, time_budget=3)
    spec = result["spec"]
    assert count_solutions(grid_puzzle_csp(spec), limit=2, budget=500_000) == 1
    assert grid_puzzle_csp(spec).is_solution(result["solution"])


def test_generator_targets_easy():
    result = generate_puzzle("sudoku", 6, target_level=1, seed=4, time_budget=4)
    assert result["grade"].level == 1


def test_generator_works_on_an_invented_rule_set():
    spec = latin_rules(5)
    spec["rules"]["diagonals"] = True
    spec["cages"] = [{"cells": [[0, 0], [0, 1]], "op": "+", "target": 7}]
    csp = grid_puzzle_csp(spec)
    result = generate(csp, None, random.Random(5), 4)
    assert count_solutions(grid_puzzle_csp({**spec, "givens": [
        [r, c, v] for (r, c), v in result["givens"].items()]}), budget=500_000) == 1


def test_presets_file_is_valid():
    for p in puzzle_presets.load():
        assert count_solutions(grid_puzzle_csp(p["spec"]), budget=500_000) == 1, p["id"]
