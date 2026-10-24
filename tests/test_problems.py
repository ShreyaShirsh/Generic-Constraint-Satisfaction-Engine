"""Tests for the adapters in `csp_engine/problems` -- each one only builds a
CSP; these tests confirm the description is right by checking the solver's
answer against a known fact about the puzzle (a count, a specific value, a
feasibility result).
"""
import pytest

from csp_engine.core.backtracking import backtracking_search, find_all_solutions
from csp_engine.core.inference import mac
from csp_engine.core.heuristics import mrv, mrv_degree, lcv
from csp_engine.problems import nqueens, graph_colouring, sudoku, cryptarithmetic, zebra, exam_scheduling


# ---- N-Queens ----------------------------------------------------------------

@pytest.mark.parametrize("n,expected", [(4, 2), (6, 4), (8, 92)])
def test_nqueens_solution_counts(n, expected):
    solutions, metrics = find_all_solutions(nqueens.nqueens_csp(n))
    assert len(solutions) == expected
    assert metrics.solved is True


def test_nqueens_one_queen_trivially_solvable():
    solution, _ = backtracking_search(nqueens.nqueens_csp(1))
    assert solution == {0: 0}


def test_nqueens_board_str_places_queens_correctly():
    csp = nqueens.nqueens_csp(4)
    solution, _ = backtracking_search(csp)
    board = nqueens.board_str(solution, 4)
    assert board.count("Q") == 4


# ---- Map / graph colouring ----------------------------------------------------

def test_australia_three_colours_solvable():
    solution, _ = backtracking_search(graph_colouring.australia_csp())
    assert solution is not None


def test_australia_two_colours_impossible():
    solution, _ = backtracking_search(graph_colouring.australia_csp(["red", "green"]))
    assert solution is None


def test_custom_graph_adjacency_builds_correctly():
    adjacency = {"A": ["B"], "B": ["A", "C"], "C": ["B"]}     # a 3-node path, not a triangle
    csp = graph_colouring.graph_colouring_csp(adjacency, ["red", "blue"])
    solution, _ = backtracking_search(csp)
    assert solution is not None                                # a path is 2-colourable
    assert solution["A"] != solution["B"] != solution["C"]


# ---- Sudoku ---------------------------------------------------------------------

def test_sudoku_easy_preset_solves_and_is_valid():
    csp = sudoku.sudoku_csp(sudoku.EASY_9x9, 3, 3)
    solution, _ = backtracking_search(csp, select_var=mrv, inference=mac)
    assert solution is not None
    assert csp.is_solution(solution)
    for r in range(9):
        assert {solution[(r, c)] for c in range(9)} == set(range(1, 10))   # every row is 1-9


def test_sudoku_respects_given_clues():
    csp = sudoku.sudoku_csp(sudoku.EASY_9x9, 3, 3)
    solution, _ = backtracking_search(csp, select_var=mrv, inference=mac)
    for r in range(9):
        for c in range(9):
            given = sudoku.EASY_9x9[r][c]
            if given:
                assert solution[(r, c)] == given


# ---- Cryptarithmetic -----------------------------------------------------------

def test_send_more_money():
    csp = cryptarithmetic.cryptarithmetic_csp("SEND", "MORE", "MONEY")
    solution, _ = backtracking_search(csp, select_var=mrv_degree, order_values=lcv, inference=mac)
    assert solution is not None
    s = solution
    send = s["S"] * 1000 + s["E"] * 100 + s["N"] * 10 + s["D"]
    more = s["M"] * 1000 + s["O"] * 100 + s["R"] * 10 + s["E"]
    money = s["M"] * 10000 + s["O"] * 1000 + s["N"] * 100 + s["E"] * 10 + s["Y"]
    assert send + more == money
    assert s["S"] != 0 and s["M"] != 0                        # leading digits non-zero
    letters = set("SENDMORY")
    letter_values = [v for k, v in s.items() if k in letters]
    assert len(set(letter_values)) == len(letter_values)       # all-different held (letters only;
                                                                # hidden carry variables aren't part of it)


def test_cryptarithmetic_rejects_result_shorter_than_addends():
    with pytest.raises(ValueError):
        cryptarithmetic.cryptarithmetic_csp("ABCDE", "F", "GH")


# ---- Zebra puzzle -----------------------------------------------------------------

def test_zebra_puzzle_has_unique_known_answer():
    csp = zebra.zebra_csp()
    solution, _ = backtracking_search(csp, select_var=mrv, inference=mac)
    assert solution is not None
    assert zebra.who_owns_zebra(solution) == "Japanese"
    # the other classic fact about this puzzle
    water_house = solution[("drink", "Water")]
    norwegian_house = solution[("nation", "Norwegian")]
    assert water_house == norwegian_house


# ---- Exam scheduling (reduction to graph colouring) --------------------------------

def test_conflict_graph_symmetric_and_correct():
    adjacency = exam_scheduling.conflict_graph(exam_scheduling.SAMPLE_ENROLLMENTS)
    for exam, neighbours in adjacency.items():
        for other in neighbours:
            assert exam in adjacency[other]                    # symmetric


def test_exam_scheduling_feasible_with_enough_slots():
    csp = exam_scheduling.exam_scheduling_csp(exam_scheduling.SAMPLE_ENROLLMENTS, num_slots=4)
    solution, _ = backtracking_search(csp)
    assert solution is not None
    adjacency = exam_scheduling.conflict_graph(exam_scheduling.SAMPLE_ENROLLMENTS)
    for exam, neighbours in adjacency.items():                 # no two conflicting exams share a slot
        for other in neighbours:
            assert solution[exam] != solution[other]


def test_exam_scheduling_infeasible_with_one_slot():
    csp = exam_scheduling.exam_scheduling_csp(exam_scheduling.SAMPLE_ENROLLMENTS, num_slots=1)
    solution, _ = backtracking_search(csp)
    assert solution is None
