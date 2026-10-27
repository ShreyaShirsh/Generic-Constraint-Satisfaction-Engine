"""Human-style reasoning: solve a CSP the way a person would, one justified
step at a time, and explain each step in words.

The search in backtracking.py is fast but opaque -- it guesses and undoes.
This module never guesses. It keeps a set of candidate values per variable,
crosses candidates out only when a constraint proves them impossible
(remembering WHICH constraint and WHICH variables did it), and fills in a
variable only when the remaining evidence forces it. That gives us three
things the Studio needs:

  * hints      -- the easiest next step, with a plain-English reason
  * grading    -- how hard a puzzle is = the hardest kind of step it needs
  * candidates -- the pencil marks a solver would write

Still fully generic: it works from constraints' `is_satisfied`, the shared
revise functions in inference.py, and the optional all-different `groups`
on the CSP. Nothing here knows what a Sudoku is.

Levels of reasoning, easiest first:
  1  Direct      -- a value is ruled out by a constraint whose other
                    variables are already filled in ("7 is already in this row")
  2  Only place  -- a value can go in only one variable of an all-different
                    group that must contain every value
  3  Advanced    -- generalised arc consistency across constraints (cage
                    arithmetic, inequality chains), naked subsets ("these two
                    cells take 3 and 5 between them"), group intersections
  4  Search      -- no logical step exists; the engine has to guess
"""
from __future__ import annotations
from dataclasses import dataclass, field
from itertools import combinations
from typing import Callable
from .model import CSP, Domain, Var, Value
from .inference import _revise_binary, _revise_nary

LEVEL_NAMES = {1: "Easy", 2: "Medium", 3: "Hard", 4: "Expert"}
LEVEL_TECHNIQUES = {
    1: "direct elimination",
    2: "only place left in a group",
    3: "advanced reasoning (arithmetic/inequality propagation, subsets, intersections)",
    4: "trial and error (search)",
}


@dataclass
class Why:
    """Why one candidate value was crossed out."""
    kind: str               # "used" | "breaks" | "propagate" | "subset" | "intersection"
    label: str              # the constraint / group responsible, in words
    culprits: tuple         # the variables whose state caused it
    level: int


@dataclass
class Step:
    kind: str               # "single" | "hidden" | "contradiction"
    var: Var | None
    value: Value | None
    level: int
    text: str
    highlight: list = field(default_factory=list)   # variables the explanation points at
    group: str | None = None

    def __post_init__(self):
        if self.text:
            self.text = self.text[0].upper() + self.text[1:]


def _fmt_values(vals) -> str:
    vals = sorted(vals, key=lambda x: (str(type(x)), x))
    return ", ".join(str(v) for v in vals)


class Reasoner:
    def __init__(self, csp: CSP, assignment: dict, name_of: Callable[[Var], str] = str,
                 value_of: Callable[[Var, Value], str] | None = None,
                 hidden_fmt: str | None = None):
        """name_of / value_of / hidden_fmt only shape the English of the
        explanations (e.g. "the Englishman must be in house 3")."""
        self.csp = csp
        self.name_of = name_of
        self.value_of = value_of or (lambda var, val: str(val))
        self.hidden_fmt = hidden_fmt
        self.assignment: dict = dict(assignment)
        self.cands: dict[Var, set] = {
            v: set(csp.domains[v]) for v in csp.variables if v not in self.assignment
        }
        self.why: dict[tuple[Var, Value], Why] = {}
        self.removed: dict[Var, set] = {v: set() for v in self.cands}

        # Only groups that must contain EVERY value exactly once support
        # "only place left" reasoning (a Killer cage of 3 cells doesn't).
        self.groups: list[tuple[str, tuple]] = []
        for label, vs in csp.groups:
            union = set()
            for v in vs:
                union |= set(csp.domains[v])
            if len(union) == len(vs):
                self.groups.append((label, vs))
        self.groups_of: dict[Var, list] = {}
        for g in self.groups:
            for v in g[1]:
                self.groups_of.setdefault(v, []).append(g)

        for v in list(self.cands):
            self._direct(v, csp.constraints_on(v))

    # ---- bookkeeping -------------------------------------------------

    def _cross_out(self, var: Var, val: Value, why: Why) -> None:
        if val in self.cands.get(var, ()):
            self.cands[var].discard(val)
            self.removed[var].add(val)
            self.why[(var, val)] = why

    def _label(self, c) -> str:
        if getattr(c, "label", None):
            return c.label
        return f"{c.name} on {', '.join(self.name_of(v) for v in c.variables)}"

    def _direct(self, y: Var, constraints) -> None:
        """Level 1: cross out values of y that break a constraint whose other
        variables are all filled in."""
        for c in constraints:
            others = [u for u in c.variables if u != y]
            if any(u not in self.assignment for u in others):
                continue
            kind = "used" if getattr(c, "name", "") == "NotEqual" else "breaks"
            for val in list(self.cands[y]):
                self.assignment[y] = val
                ok = c.is_satisfied(self.assignment)
                del self.assignment[y]
                if not ok:
                    self._cross_out(y, val, Why(kind, self._label(c), tuple(others), 1))

    def assign(self, var: Var, val: Value) -> None:
        self.assignment[var] = val
        self.cands.pop(var, None)
        for c in self.csp.constraints_on(var):
            for y in c.variables:
                if y != var and y in self.cands:
                    self._direct(y, [c])

    # ---- level 3 techniques --------------------------------------------

    def _propagate(self) -> bool:
        """Generalised arc consistency over the candidate sets, remembering
        which constraint removed each value. Returns True if anything changed."""
        csp = self.csp
        saved = csp.domains
        domains = {v: Domain([val]) for v, val in self.assignment.items() if v in saved}
        for v, cs in self.cands.items():
            domains[v] = Domain(cs)
        csp.domains = domains
        changed_any = False
        try:
            queue = list(csp.constraints)
            queued = {id(c) for c in queue}
            while queue:
                c = queue.pop()
                queued.discard(id(c))
                changed = []
                if hasattr(c, "holds"):
                    for x, y in ((c.x, c.y), (c.y, c.x)):
                        if x in self.assignment:
                            continue
                        for val in _revise_binary(csp, c, x, y):
                            self._cross_out(x, val, Why("propagate", self._label(c), (y,), 3))
                            changed.append(x)
                else:
                    removed = _revise_nary(csp, c) or {}
                    for x, vals in removed.items():
                        if x in self.assignment:
                            continue
                        others = tuple(u for u in c.variables if u != x)
                        for val in vals:
                            self._cross_out(x, val, Why("propagate", self._label(c), others, 3))
                        changed.append(x)
                for x in changed:
                    changed_any = True
                    if not domains[x]:
                        return True
                    for c2 in csp.constraints_on(x):
                        if id(c2) not in queued:
                            queue.append(c2)
                            queued.add(id(c2))
        finally:
            csp.domains = saved
        return changed_any

    def _subsets(self) -> bool:
        """Naked pairs/triples: k open cells of a group whose candidates
        together are exactly k values claim those values for themselves."""
        changed = False
        for label, vs in self.groups:
            open_vars = [v for v in vs if v in self.cands]
            for k in (2, 3):
                small = [v for v in open_vars if 1 < len(self.cands[v]) <= k]
                for subset in combinations(small, k):
                    union = set().union(*(self.cands[v] for v in subset))
                    if len(union) != k:
                        continue
                    for other in open_vars:
                        if other in subset:
                            continue
                        for val in union & self.cands[other]:
                            self._cross_out(other, val, Why("subset", label, subset, 3))
                            changed = True
        return changed

    def _intersections(self) -> bool:
        """If, inside group A, value v can only sit in cells that all belong
        to group B too, then v can't sit anywhere else in B."""
        changed = False
        for label_a, vs_a in self.groups:
            placed = {self.assignment[v] for v in vs_a if v in self.assignment}
            values = set().union(*(self.cands[v] for v in vs_a if v in self.cands)) - placed
            for val in values:
                places = [v for v in vs_a if v in self.cands and val in self.cands[v]]
                if len(places) < 2:
                    continue
                common = set(map(id, self.groups_of.get(places[0], [])))
                for p in places[1:]:
                    common &= set(map(id, self.groups_of.get(p, [])))
                for group_b in self.groups:
                    label_b, vs_b = group_b
                    if id(group_b) not in common or label_b == label_a:
                        continue
                    for other in vs_b:
                        if other in places or other not in self.cands:
                            continue
                        if val in self.cands[other]:
                            self._cross_out(other, val, Why(
                                "intersection",
                                f"{label_a} can only place it where it overlaps {label_b}",
                                tuple(places), 3))
                            changed = True
        return changed

    # ---- finding the next step ------------------------------------------

    def _level_of_removals(self, var: Var, vals) -> int:
        return max((self.why[(var, v)].level for v in vals if (var, v) in self.why), default=1)

    def _find_simple(self, max_level: int) -> Step | None:
        for var, cs in self.cands.items():
            if len(cs) == 0:
                return Step("contradiction", var, None, 1,
                            f"{self.name_of(var)} has no possible value left — "
                            f"some entry already on the board is wrong.", [var])
        best = None
        for var, cs in self.cands.items():
            if len(cs) == 1:
                level = self._level_of_removals(var, self.removed[var])
                if level <= max_level and (best is None or level < best.level):
                    best = self._single_step(var, next(iter(cs)), level)
                    if level == 1:
                        return best
        for label, vs in self.groups:
            placed = {self.assignment[v] for v in vs if v in self.assignment}
            for val in set().union(*(self.cands[v] for v in vs if v in self.cands)) - placed:
                places = [v for v in vs if v in self.cands and val in self.cands[v]]
                if len(places) == 1:
                    blockers = [v for v in vs if v in self.cands and v != places[0]]
                    level = max([2] + [self.why[(b, val)].level for b in blockers
                                       if (b, val) in self.why])
                    if level <= max_level and (best is None or level < best.level):
                        best = self._hidden_step(places[0], val, label, blockers, level)
        return best

    def next_step(self, max_level: int = 3) -> Step | None:
        step = self._find_simple(min(max_level, 2))
        if step is not None or max_level < 3:
            return step
        while True:
            progressed = self._propagate()
            progressed = self._subsets() or progressed
            progressed = self._intersections() or progressed
            step = self._find_simple(3)
            if step is not None or not progressed:
                return step

    # ---- explanations ---------------------------------------------------

    def _single_step(self, var: Var, val: Value, level: int) -> Step:
        name = self.name_of(var)
        by_reason: dict[tuple, list] = {}
        highlight: set = set()
        for v in self.removed[var]:
            w = self.why.get((var, v))
            if w is None:
                continue
            by_reason.setdefault((w.kind, w.label), []).append(v)
            highlight.update(w.culprits)

        clauses = []
        for (kind, label), vals in sorted(by_reason.items(), key=lambda kv: min(kv[1])):
            vs = _fmt_values(vals)
            plural = len(vals) > 1
            if kind == "used":
                clauses.append(f"{vs} {'are' if plural else 'is'} already used in {label}")
            elif kind == "breaks":
                clauses.append(f"{vs} would break {label}")
            elif kind == "propagate":
                clauses.append(f"{vs} can't work with {label}")
            elif kind == "subset":
                clauses.append(f"{vs} {'are' if plural else 'is'} claimed by other cells in {label}")
            else:
                clauses.append(f"{vs} must go elsewhere ({label})")
        reason = "; ".join(clauses) if clauses else "it is the only value in its domain"
        return Step("single", var, val, level,
                    f"{name} must be {self.value_of(var, val)}. Everything else is ruled out: {reason}.",
                    sorted(highlight, key=str))

    def _hidden_step(self, var: Var, val: Value, label: str, blockers, level: int) -> Step:
        name = self.name_of(var)
        if self.hidden_fmt:
            text = self.hidden_fmt.format(value=self.value_of(var, val), group=label, name=name)
        else:
            text = (f"{val} has to appear somewhere in {label}, and {name} is the only "
                    f"empty cell there that can still hold it — every other one rules {val} out.")
        return Step("hidden", var, val, level, text,
                    sorted(blockers, key=str), label)


# ---- public helpers -------------------------------------------------------

def next_step(csp: CSP, assignment: dict, name_of: Callable[[Var], str] = str,
              max_level: int = 3) -> Step | None:
    """The easiest justified next move from this position, or None if no
    logical step exists (the puzzle needs guessing from here)."""
    return Reasoner(csp, assignment, name_of).next_step(max_level)


def candidates(csp: CSP, assignment: dict, level: int = 1) -> dict[Var, set]:
    """Pencil marks: candidate values per open variable after the given
    level of reasoning (1 = direct eliminations only)."""
    r = Reasoner(csp, assignment)
    if level >= 3:
        r._propagate()
        r._subsets()
        r._intersections()
    return r.cands


@dataclass
class Grade:
    level: int
    name: str
    solved_by_logic: bool
    steps_by_level: dict[int, int]
    steps: int
    open_left: int

    def as_dict(self) -> dict:
        return {
            "level": self.level, "name": self.name,
            "solved_by_logic": self.solved_by_logic,
            "steps_by_level": self.steps_by_level,
            "steps": self.steps, "open_left": self.open_left,
            "technique": LEVEL_TECHNIQUES[self.level],
        }


def grade(csp: CSP, assignment: dict | None = None) -> Grade:
    """Solve with human-style steps only, always taking the easiest step
    available. Difficulty = the hardest step that was ever necessary; if
    logic runs out before the end, the puzzle needs search (Expert)."""
    r = Reasoner(csp, assignment or {})
    counts = {1: 0, 2: 0, 3: 0}
    hardest = 1
    while r.cands:
        step = r.next_step(3)
        if step is None or step.kind == "contradiction":
            break
        counts[step.level] += 1
        hardest = max(hardest, step.level)
        r.assign(step.var, step.value)
    solved = not r.cands
    level = hardest if solved else 4
    return Grade(level, LEVEL_NAMES[level], solved, counts, sum(counts.values()), len(r.cands))
