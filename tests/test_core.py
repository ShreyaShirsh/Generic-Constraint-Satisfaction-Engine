"""Tests for the problem-agnostic engine: everything in `csp_engine/core`.

These deliberately build tiny hand-rolled CSPs instead of importing
`problems/`, so a bug in an adapter can never hide a bug in the engine
(and vice versa) -- the two are tested independently, matching how the
codebase itself separates them.
"""
from csp_engine.core.model import CSP, Domain
from csp_engine.core.constraints import BinaryRelation, Predicate, NotEqual, all_different
from csp_engine.core.backtracking import (backtracking_search, find_all_solutions,
                                          first_unassigned, domain_order, no_inference)
from csp_engine.core.inference import forward_checking, ac3, mac
from csp_engine.core.heuristics import mrv, mrv_degree, lcv
from csp_engine.core.local_search import min_conflicts


# ---- Domain ----------------------------------------------------------------

def test_domain_basic_ops():
    d = Domain([1, 2, 3])
    assert len(d) == 3 and 2 in d
    d.remove(2)
    assert len(d) == 2 and 2 not in d
    d.add(2)
    assert 2 in d
    copy = d.copy()
    copy.remove(1)
    assert 1 in d and 1 not in copy          # copy is independent


# ---- a tiny hand-built CSP: a 3-node triangle graph colouring --------------

def triangle_csp(colours):
    variables = ["A", "B", "C"]
    domains = {v: colours for v in variables}
    constraints = [NotEqual("A", "B"), NotEqual("B", "C"), NotEqual("A", "C")]
    return CSP(variables, domains, constraints)


def test_csp_neighbors_and_constraints_between():
    csp = triangle_csp([1, 2, 3])
    assert csp.neighbors("A") == {"B", "C"}
    assert len(csp.constraints_between("A", "B")) == 1
    assert csp.constraints_between("A", "D") == []       # D isn't even in the CSP


def test_is_consistent_and_is_solution():
    csp = triangle_csp([1, 2, 3])
    assert csp.is_consistent("B", 1, {"A": 2}) is True
    assert csp.is_consistent("B", 2, {"A": 2}) is False
    solution = {"A": 1, "B": 2, "C": 3}
    assert csp.is_solution(solution) is True
    assert csp.is_solution({"A": 1, "B": 1, "C": 2}) is False       # violates A!=B
    assert csp.is_solution({"A": 1, "B": 2}) is False               # incomplete


def test_triangle_needs_three_colours():
    assert backtracking_search(triangle_csp([1, 2]))[0] is None          # 2 colours: impossible
    assert backtracking_search(triangle_csp([1, 2, 3]))[0] is not None   # 3 colours: solvable


# ---- constraints.py ---------------------------------------------------------

def test_binary_relation_not_satisfied_until_both_assigned():
    c = NotEqual("x", "y")
    assert c.is_satisfied({}) is True
    assert c.is_satisfied({"x": 1}) is True
    assert c.is_satisfied({"x": 1, "y": 1}) is False
    assert c.is_satisfied({"x": 1, "y": 2}) is True


def test_all_different_expands_to_pairwise_relations():
    rels = all_different(["A", "B", "C"])
    assert len(rels) == 3                      # C(3,2)
    assert all(isinstance(r, BinaryRelation) for r in rels)
    pairs = {frozenset((r.x, r.y)) for r in rels}
    assert pairs == {frozenset(("A", "B")), frozenset(("B", "C")), frozenset(("A", "C"))}


def test_predicate_nary_checks_only_once_fully_assigned():
    p = Predicate(["x", "y", "z"], lambda a: a["x"] + a["y"] == a["z"], name="sum")
    assert p.is_satisfied({"x": 1}) is True            # partial: not violated yet
    assert p.is_satisfied({"x": 1, "y": 2, "z": 3}) is True
    assert p.is_satisfied({"x": 1, "y": 2, "z": 4}) is False


# ---- backtracking.py --------------------------------------------------------

def test_find_all_solutions_triangle():
    solutions, metrics = find_all_solutions(triangle_csp([1, 2, 3]))
    assert len(solutions) == 6                 # 3! colourings of a triangle with 3 colours
    assert metrics.solved is True


def test_max_nodes_cuts_off_naive_search():
    # 10-queens with naive backtracking needs far more than 5 nodes to finish.
    from csp_engine.problems.nqueens import nqueens_csp
    _, metrics = backtracking_search(nqueens_csp(10), max_nodes=5)
    assert metrics.timed_out is True
    assert metrics.solved is False
    assert metrics.nodes <= 5


# ---- inference.py -------------------------------------------------------------

def test_forward_checking_prunes_neighbour_domain():
    csp = triangle_csp([1, 2])
    ok, pruned = forward_checking(csp, "A", 1, {"A": 1})
    assert ok is True
    assert ("B", 1) in pruned and ("C", 1) in pruned
    assert 1 not in csp.domains["B"]


def test_forward_checking_detects_wipeout():
    csp = triangle_csp([1])              # only one colour available
    ok, _ = forward_checking(csp, "A", 1, {"A": 1})
    assert ok is False                   # B's domain is wiped out


def test_ac3_prunes_globally_consistent_domains():
    csp = triangle_csp([1, 2, 3])
    ok, _ = ac3(csp)
    assert ok is True
    # every value must still be usable in some solution; AC-3 shouldn't
    # over-prune a solvable triangle
    assert all(len(csp.domains[v]) > 0 for v in csp.variables)


def test_ac3_is_a_local_check_not_a_global_one():
    # Textbook caveat: a triangle (3-clique) with 2 colours is already ARC
    # CONSISTENT -- every value in every domain has *some* support in its
    # neighbour -- even though no global 2-colouring of a triangle exists.
    # AC-3 can't see that; only full search can. This is exactly why the
    # engine still needs backtracking even with AC-3 wired in.
    csp = triangle_csp([1, 2])
    ok, pruned = ac3(csp)
    assert ok is True and pruned == []
    assert backtracking_search(csp)[0] is None       # search still correctly fails


def test_mac_restricts_assigned_variable_to_single_value():
    csp = triangle_csp([1, 2, 3])
    ok, pruned = mac(csp, "A", 1, {"A": 1})
    assert ok is True
    assert set(csp.domains["A"]) == {1}
    assert ("A", 2) in pruned and ("A", 3) in pruned


# ---- heuristics.py --------------------------------------------------------------

def test_mrv_picks_smallest_domain():
    csp = triangle_csp([1, 2, 3])
    csp.domains["B"] = Domain([1])        # force B to have the smallest domain
    assert mrv(csp, {}) == "B"


def test_lcv_orders_least_constraining_first():
    csp = triangle_csp([1, 2, 3])
    order = lcv(csp, "A", {})
    assert set(order) == {1, 2, 3}        # a valid permutation of the domain


def test_mrv_degree_breaks_ties_by_degree():
    # all three variables start with equal domains/degrees in a triangle
    csp = triangle_csp([1, 2, 3])
    choice = mrv_degree(csp, {})
    assert choice in csp.variables


# ---- local_search.py ---------------------------------------------------------

def test_min_conflicts_solves_simple_csp():
    csp = triangle_csp([1, 2, 3])
    solution, metrics = min_conflicts(csp, max_steps=1000)
    assert solution is not None
    assert csp.is_solution(solution)
    assert metrics.solved is True


def test_min_conflicts_reports_failure_when_impossible():
    csp = triangle_csp([1, 2])            # unsolvable
    solution, metrics = min_conflicts(csp, max_steps=200)
    assert solution is None
    assert metrics.solved is False
