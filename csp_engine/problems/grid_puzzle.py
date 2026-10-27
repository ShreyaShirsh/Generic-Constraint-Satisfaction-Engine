"""Adapter: ANY grid puzzle -> CSP, from a small declarative spec.

Sudoku, X-Sudoku, Futoshiki, KenKen, Killer Sudoku -- and whatever a user
invents in the Studio's builder -- are all the same thing to this file: a
grid of cells (the variables), a set of allowed values (the domains), and a
list of rules, each of which compiles to the engine's two primitives:

  rows / columns / boxes / diagonals / regions  -> all_different (pairwise BinaryRelation)
  inequalities  "A < B"                         -> BinaryRelation
  cages "cells sum / multiply / differ / divide to N" -> Predicate (n-ary)

Spec (all keys optional except size):
{
  "size": 9,
  "values": [1, ..., 9],                       # default 1..size
  "rules": {"rows": true, "cols": true, "boxes": [3, 3], "diagonals": false},
  "regions": [{"cells": [[r, c], ...], "label": "the L-shape"}],
  "cages": [{"cells": [[r, c], ...], "op": "+", "target": 12, "distinct": true}],
  "inequalities": [{"a": [r, c], "b": [r, c]}],       # value at a < value at b
  "givens": [[r, c, value], ...]
}
Cells are zero-based [row, col]. Cage ops: "+", "*", "-", "/", "=".
"""
from __future__ import annotations
import random
from math import prod
from ..core.model import CSP
from ..core.constraints import all_different, BinaryRelation, Predicate

Cell = tuple[int, int]
OPS = {"+", "*", "-", "/", "="}


def cell_name(cell: Cell) -> str:
    r, c = cell
    return f"R{r + 1}C{c + 1}"


def _cells(raw) -> list[Cell]:
    return [(int(r), int(c)) for r, c in raw]


def _lt(a, b):
    return a < b


# ---- cage predicates (each judges partial cages too, for early pruning) ----

def _cage_fn(op: str, target: int, size: int, values: list[int]):
    lo, hi = min(values), max(values)
    vals = set(values)

    if op == "+":
        def fn(local):
            s, filled = sum(local.values()), len(local)
            left = size - filled
            return s + left * lo <= target <= s + left * hi
    elif op == "*":
        def fn(local):
            p = prod(local.values())
            if len(local) == size:
                return p == target
            return lo < 1 or (p != 0 and target % p == 0)
    elif op == "-":
        def fn(local):
            xs = list(local.values())
            if len(xs) == 2:
                return abs(xs[0] - xs[1]) == target
            a = xs[0]
            return (a + target) in vals or (a - target) in vals
    elif op == "/":
        def fn(local):
            xs = list(local.values())
            if len(xs) == 2:
                big, small = max(xs), min(xs)
                return small != 0 and big == small * target
            a = xs[0]
            return (a * target) in vals or (a % target == 0 and a // target in vals)
    else:  # "="
        def fn(local):
            return all(v == target for v in local.values())
    return fn


def cage_label(cage: dict) -> str:
    op = cage["op"]
    symbol = {"*": "×", "/": "÷", "-": "−", "+": "+", "=": ""}[op]
    return f"the {cage['target']}{symbol} cage"


# ---- spec -> CSP ---------------------------------------------------------

def validate(spec: dict) -> None:
    size = spec.get("size")
    if not isinstance(size, int) or not 2 <= size <= 12:
        raise ValueError("size must be an integer between 2 and 12")

    def check_cell(cell, what):
        r, c = cell
        if not (0 <= r < size and 0 <= c < size):
            raise ValueError(f"{what}: cell {cell} is outside the {size}x{size} grid")

    boxes = (spec.get("rules") or {}).get("boxes")
    if boxes:
        br, bc = boxes
        if size % br or size % bc or br * bc != size:
            raise ValueError(f"boxes {br}x{bc} don't tile a {size}x{size} grid")
    for i, reg in enumerate(spec.get("regions", [])):
        for cell in reg["cells"]:
            check_cell(cell, f"region {i + 1}")
    for i, cage in enumerate(spec.get("cages", [])):
        if cage.get("op") not in OPS:
            raise ValueError(f"cage {i + 1}: op must be one of {sorted(OPS)}")
        if cage["op"] in "-/" and len(cage["cells"]) != 2:
            raise ValueError(f"cage {i + 1}: '{cage['op']}' cages need exactly 2 cells")
        if not cage["cells"]:
            raise ValueError(f"cage {i + 1}: a cage needs at least one cell")
        for cell in cage["cells"]:
            check_cell(cell, f"cage {i + 1}")
    for ineq in spec.get("inequalities", []):
        check_cell(ineq["a"], "inequality")
        check_cell(ineq["b"], "inequality")
    for r, c, v in spec.get("givens", []):
        check_cell((r, c), "given")


def grid_puzzle_csp(spec: dict, include_givens: bool = True) -> CSP:
    validate(spec)
    size = spec["size"]
    values = list(spec.get("values") or range(1, size + 1))
    rules = spec.get("rules") or {}
    cells: list[Cell] = [(r, c) for r in range(size) for c in range(size)]

    domains = {cell: set(values) for cell in cells}
    if include_givens:
        for r, c, v in spec.get("givens", []):
            domains[(r, c)] = {v}

    groups: list[tuple[str, list[Cell]]] = []
    if rules.get("rows"):
        groups += [(f"row {r + 1}", [(r, c) for c in range(size)]) for r in range(size)]
    if rules.get("cols"):
        groups += [(f"column {c + 1}", [(r, c) for r in range(size)]) for c in range(size)]
    if rules.get("boxes"):
        br, bc = rules["boxes"]
        k = 0
        for r0 in range(0, size, br):
            for c0 in range(0, size, bc):
                k += 1
                groups.append((f"box {k}", [(r, c) for r in range(r0, r0 + br)
                                            for c in range(c0, c0 + bc)]))
    if rules.get("diagonals"):
        groups.append(("the main diagonal", [(i, i) for i in range(size)]))
        groups.append(("the anti-diagonal", [(i, size - 1 - i) for i in range(size)]))
    for i, reg in enumerate(spec.get("regions", [])):
        groups.append((reg.get("label") or f"region {i + 1}", _cells(reg["cells"])))

    cages = spec.get("cages", [])
    for cage in cages:
        if cage.get("distinct"):
            groups.append((cage_label(cage), _cells(cage["cells"])))

    constraints = []
    seen: set[frozenset] = set()
    for label, members in groups:
        for rel in all_different(members, label=label):
            key = frozenset((rel.x, rel.y))
            if key not in seen:          # a row and a box can share a pair
                seen.add(key)
                constraints.append(rel)

    for cage in cages:
        scope = _cells(cage["cells"])
        constraints.append(Predicate(
            scope, _cage_fn(cage["op"], int(cage["target"]), len(scope), values),
            name="Cage", check_when_partial=True, label=cage_label(cage)))

    for ineq in spec.get("inequalities", []):
        a, b = tuple(ineq["a"]), tuple(ineq["b"])
        constraints.append(BinaryRelation(a, b, _lt, name="LessThan",
                                          label=f"{cell_name(a)} < {cell_name(b)}"))

    return CSP(cells, domains, constraints, groups=groups)


def givens_of(spec: dict) -> dict[Cell, int]:
    return {(r, c): v for r, c, v in spec.get("givens", [])}


def with_givens(spec: dict, givens: dict[Cell, int]) -> dict:
    out = dict(spec)
    out["givens"] = sorted([[r, c, v] for (r, c), v in givens.items()])
    return out


# ---- rule sets for the built-in puzzle types --------------------------------

BOX_SHAPES = {4: [2, 2], 6: [2, 3], 8: [2, 4], 9: [3, 3]}


def sudoku_rules(size: int = 9, diagonals: bool = False) -> dict:
    return {"size": size, "type": "x-sudoku" if diagonals else "sudoku",
            "rules": {"rows": True, "cols": True, "boxes": BOX_SHAPES[size],
                      "diagonals": diagonals}}


def latin_rules(size: int) -> dict:
    return {"size": size, "rules": {"rows": True, "cols": True}}


def _random_latin(size: int, rng: random.Random) -> dict[Cell, int]:
    from ..core.generator import random_solution
    return random_solution(grid_puzzle_csp(latin_rules(size)), rng)


def _neighbours(cell: Cell, size: int):
    r, c = cell
    for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        if 0 <= r + dr < size and 0 <= c + dc < size:
            yield (r + dr, c + dc)


def _partition(solution: dict[Cell, int], size: int, rng: random.Random,
               max_size: int, distinct: bool) -> list[list[Cell]]:
    """Randomly carve the grid into connected cages of 1..max_size cells."""
    free = {(r, c) for r in range(size) for c in range(size)}
    cages = []
    while free:
        start = rng.choice(sorted(free))
        want = rng.choices(range(1, max_size + 1),
                           weights=[1] + [3] * (max_size - 1))[0]
        cage = [start]
        free.discard(start)
        while len(cage) < want:
            options = [n for cell in cage for n in _neighbours(cell, size) if n in free
                       and not (distinct and solution[n] in {solution[x] for x in cage})]
            if not options:
                break
            nxt = rng.choice(options)
            cage.append(nxt)
            free.discard(nxt)
        cages.append(cage)
    return cages


def futoshiki_rules(size: int, rng: random.Random, density: float = 0.35) -> dict:
    sol = _random_latin(size, rng)
    inequalities = []
    for r in range(size):
        for c in range(size):
            for n in ((r, c + 1), (r + 1, c)):
                if n[0] < size and n[1] < size and rng.random() < density:
                    a, b = ((r, c), n) if sol[(r, c)] < sol[n] else (n, (r, c))
                    inequalities.append({"a": list(a), "b": list(b)})
    spec = latin_rules(size)
    spec.update(type="futoshiki", inequalities=inequalities)
    return spec


def kenken_rules(size: int, rng: random.Random) -> dict:
    sol = _random_latin(size, rng)
    cages = []
    for cells in _partition(sol, size, rng, max_size=3 if size <= 4 else 4, distinct=False):
        vals = [sol[c] for c in cells]
        if len(cells) == 1:
            op, target = "=", vals[0]
        elif len(cells) == 2:
            big, small = max(vals), min(vals)
            if big % small == 0 and rng.random() < 0.5:
                op, target = "/", big // small
            else:
                op, target = rng.choice([("-", big - small), ("+", big + small),
                                         ("*", big * small)])
        else:
            op, target = rng.choice([("+", sum(vals)), ("*", prod(vals))])
        cages.append({"cells": [list(c) for c in cells], "op": op, "target": target})
    spec = latin_rules(size)
    spec.update(type="kenken", cages=cages)
    return spec


def killer_rules(size: int, rng: random.Random) -> dict:
    from ..core.generator import random_solution
    sol = random_solution(grid_puzzle_csp(sudoku_rules(size)), rng)
    cages = [{"cells": [list(c) for c in cells], "op": "+",
              "target": sum(sol[c] for c in cells), "distinct": True}
             for cells in _partition(sol, size, rng, max_size=4, distinct=True)]
    spec = sudoku_rules(size)
    spec.update(type="killer", cages=cages)
    return spec


def rules_for(kind: str, size: int, rng: random.Random) -> dict:
    if kind == "sudoku":
        return sudoku_rules(size)
    if kind == "x-sudoku":
        return sudoku_rules(size, diagonals=True)
    if kind == "futoshiki":
        return futoshiki_rules(size, rng)
    if kind == "kenken":
        return kenken_rules(size, rng)
    if kind == "killer":
        return killer_rules(size, rng)
    raise ValueError(f"unknown puzzle type '{kind}'")


def generate_puzzle(kind: str, size: int, target_level: int | None = None,
                    seed: int | None = None, time_budget: float = 8.0) -> dict:
    """Rules for a built-in type + the generic generator = a playable puzzle."""
    from ..core.generator import generate
    rng = random.Random(seed)
    spec = rules_for(kind, size, rng)
    result = generate(grid_puzzle_csp(spec), target_level, rng, time_budget)
    return {
        "spec": with_givens(spec, result["givens"]),
        "solution": result["solution"],
        "grade": result["grade"],
        "stats": result["stats"],
    }
