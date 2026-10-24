"""Adapter: the Zebra / Einstein logic puzzle -> CSP.

This is the relational-constraint demonstration promised in the project
abstract — "the Englishman lives in the red house", "the green house is
immediately to the right of the ivory house" — and it reuses nothing but
BinaryRelation, the exact same primitive N-Queens uses for "no shared
diagonal" and Sudoku uses for "no shared digit". Only the predicate changes.

Encoding:
  Five houses (1-5) in a row. Five categories (nationality, colour, drink,
  smoke, pet), five values each. variables = every (category, value) pair,
  e.g. ("nation", "English"); domain = which house (1-5) holds that value.

  constraints:
    - within a category, all 5 values sit in different houses
      (all_different -- a bijection value<->house)
    - each clue becomes one relation between two variables:
        same_house(a, b)   "the Englishman lives in the red house"
        right_of(a, b)     "green is immediately right of ivory"
        next_to(a, b)      "the man with the fox lives next to the doctor"
        houses_apart(a,b,k) generalisation used nowhere here but offered
                             for completeness (k=0 is same_house)

The puzzle itself (which clues exist) is fixed data, same as a Sudoku clue
grid is fixed data -- the engine doesn't change to accommodate it.
"""
from __future__ import annotations
from ..core.model import CSP, Var
from ..core.constraints import all_different, BinaryRelation

HOUSES = [1, 2, 3, 4, 5]

CATEGORIES: dict[str, list[str]] = {
    "nation": ["English", "Spaniard", "Ukrainian", "Norwegian", "Japanese"],
    "colour": ["Red", "Green", "Ivory", "Yellow", "Blue"],
    "drink":  ["Coffee", "Tea", "Milk", "OrangeJuice", "Water"],
    "smoke":  ["OldGold", "Kools", "Chesterfields", "LuckyStrike", "Parliaments"],
    "pet":    ["Dog", "Snails", "Fox", "Horse", "Zebra"],
}


def same_house(a: Var, b: Var) -> BinaryRelation:
    return BinaryRelation(a, b, lambda x, y: x == y, name="SameHouse")


def right_of(a: Var, b: Var) -> BinaryRelation:
    """a is immediately to the right of b."""
    return BinaryRelation(a, b, lambda x, y: x == y + 1, name="RightOf")


def next_to(a: Var, b: Var) -> BinaryRelation:
    return BinaryRelation(a, b, lambda x, y: abs(x - y) == 1, name="NextTo")


def v(category: str, value: str) -> Var:
    return (category, value)


def zebra_csp() -> CSP:
    variables: list[Var] = [v(cat, val) for cat, vals in CATEGORIES.items() for val in vals]
    domains = {var: set(HOUSES) for var in variables}

    constraints = []
    for cat, vals in CATEGORIES.items():
        constraints.extend(all_different([v(cat, val) for val in vals]))

    clues = [
        same_house(v("nation", "English"),    v("colour", "Red")),
        same_house(v("nation", "Spaniard"),    v("pet", "Dog")),
        same_house(v("drink", "Coffee"),       v("colour", "Green")),
        same_house(v("nation", "Ukrainian"),   v("drink", "Tea")),
        right_of(v("colour", "Green"),         v("colour", "Ivory")),
        same_house(v("smoke", "OldGold"),      v("pet", "Snails")),
        same_house(v("smoke", "Kools"),        v("colour", "Yellow")),
    ]
    constraints.extend(clues)

    # "milk is drunk in the middle house" and "the Norwegian lives in the
    # first house" fix a value directly -- cheapest as a unary domain trim.
    domains[v("drink", "Milk")] = {3}
    domains[v("nation", "Norwegian")] = {1}

    constraints += [
        next_to(v("smoke", "Chesterfields"), v("pet", "Fox")),
        next_to(v("smoke", "Kools"),         v("pet", "Horse")),
        same_house(v("smoke", "LuckyStrike"), v("drink", "OrangeJuice")),
        same_house(v("nation", "Japanese"),  v("smoke", "Parliaments")),
        next_to(v("nation", "Norwegian"),    v("colour", "Blue")),
    ]

    return CSP(variables, domains, constraints)


def describe(solution: dict) -> str:
    by_house = {h: {} for h in HOUSES}
    for (cat, val), house in solution.items():
        by_house[house][cat] = val
    lines = []
    for h in HOUSES:
        row = by_house[h]
        lines.append(f"House {h}: {row.get('nation','?'):<10} {row.get('colour','?'):<7} "
                     f"{row.get('drink','?'):<12} {row.get('smoke','?'):<14} {row.get('pet','?')}")
    return "\n".join(lines)


def who_owns_zebra(solution: dict) -> str:
    for (cat, val), house in solution.items():
        if cat == "pet" and val == "Zebra":
            owner_house = house
    for (cat, val), house in solution.items():
        if cat == "nation" and house == owner_house:
            return val
    raise RuntimeError("no solution assigned a zebra owner")


if __name__ == "__main__":      # self-test (fixed puzzle, known-unique answer)
    from ..core.backtracking import backtracking_search
    from ..core.inference import mac
    from ..core.heuristics import mrv

    csp = zebra_csp()
    solution, metrics = backtracking_search(csp, select_var=mrv, inference=mac)
    assert solution is not None and csp.is_solution(solution)
    owner = who_owns_zebra(solution)
    assert owner == "Japanese", f"expected Japanese, got {owner}"
    print("zebra self-test passed. The zebra owner is:", owner)
    print(describe(solution))
    print(metrics.summary())
