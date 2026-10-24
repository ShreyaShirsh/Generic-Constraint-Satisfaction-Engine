"""Tests for the Custom CSP playground builder -- the piece that proves the
engine is genuinely generic by building a CSP from a raw user-supplied spec
using nothing but the primitives every preset problem already uses.
"""
import pytest

from csp_engine.core.backtracking import backtracking_search
from csp_engine.web.custom_csp import build_custom_csp, CustomCSPError


def test_builds_and_solves_a_simple_spec():
    spec = {
        "variables": ["A", "B", "C"],
        "domains": {"A": [1, 2, 3], "B": [1, 2, 3], "C": [1, 2, 3]},
        "constraints": [{"type": "all_different", "scope": ["A", "B", "C"]}],
    }
    csp = build_custom_csp(spec)
    solution, _ = backtracking_search(csp)
    assert solution is not None
    assert len(set(solution.values())) == 3


def test_sum_equals_constraint():
    spec = {
        "variables": ["X", "Y"],
        "domains": {"X": [1, 2, 3, 4], "Y": [1, 2, 3, 4]},
        "constraints": [{"type": "sum_equals", "scope": ["X", "Y"], "target": 5}],
    }
    solution, _ = backtracking_search(build_custom_csp(spec))
    assert solution is not None
    assert solution["X"] + solution["Y"] == 5


@pytest.mark.parametrize("op,a,b,expect", [
    ("not_equal", 1, 2, True), ("not_equal", 1, 1, False),
    ("equal", 1, 1, True), ("equal", 1, 2, False),
    ("less_than", 1, 2, True), ("less_than", 2, 1, False),
    ("greater_than", 2, 1, True), ("greater_than", 1, 2, False),
])
def test_binary_operators(op, a, b, expect):
    spec = {
        "variables": ["X", "Y"],
        "domains": {"X": [a], "Y": [b]},
        "constraints": [{"type": op, "scope": ["X", "Y"]}],
    }
    solution, _ = backtracking_search(build_custom_csp(spec))
    assert (solution is not None) == expect


def test_missing_variables_rejected():
    with pytest.raises(CustomCSPError):
        build_custom_csp({"domains": {}, "constraints": []})


def test_missing_domain_rejected():
    with pytest.raises(CustomCSPError):
        build_custom_csp({"variables": ["A", "B"], "domains": {"A": [1]}, "constraints": []})


def test_unknown_constraint_type_rejected():
    spec = {
        "variables": ["A", "B"], "domains": {"A": [1], "B": [1]},
        "constraints": [{"type": "nonsense", "scope": ["A", "B"]}],
    }
    with pytest.raises(CustomCSPError):
        build_custom_csp(spec)


def test_binary_constraint_with_wrong_arity_rejected():
    spec = {
        "variables": ["A", "B", "C"],
        "domains": {"A": [1], "B": [1], "C": [1]},
        "constraints": [{"type": "not_equal", "scope": ["A", "B", "C"]}],
    }
    with pytest.raises(CustomCSPError):
        build_custom_csp(spec)


def test_scope_referencing_unknown_variable_rejected():
    spec = {
        "variables": ["A", "B"], "domains": {"A": [1], "B": [1]},
        "constraints": [{"type": "not_equal", "scope": ["A", "Z"]}],
    }
    with pytest.raises(CustomCSPError):
        build_custom_csp(spec)
