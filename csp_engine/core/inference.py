"""Constraint propagation — reasoning about which values CAN'T be part of any
solution and removing them before the search ever has to guess.

Every function here is generic: none knows what a variable represents. They
only use what every CSP provides — the constraint graph and each
constraint's `is_satisfied` / `holds` — which is why the same code powers
Sudoku, N-Queens, KenKen cages and cryptarithmetic columns unmodified.

  forward_checking — cheap, local: after assigning var=value, prune values
                      from unassigned neighbours that are now impossible.
                      Handles binary constraints, and n-ary ones the moment
                      only one of their variables is left unassigned.

  ac3              — thorough, global: enforces (generalised) arc
                      consistency on every constraint until nothing more can
                      be pruned or a domain empties. Binary constraints are
                      revised value-pair by value-pair; n-ary constraints
                      (cage sums, column equations) by enumerating the
                      tuples that satisfy them.

  mac              — "Maintaining Arc Consistency": ac3 restarted from the
                      constraints touching the variable just assigned. Used
                      as the inference hook during search.

  mac_plus         — mac, plus pigeonhole reasoning over the CSP's
                      all-different groups: if k all-different variables
                      have only k candidate values between them, each value
                      must appear exactly once, so a value with a single
                      possible home goes there, and a value with none is a
                      dead end. Pairwise not-equal constraints can't see this.

All return (ok, pruned): pruned is the list of (variable, value) pairs
removed from domains, which the search undoes exactly on backtrack.
"""
from __future__ import annotations
from collections import deque
from .model import CSP, Var, Value
from .constraints import _ne

# An n-ary constraint is only revised once the product of its scope's domain
# sizes drops below this; above it, enumerating supports costs more than the
# pruning saves. Skipping a revision never loses correctness, only pruning.
GAC_TUPLE_LIMIT = 6000


# ---- forward checking ----------------------------------------------------

def forward_checking(csp: CSP, var: Var, value: Value, assignment: dict):
    pruned: list[tuple[Var, Value]] = []

    for nbr in csp.neighbors(var):
        if nbr in assignment:
            continue
        dom = csp.domains[nbr]
        for c in csp.binary_constraints_between(var, nbr):
            var_is_x = c.x == var
            for val in list(dom):
                ok = c.rel(value, val) if var_is_x else c.rel(val, value)
                if not ok:
                    dom.remove(val)
                    pruned.append((nbr, val))
        if len(dom) == 0:
            return False, pruned

    for c in csp.constraints_on(var):
        if hasattr(c, "holds"):
            continue
        open_vars = [u for u in c.variables if u not in assignment]
        if len(open_vars) != 1:
            continue
        u = open_vars[0]
        dom = csp.domains[u]
        for val in list(dom):
            assignment[u] = val
            ok = c.is_satisfied(assignment)
            del assignment[u]
            if not ok:
                dom.remove(val)
                pruned.append((u, val))
        if len(dom) == 0:
            return False, pruned

    return True, pruned


# ---- revision of a single constraint -------------------------------------

def _revise_binary(csp: CSP, c, x: Var, y: Var) -> list[Value]:
    """Remove values of x with no supporting value of y under c."""
    dom_x, dom_y = csp.domains[x], csp.domains[y]
    if c.rel is _ne:
        # A not-equal arc can only prune when y is down to a single value.
        if len(dom_y) != 1:
            return []
        (only,) = dom_y.values
        if only in dom_x:
            dom_x.remove(only)
            return [only]
        return []

    removed = []
    x_first = c.x == x
    rel = c.rel
    for a in list(dom_x):
        if x_first:
            supported = any(rel(a, b) for b in dom_y)
        else:
            supported = any(rel(b, a) for b in dom_y)
        if not supported:
            dom_x.remove(a)
            removed.append(a)
    return removed


def _revise_nary(csp: CSP, c) -> dict[Var, list[Value]] | None:
    """Generalised arc consistency for an n-ary constraint: enumerate the
    tuples over the scope's current domains that satisfy it (pruning
    partial tuples early when the constraint can judge them), then drop
    every value that appears in no satisfying tuple. Returns None if the
    scope is still too large to enumerate."""
    scope = c.variables
    size = 1
    for v in scope:
        size *= len(csp.domains[v])
        if size > GAC_TUPLE_LIMIT:
            return None

    order = sorted(scope, key=lambda v: len(csp.domains[v]))
    domains = {v: list(csp.domains[v]) for v in scope}
    supported: dict[Var, set] = {v: set() for v in scope}
    remaining = [sum(len(d) for d in domains.values())]   # values still lacking support
    partial: dict[Var, Value] = {}
    last = len(order) - 1

    def dfs(k: int) -> bool:          # True = every value already supported, stop early
        v = order[k]
        for val in domains[v]:
            partial[v] = val
            if c.is_satisfied(partial):
                if k == last:
                    for u, uval in partial.items():
                        if uval not in supported[u]:
                            supported[u].add(uval)
                            remaining[0] -= 1
                    if remaining[0] == 0:
                        del partial[v]
                        return True
                elif dfs(k + 1):
                    del partial[v]
                    return True
            del partial[v]
        return False

    dfs(0)

    removed: dict[Var, list[Value]] = {}
    for v in scope:
        dom = csp.domains[v]
        for val in list(dom):
            if val not in supported[v]:
                dom.remove(val)
                removed.setdefault(v, []).append(val)
    return removed


def _groups_pass(csp: CSP, groups, pruned: list, queue: deque, queued: set,
                 touched: set) -> bool | None:
    """One sweep of pigeonhole reasoning over the given all-different groups.
    Returns False on a dead end, True if it pruned anything, None if not."""
    changed = None
    for _, members in groups:
        union: set = set()
        for v in members:
            union |= csp.domains[v].values
        if len(union) < len(members):
            return False                     # not enough values to go round
        if len(union) > len(members):
            continue
        for val in union:
            home = None
            count = 0
            for v in members:
                if val in csp.domains[v].values:
                    count += 1
                    home = v
                    if count > 1:
                        break
            if count == 1 and len(csp.domains[home]) > 1:
                dom = csp.domains[home]
                for other in list(dom):
                    if other != val:
                        dom.remove(other)
                        pruned.append((home, other))
                touched.add(home)
                for c2 in csp.constraints_on(home):
                    if id(c2) not in queued:
                        queue.append(c2)
                        queued.add(id(c2))
                changed = True
    return changed


def _propagate(csp: CSP, queue_constraints, pruned: list, use_groups: bool = False,
               touched: set | None = None) -> bool:
    queue = deque(queue_constraints)
    queued = {id(c) for c in queue}
    touched = set(touched or ())        # variables whose domains changed

    while True:
        if not _drain(csp, queue, queued, pruned, touched):
            return False
        if not use_groups or not touched:
            return True
        groups = {id(g): g for v in touched for g in csp.groups_of.get(v, ())}
        touched.clear()
        result = _groups_pass(csp, groups.values(), pruned, queue, queued, touched)
        if result is False:
            return False
        if result is None and not queue:
            return True


def _drain(csp: CSP, queue: deque, queued: set, pruned: list, touched: set) -> bool:
    while queue:
        c = queue.popleft()
        queued.discard(id(c))
        changed: list[Var] = []

        if hasattr(c, "holds"):
            for x, y in ((c.x, c.y), (c.y, c.x)):
                removed = _revise_binary(csp, c, x, y)
                if removed:
                    pruned.extend((x, v) for v in removed)
                    if len(csp.domains[x]) == 0:
                        return False
                    changed.append(x)
        else:
            removed_map = _revise_nary(csp, c)
            if removed_map:
                # record every removal before checking for a wipeout, or the
                # search can't restore them on backtrack
                for v, vals in removed_map.items():
                    pruned.extend((v, val) for val in vals)
                    changed.append(v)
                if any(len(csp.domains[v]) == 0 for v in removed_map):
                    return False

        touched.update(changed)
        for v in changed:
            for c2 in csp.constraints_on(v):
                if c2 is not c and id(c2) not in queued:
                    queue.append(c2)
                    queued.add(id(c2))
    return True


# ---- AC-3 / MAC -----------------------------------------------------------

def ac3(csp: CSP, constraints=None):
    """Enforce (generalised) arc consistency over the given constraints
    (default: all of them). Returns (ok, pruned)."""
    pruned: list[tuple[Var, Value]] = []
    ok = _propagate(csp, constraints if constraints is not None else csp.constraints, pruned)
    return ok, pruned


def mac(csp: CSP, var: Var, value: Value, assignment: dict):
    """Arc consistency restarted from the variable just assigned.

    The search records the assignment in `assignment` but never shrinks
    `csp.domains[var]` itself, so we first pin domain[var] to exactly
    {value} (tracked as ordinary prunes, undone on backtrack like any
    other), then propagate outward from the constraints touching it.
    """
    pruned = [(var, v) for v in list(csp.domains[var]) if v != value]
    for _, v in pruned:
        csp.domains[var].remove(v)
    ok = _propagate(csp, csp.constraints_on(var), pruned)
    return ok, pruned


def mac_plus(csp: CSP, var: Var, value: Value, assignment: dict):
    """mac + pigeonhole reasoning over all-different groups (see above)."""
    pruned = [(var, v) for v in list(csp.domains[var]) if v != value]
    for _, v in pruned:
        csp.domains[var].remove(v)
    ok = _propagate(csp, csp.constraints_on(var), pruned, use_groups=True, touched={var})
    return ok, pruned
