"""Logic puzzles with generators: Zebra / Einstein riddles and Knights &
Knaves. Each clue or statement becomes ONE constraint whose label is the
clue's own text, so when the coach explains a step it can say exactly which
clue forced it.

Generation is the same idea as the grid generator, but over constraints
instead of givens: pick a random hidden answer, write true clues about it,
add clues until the answer is the only one left (proved by the engine
counting solutions), then delete every clue that turns out to be redundant.
"""
from __future__ import annotations
import random
from itertools import combinations
from ..core.model import CSP
from ..core.constraints import all_different, BinaryRelation, Predicate
from ..core.generator import count_solutions
from ..core.explain import grade

# ============================================================== Zebra / Einstein ====

ZEBRA_CATEGORIES = {
    "nation": ["English", "Spaniard", "Ukrainian", "Norwegian", "Japanese"],
    "colour": ["Red", "Green", "Ivory", "Yellow", "Blue"],
    "drink":  ["Coffee", "Tea", "Milk", "Juice", "Water"],
    "smoke":  ["Old Gold", "Kools", "Chesterfield", "Lucky Strike", "Parliament"],
    "pet":    ["Dog", "Snails", "Fox", "Horse", "Zebra"],
}
CATEGORY_LABEL = {"nation": "nationalities", "colour": "house colours", "drink": "drinks",
                  "smoke": "cigarette brands", "pet": "pets"}


def phrase(cat: str, val: str) -> str:
    """How a riddle refers to the holder of a value."""
    return {
        "nation": f"the {val}{'man' if val == 'English' else ''}",
        "colour": f"the {val.lower()} house",
        "drink": f"the {val.lower()} drinker",
        "smoke": f"the {val} smoker",
        "pet": f"the {val.lower()} owner" if val not in ("Snails",) else "the snail keeper",
    }[cat]


def _cap(s: str) -> str:
    return s[0].upper() + s[1:]


def _same(a, b): return a == b
def _diff(a, b): return a != b
def _right(a, b): return a == b + 1
def _next(a, b): return abs(a - b) == 1
def _left_of(a, b): return a < b


CLUE_KINDS = {"same": _same, "diff": _diff, "right": _right, "next": _next, "left_of": _left_of}

# The classic 1962 puzzle (water/zebra are the questions, so they get no clue).
CLASSIC_CLUES = [
    ("same", ("nation", "English"), ("colour", "Red")),
    ("same", ("nation", "Spaniard"), ("pet", "Dog")),
    ("same", ("drink", "Coffee"), ("colour", "Green")),
    ("same", ("nation", "Ukrainian"), ("drink", "Tea")),
    ("right", ("colour", "Green"), ("colour", "Ivory")),
    ("same", ("smoke", "Old Gold"), ("pet", "Snails")),
    ("same", ("smoke", "Kools"), ("colour", "Yellow")),
    ("at", ("drink", "Milk"), 3),
    ("at", ("nation", "Norwegian"), 1),
    ("next", ("smoke", "Chesterfield"), ("pet", "Fox")),
    ("next", ("smoke", "Kools"), ("pet", "Horse")),
    ("same", ("smoke", "Lucky Strike"), ("drink", "Juice")),
    ("same", ("nation", "Japanese"), ("smoke", "Parliament")),
    ("next", ("nation", "Norwegian"), ("colour", "Blue")),
]


def _where(h: int, houses: int) -> str:
    if houses % 2 and h == (houses + 1) // 2:
        return "the middle house"
    return "the first house" if h == 1 else f"house {h}"


def clue_text(clue, houses: int) -> str:
    kind, a = clue[0], tuple(clue[1])
    if kind == "at":
        h = clue[2]
        if a[0] == "colour":
            return f"{_cap(phrase(*a))} is {_where(h, houses)}."
        return f"{_cap(phrase(*a))} lives in {_where(h, houses)}."
    b = tuple(clue[2])
    if kind in ("same", "diff") and "colour" in (a[0], b[0]):
        person, house = (b, a) if a[0] == "colour" else (a, b)
        verb = "lives" if kind == "same" else "does not live"
        return f"{_cap(phrase(*person))} {verb} in {phrase(*house)}."
    A, B = phrase(*a), phrase(*b)
    return {
        "same": f"{_cap(A)} lives in the same house as {B}.",
        "diff": f"{_cap(A)} and {B} live in different houses.",
        "right": f"{_cap(A)} is immediately to the right of {B}.",
        "next": f"{_cap(A)} is next to {B}.",
        "left_of": f"{_cap(A)} is somewhere to the left of {B}.",
    }[kind]


def zebra_csp(categories: dict, houses: int, clues: list) -> CSP:
    variables = [(cat, val) for cat, vals in categories.items() for val in vals]
    domains = {v: list(range(1, houses + 1)) for v in variables}
    constraints, groups = [], []
    for cat, vals in categories.items():
        label = f"the {CATEGORY_LABEL.get(cat, cat)}"
        members = [(cat, v) for v in vals]
        constraints += all_different(members, label=label)
        groups.append((label, members))
    for i, clue in enumerate(clues, 1):
        text = f"clue {i} (“{clue_text(clue, houses)}”)"
        if clue[0] == "at":
            h = clue[2]
            constraints.append(Predicate([tuple(clue[1])], lambda l, h=h: all(x == h for x in l.values()),
                                         name="InHouse", label=text, check_when_partial=True))
        else:
            fn = CLUE_KINDS[clue[0]]
            constraints.append(BinaryRelation(tuple(clue[1]), tuple(clue[2]), fn,
                                              name=clue[0].title(), label=text))
    return CSP(variables, domains, constraints, groups=groups)


def classic_zebra() -> dict:
    return {"houses": 5, "categories": ZEBRA_CATEGORIES,
            "clues": [list(c) for c in CLASSIC_CLUES],
            "question": ["pet", "Zebra"], "name": "Einstein's riddle (1962)"}


def _true_clues(solution: dict, categories: dict, houses: int) -> list:
    variables = list(solution)
    out = []
    for a, b in combinations(variables, 2):
        if a[0] == b[0]:
            continue
        ha, hb = solution[a], solution[b]
        if ha == hb:
            out.append(("same", a, b))
        else:
            out.append(("diff", a, b))
        if ha == hb + 1:
            out.append(("right", a, b))
        if hb == ha + 1:
            out.append(("right", b, a))
        if abs(ha - hb) == 1:
            out.append(("next", a, b))
        if ha < hb:
            out.append(("left_of", a, b))
        elif hb < ha:
            out.append(("left_of", b, a))
    for v in variables:
        out.append(("at", v, solution[v]))
    return out


def generate_zebra(houses: int = 5, n_categories: int = 5, seed: int | None = None) -> dict:
    """Invent a brand-new riddle with exactly one answer."""
    rng = random.Random(seed)
    cats = list(ZEBRA_CATEGORIES)[:n_categories]
    categories = {c: rng.sample(ZEBRA_CATEGORIES[c], houses) for c in cats}
    solution = {}
    for cat, vals in categories.items():
        order = list(range(1, houses + 1))
        rng.shuffle(order)
        for v, h in zip(vals, order):
            solution[(cat, v)] = h

    pool = _true_clues(solution, categories, houses)
    weights = {"same": 6, "next": 4, "right": 3, "left_of": 2, "diff": 1, "at": 1}
    rng.shuffle(pool)
    pool.sort(key=lambda c: -weights[c[0]] * rng.random())

    question = rng.choice([v for v in solution if v[0] == cats[-1]])
    pool = [c for c in pool if not (c[0] == "at" and question in c[1:])]

    def good(cs) -> bool:
        """Unique AND solvable by pure logic (no guessing), so it's fun."""
        csp = zebra_csp(categories, houses, cs)
        return count_solutions(csp, limit=2, budget=20_000) == 1 and grade(csp, {}).solved_by_logic

    clues: list = []
    for clue in pool:
        clues.append(clue)
        if len(clues) >= houses * 2 and good(clues):
            break
    # drop every clue that turns out to be unnecessary
    i = 0
    while i < len(clues):
        trial = clues[:i] + clues[i + 1:]
        if good(trial):
            clues = trial
        else:
            i += 1
    return {"houses": houses, "categories": categories,
            "clues": [[c[0], list(c[1]), (list(c[2]) if isinstance(c[2], tuple) else c[2])] for c in clues],
            "question": list(question), "name": "Generated riddle"}


def zebra_from_instance(inst: dict) -> CSP:
    clues = [(c[0], tuple(c[1]), tuple(c[2]) if isinstance(c[2], list) else c[2]) for c in inst["clues"]]
    return zebra_csp(inst["categories"], inst["houses"], clues)


def zebra_name(var) -> str:
    return phrase(*var)


def zebra_value(var, house) -> str:
    return f"house {house}" if var[0] == "colour" else f"in house {house}"


ZEBRA_HIDDEN = ("Someone among {group} has to be {value}, and {name} is the only one left "
                "who can — every other one is ruled out.")


# ============================================================ Knights & Knaves ====

PEOPLE = ["Alice", "Bob", "Cara", "Dev", "Esha", "Farid"]
KNIGHT, KNAVE = "knight", "knave"


def statement_text(st: list, speaker: str) -> str:
    kind = st[0]
    def who(p): return "I" if p == speaker else p
    def be(p): return "am" if p == speaker else "is"
    if kind == "is":
        return f"{who(st[1])} {be(st[1])} a {st[2]}."
    if kind == "same":
        return f"{st[1]} and {st[2]} are the same kind." if speaker not in st[1:3] else \
            f"{st[2] if st[1] == speaker else st[1]} and I are the same kind."
    if kind == "diff":
        return f"{st[1]} and {st[2]} are different kinds." if speaker not in st[1:3] else \
            f"{st[2] if st[1] == speaker else st[1]} and I are different kinds."
    if kind == "count":
        return f"Exactly {st[1]} of us {'is a knight' if st[1] == 1 else 'are knights'}."
    if kind == "atleast_knaves":
        return f"At least {st[1]} of us {'is a knave' if st[1] == 1 else 'are knaves'}."
    if kind == "or":
        return f"{who(st[1])} {be(st[1])} a {st[2]} or {who(st[3])} {be(st[3])} a {st[4]}."
    if kind == "if":
        return f"If {who(st[1])} {be(st[1])} a {st[2]}, then {who(st[3])} {be(st[3])} a {st[4]}."
    raise ValueError(kind)


def statement_scope(st: list, people: list) -> list:
    kind = st[0]
    if kind in ("count", "atleast_knaves"):
        return list(people)
    if kind in ("is",):
        return [st[1]]
    if kind in ("same", "diff"):
        return [st[1], st[2]]
    return [st[1], st[3]]


def statement_true(st: list, a: dict) -> bool:
    kind = st[0]
    if kind == "is":
        return a[st[1]] == st[2]
    if kind == "same":
        return a[st[1]] == a[st[2]]
    if kind == "diff":
        return a[st[1]] != a[st[2]]
    if kind == "count":
        return sum(1 for v in a.values() if v == KNIGHT) == st[1]
    if kind == "atleast_knaves":
        return sum(1 for v in a.values() if v == KNAVE) >= st[1]
    if kind == "or":
        return a[st[1]] == st[2] or a[st[3]] == st[4]
    if kind == "if":
        return a[st[1]] != st[2] or a[st[3]] == st[4]
    raise ValueError(kind)


def knights_csp(people: list, statements: list) -> CSP:
    """One Predicate per statement: the speaker is a knight exactly when the
    statement is true (knights always tell the truth, knaves always lie)."""
    constraints = []
    for i, (speaker, st) in enumerate(statements, 1):
        scope = list(dict.fromkeys([speaker] + statement_scope(st, people)))

        def fn(local, speaker=speaker, st=st, scope=scope):
            return (local[speaker] == KNIGHT) == statement_true(st, local)

        constraints.append(Predicate(scope, fn, name="Statement",
                                     label=f"{speaker}'s statement (“{statement_text(st, speaker)}”)"))
    return CSP(people, {p: [KNIGHT, KNAVE] for p in people}, constraints)


def _random_statement(rng, people, speaker):
    kinds = ["is", "is", "same", "diff", "count", "atleast_knaves", "or", "if"]
    kind = rng.choice(kinds)
    kind_word = lambda: rng.choice([KNIGHT, KNAVE])
    if kind == "is":
        return ["is", rng.choice(people), kind_word()]
    if kind in ("same", "diff"):
        a, b = rng.sample(people, 2)
        return [kind, a, b]
    if kind == "count":
        return ["count", rng.randint(0, len(people))]
    if kind == "atleast_knaves":
        return ["atleast_knaves", rng.randint(1, len(people))]
    a, b = rng.sample(people, 2)
    return [kind, a, kind_word(), b, kind_word()]


def generate_knights(n: int = 3, seed: int | None = None) -> dict:
    rng = random.Random(seed)
    people = PEOPLE[:n]
    while True:
        secret = {p: rng.choice([KNIGHT, KNAVE]) for p in people}
        statements: list = []
        for _ in range(60):
            speaker = rng.choice(people)
            st = _random_statement(rng, people, speaker)
            truth = statement_true(st, secret)
            if truth != (secret[speaker] == KNIGHT):
                continue                                # the speaker couldn't say it
            if any(s == speaker and x == st for s, x in statements):
                continue
            statements.append([speaker, st])
            if count_solutions(knights_csp(people, statements), limit=2) == 1:
                break
        if count_solutions(knights_csp(people, statements), limit=2) != 1:
            continue
        i = 0
        while i < len(statements):
            trial = statements[:i] + statements[i + 1:]
            if count_solutions(knights_csp(people, trial), limit=2) == 1:
                statements = trial
            else:
                i += 1
        return {"people": people, "statements": statements,
                "texts": [[s, statement_text(st, s)] for s, st in statements]}


CLASSIC_KNIGHTS = {
    "people": ["Alice", "Bob"],
    "statements": [["Alice", ["is", "Bob", KNAVE]], ["Bob", ["same", "Alice", "Bob"]]],
}
