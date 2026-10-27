"""Tests for the Puzzle Studio HTTP routes (plumbing only)."""
import pytest

from csp_engine.web.app import app
from csp_engine.problems import puzzle_presets
from csp_engine.problems.grid_puzzle import sudoku_rules
from csp_engine.problems.sudoku import EASY_9x9


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def easy_spec():
    spec = sudoku_rules(9)
    spec["givens"] = [[r, c, EASY_9x9[r][c]] for r in range(9) for c in range(9) if EASY_9x9[r][c]]
    return spec


def test_studio_page_loads(client):
    res = client.get("/studio")
    assert res.status_code == 200 and b"Puzzle Studio" in res.data


def test_presets(client):
    data = client.get("/api/studio/presets").get_json()
    assert len(data) == len(puzzle_presets.load()) and data[0]["spec"]["size"] == 9


def test_trace_grid_and_queens(client):
    res = client.post("/api/studio/trace", json={"puzzle": {"kind": "grid", "spec": easy_spec()},
                                                 "algorithm": "smart"}).get_json()
    assert res["metrics"]["solved"] and res["events"][-1][0] == "s"
    assert len(res["vars"]) == 81 and "0,0" in res["initial"]

    res = client.post("/api/studio/trace", json={"puzzle": {"kind": "nqueens", "n": 6},
                                                 "algorithm": "naive"}).get_json()
    assert res["metrics"]["solved"]


def test_trace_rejects_unknown_algorithm(client):
    res = client.post("/api/studio/trace", json={"puzzle": {"kind": "grid", "spec": easy_spec()},
                                                 "algorithm": "magic"})
    assert res.status_code == 400


def test_check_flags_conflicts(client):
    res = client.post("/api/studio/check", json={"spec": easy_spec(), "entries": [[0, 2, 5]]}).get_json()
    assert res["conflicts"] and not res["solved"]


def test_hint_flow(client):
    res = client.post("/api/studio/hint", json={"spec": easy_spec(), "entries": []}).get_json()
    assert res["kind"] == "single" and res["level"] == 1 and res["value"] == 5

    res = client.post("/api/studio/hint", json={"spec": easy_spec(), "entries": [[0, 2, 5]]}).get_json()
    assert res["kind"] == "conflict"

    solution = client.post("/api/studio/solve", json={"spec": easy_spec()}).get_json()["solution"]
    r, c, v = next(x for x in solution if (x[0], x[1]) == (2, 0))
    wrong = next(w for w in range(1, 10) if w != v and w not in (8, 9, 6, 4, 7, 5))
    res = client.post("/api/studio/hint", json={"spec": easy_spec(), "entries": [[2, 0, wrong]]}).get_json()
    assert res["kind"] in ("mistake", "conflict")


def test_candidates(client):
    res = client.post("/api/studio/candidates", json={"spec": easy_spec(), "entries": []}).get_json()
    assert res["candidates"]["4,4"] == [5]


def test_generate_analyze_make(client):
    res = client.post("/api/studio/generate", json={"type": "sudoku", "size": 4}).get_json()
    assert res["grade"]["name"] in ("Easy", "Medium", "Hard", "Expert")

    analysis = client.post("/api/studio/analyze", json={"spec": res["spec"]}).get_json()
    assert analysis["solutions"] == 1 and analysis["grade"]
    assert analysis["compiled"]["variables"] == 16

    rules = {"size": 5, "rules": {"rows": True, "cols": True, "diagonals": True}}
    made = client.post("/api/studio/make", json={"spec": rules, "difficulty": "any"}).get_json()
    again = client.post("/api/studio/analyze", json={"spec": made["spec"]}).get_json()
    assert again["solutions"] == 1


def test_make_rejects_impossible_rules(client):
    spec = {"size": 4, "rules": {"rows": True}, "givens": [[0, 0, 1], [0, 1, 1]]}
    res = client.post("/api/studio/make", json={"spec": spec})
    assert res.status_code == 400


def test_bad_spec_is_400(client):
    assert client.post("/api/studio/check", json={"spec": {"size": 99}}).status_code == 400
    assert client.post("/api/studio/hint", json={}).status_code == 400
