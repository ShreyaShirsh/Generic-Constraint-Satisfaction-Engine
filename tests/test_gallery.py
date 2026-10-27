"""Smoke tests for every problem page's API (/api/p/<problem>/<action>) and
the pages themselves. Each problem's own correctness is tested in
test_gallery_engine.py; these check the HTTP plumbing end to end."""
import pytest

from csp_engine.web.app import app
from csp_engine.web.catalog import P


@pytest.fixture(scope="module")
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def post(client, pid, action, body=None):
    res = client.post(f"/api/p/{pid}/{action}", json=body or {})
    assert res.status_code == 200, (pid, action, res.get_json())
    return res.get_json()


def test_home_and_every_problem_page(client):
    assert b"One engine" in client.get("/").data
    assert client.get("/engine").status_code == 200
    for p in P:
        assert client.get(f"/p/{p['id']}").status_code == 200, p["id"]
    assert client.get("/p/nonsense").status_code == 404


def test_catalog_lists_thirty_problems(client):
    data = client.get("/api/p/catalog").get_json()
    assert len(data["problems"]) == 30 and len(data["categories"]) == 6


def test_reasoning(client):
    z = post(client, "zebra", "new", {"mode": "classic"})["inst"]
    sol = post(client, "zebra", "solve", {"inst": z})
    assert sol["solution"]["pet|Zebra"] == sol["solution"]["nation|Japanese"]
    assert post(client, "zebra", "hint", {"inst": z, "entries": []})["kind"] in ("single", "hidden")
    g = post(client, "zebra", "new", {"houses": 4, "categories": 4, "seed": 1})["inst"]
    assert post(client, "zebra", "trace", {"inst": g, "algorithm": "smart"})["metrics"]["solved"]

    c = post(client, "crypto", "new", {"mode": "classic", "index": 0})["inst"]
    assert post(client, "crypto", "solve", {"inst": c})["solution"]["M"] == 1
    assert post(client, "crypto", "new", {"mode": "custom", "words": "TO + GO = OUT"})["inst"]["result"] == "OUT"

    k = post(client, "knights", "new", {"people": 3, "seed": 2})["inst"]
    assert post(client, "knights", "solve", {"inst": k})["solution"]

    m = post(client, "minesweeper", "new", {"rows": 9, "cols": 9, "mines": 10, "first": [4, 4], "seed": 1})
    assert len(m["mines"]) == 10 and [4, 4] not in m["mines"]
    a = post(client, "minesweeper", "assist", {"rows": 9, "cols": 9, "mines": 10, "revealed": [[0, 0, 1]]})
    assert a["kind"] in ("certain", "guess")
    assert "won" in post(client, "minesweeper", "autoplay", {"seed": 3})


def test_search(client):
    m = post(client, "maze", "new", {"rows": 11, "cols": 11, "seed": 1})
    assert post(client, "maze", "solve", m)["plan"]
    e = post(client, "eight", "new", {"moves": 12, "seed": 1})
    assert len(post(client, "eight", "solve", e)["plan"]) <= 12
    assert len(post(client, "hanoi", "solve", {"disks": 4, "heuristic": "exact"})["plan"]) == 15
    assert len(post(client, "river", "solve", {"variant": "fwgc"})["plan"]) == 7
    lv = post(client, "sokoban", "levels")["levels"][1]["map"]
    assert post(client, "sokoban", "solve", {"map": lv})["plan"]


def test_strategy(client):
    r = post(client, "connect4", "move", {"cols": [[1], [], [], [], [], [], []], "to_move": 2, "depth": 3})
    assert 0 <= r["move"] <= 6
    assert post(client, "nim", "analyse", {"heaps": [3, 4, 5]})["winning_moves"] == [[0, 2]]
    board = [0] * 64
    board[27] = board[36] = 2
    board[28] = board[35] = 1
    assert post(client, "othello", "move", {"board": board, "to_move": 2, "depth": 2})["move"] is not None
    assert post(client, "hex", "prove", {"n": 3})["winning_first_moves"]
    p = post(client, "chess", "puzzles")["puzzles"][3]
    s = post(client, "chess", "solve", p)
    assert s["win"] and s["san"][-1].endswith("#")
    assert post(client, "chess", "try", {**p, "move": s["line"][0]})["wins"]


def test_graphs(client):
    inst = post(client, "map", "new", {"regions": 8, "seed": 1})["inst"]
    assert post(client, "map", "solve", {"inst": inst})["solution"]
    assert post(client, "map", "chromatic", {"inst": inst})["k"] <= 4
    c = post(client, "tsp", "new", {"n": 6, "seed": 1})
    assert post(client, "tsp", "solve", c)["optimal"]
    g = post(client, "shortest", "new", {"n": 12, "seed": 1})
    r = post(client, "shortest", "solve", g)
    assert abs(r["cost"] - r["dijkstra"]["cost"]) < 1e-6
    e = post(client, "exam", "new", {"seed": 1})
    assert post(client, "exam", "solve", {"inst": e["inst"]})["solution"]
    k = post(client, "knapsack", "new", {"n": 10, "seed": 1})
    assert post(client, "knapsack", "solve", k)["value"] >= post(client, "knapsack", "solve", k)["greedy"]["value"]


def test_planning(client):
    t = post(client, "treasure", "new", {"treasures": 3, "seed": 1})
    assert post(client, "treasure", "solve", t)["path"]
    gw = post(client, "gridworld", "new", {"seed": 1})
    assert post(client, "gridworld", "plan", gw)["best"]
    assert post(client, "gridworld", "learn", {"inst": gw, "episodes": 50})["returns"]
    pr = post(client, "resource", "new", {"tasks": 6, "seed": 1})
    assert post(client, "resource", "solve", pr)["starts"]
    mp = post(client, "mapf", "new", {"agents": 3, "seed": 1})
    assert post(client, "mapf", "solve", mp)["paths"]


def test_spatial(client):
    sq = post(client, "tangram", "new", {"mode": "Square"})
    assert len(post(client, "tangram", "solve", sq)["pieces"]) == 7
    cube = post(client, "rubiks", "new", {"moves": 5, "seed": 1})
    assert len(post(client, "rubiks", "solve", {"state": cube["state"]})["plan"]) <= 5
    j = post(client, "jigsaw", "new", {"n": 3, "seed": 1})
    assert post(client, "jigsaw", "solve", {"inst": j})["solution"]
    pz = post(client, "polyomino", "new", {"mode": "5×6 rectangle"})
    assert post(client, "polyomino", "solve", pz)["pieces"]
    assert post(client, "folding", "check", {"cells": [[1, 0], [1, 1], [1, 2], [1, 3], [0, 1], [2, 1]]})["folds"]
    assert sum(x["folds"] for x in post(client, "folding", "all")["hexominoes"]) == 11


def test_bad_requests(client):
    assert client.post("/api/p/hanoi/solve", json={"disks": 50}).status_code == 400
    assert client.post("/api/p/nope/solve", json={}).status_code == 404
