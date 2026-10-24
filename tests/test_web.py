"""Tests for the Flask demo server -- these only check that each route is
correct HTTP plumbing (builds the right adapter, returns the right shape).
No route may contain search logic, so there is nothing problem-specific to
test beyond "did the right adapter get called with the right data".
"""
import pytest

from csp_engine.web.app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_index_page_loads(client):
    res = client.get("/")
    assert res.status_code == 200
    assert b"Generic" in res.data


def test_nqueens_endpoint(client):
    res = client.post("/api/solve/nqueens", json={"n": 6, "algorithm": "mac_mrv"})
    data = res.get_json()
    assert res.status_code == 200
    assert data["metrics"]["solved"] is True
    assert len(data["queens"]) == 6


def test_nqueens_rejects_out_of_range_n(client):
    res = client.post("/api/solve/nqueens", json={"n": 1000})
    assert res.status_code == 400


def test_graph_colouring_endpoint_default_preset(client):
    res = client.post("/api/solve/graph-colouring", json={"algorithm": "mac_mrv"})
    data = res.get_json()
    assert res.status_code == 200
    assert data["assignment"] is not None
    assert set(data["assignment"]) == set(data["adjacency"])


def test_sudoku_endpoint_default_preset(client):
    res = client.post("/api/solve/sudoku", json={"algorithm": "mac_mrv"})
    data = res.get_json()
    assert res.status_code == 200
    assert data["grid"] is not None
    assert len(data["grid"]) == 9 and len(data["grid"][0]) == 9


def test_cryptarithmetic_endpoint(client):
    res = client.post("/api/solve/cryptarithmetic", json={
        "addend1": "SEND", "addend2": "MORE", "result": "MONEY", "algorithm": "mac_mrv",
    })
    data = res.get_json()
    assert res.status_code == 200
    assert data["equation"] is not None


def test_zebra_endpoint(client):
    res = client.post("/api/solve/zebra", json={"algorithm": "mac_mrv"})
    data = res.get_json()
    assert res.status_code == 200
    assert len(data["houses"]) == 5


def test_exam_scheduling_endpoint_default_preset(client):
    res = client.post("/api/solve/exam-scheduling", json={"algorithm": "mac_mrv"})
    data = res.get_json()
    assert res.status_code == 200
    assert data["assignment"] is not None


def test_custom_csp_endpoint(client):
    spec = {
        "variables": ["A", "B"],
        "domains": {"A": [1, 2], "B": [1, 2]},
        "constraints": [{"type": "not_equal", "scope": ["A", "B"]}],
        "algorithm": "mac_mrv",
    }
    res = client.post("/api/solve/custom", json=spec)
    data = res.get_json()
    assert res.status_code == 200
    assert data["assignment"]["A"] != data["assignment"]["B"]


def test_custom_csp_endpoint_rejects_bad_spec(client):
    res = client.post("/api/solve/custom", json={"variables": [], "domains": {}})
    assert res.status_code == 400
    assert "error" in res.get_json()


def test_benchmark_endpoint_returns_rows(client):
    res = client.get("/api/benchmark")
    assert res.status_code == 200
    rows = res.get_json()
    assert isinstance(rows, list) and len(rows) > 0
    assert {"problem", "technique", "nodes"} <= rows[0].keys()
