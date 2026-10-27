"""Ready-made puzzles for the Studio, produced by the generic generator with
fixed seeds and stored in puzzle_presets.json so the page loads instantly.

Regenerate:  python -m csp_engine.problems.puzzle_presets
"""
from __future__ import annotations
import json
import os
from .grid_puzzle import generate_puzzle, sudoku_rules, grid_puzzle_csp, givens_of
from .sudoku import EASY_9x9
from ..core.explain import grade

PATH = os.path.join(os.path.dirname(__file__), "puzzle_presets.json")

# (id, display name, type, size, target level, seed)
RECIPES = [
    ("sudoku-medium", "Sudoku · Medium",        "sudoku",    9, 2, 11),
    ("sudoku-hard",   "Sudoku · Hard",          "sudoku",    9, 3, 1),
    ("sudoku-expert", "Sudoku · Expert",        "sudoku",    9, 4, 3),
    ("x-sudoku",      "X-Sudoku (diagonals)",   "x-sudoku",  9, None, 4),
    ("mini-sudoku",   "Mini Sudoku 6×6",        "sudoku",    6, 2, 5),
    ("futoshiki-5",   "Futoshiki 5×5",          "futoshiki", 5, 3, 6),
    ("kenken-4",      "KenKen 4×4",             "kenken",    4, None, 7),
    ("kenken-6",      "KenKen 6×6",             "kenken",    6, None, 8),
    ("killer-6",      "Killer Sudoku 6×6",      "killer",    6, None, 9),
    ("killer-9",      "Killer Sudoku 9×9",      "killer",    9, None, 10),
]


def _classic_easy() -> dict:
    spec = sudoku_rules(9)
    spec["givens"] = [[r, c, EASY_9x9[r][c]] for r in range(9) for c in range(9) if EASY_9x9[r][c]]
    g = grade(grid_puzzle_csp(spec, include_givens=False), givens_of(spec))
    return {"id": "sudoku-easy", "name": "Sudoku · Easy (classic)", "spec": spec, "grade": g.as_dict()}


def build() -> list[dict]:
    presets = [_classic_easy()]
    for pid, name, kind, size, level, seed in RECIPES:
        result = generate_puzzle(kind, size, level, seed=seed, time_budget=20)
        presets.append({"id": pid, "name": name, "spec": result["spec"],
                        "grade": result["grade"].as_dict()})
        print(f"  {name:<26} {result['grade'].name:<7} givens={len(result['spec']['givens'])}")
    return presets


def load() -> list[dict]:
    with open(PATH, encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    data = build()
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(data, f)
    print(f"wrote {len(data)} presets to {PATH}")
