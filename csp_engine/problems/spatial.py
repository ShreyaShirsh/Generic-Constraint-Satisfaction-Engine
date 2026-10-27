"""Visual & spatial puzzles: polyomino tiling, lattice tangram, jigsaw,
cube-net folding. (The pocket cube lives in search_puzzles.py.)

  Polyomino tiling / Tangram
      variables   = the pieces
      domains     = every way the piece can sit inside the target shape
                    (each rotation / reflection / position)
      constraints = for every PAIR of pieces: "they don't overlap"
      The pieces' areas add up to the target's, so no-overlap = exact cover.

  Jigsaw
      variables   = the slots of the frame; domains = (piece, rotation)
      constraints = neighbouring edges fit together; each piece used once
                    (a not-equal on the piece number); flat edges face out

  Cube nets
      variables   = the squares of the net; domains = the 24 ways a cube can
                    rest on a square
      constraints = rolling the cube from a square onto its neighbour gives
                    the neighbour's orientation; every square ends up under a
                    DIFFERENT cube face (not-equal again)
      The net folds into a cube exactly when this CSP has a solution.
"""
from __future__ import annotations
import random
from itertools import combinations
from ..core.model import CSP
from ..core.constraints import BinaryRelation, Predicate, NotEqual

# ============================================================== polyominoes ====

PENTOMINOES = {
    "F": [(0, 1), (0, 2), (1, 0), (1, 1), (2, 1)],
    "I": [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0)],
    "L": [(0, 0), (1, 0), (2, 0), (3, 0), (3, 1)],
    "N": [(0, 1), (1, 1), (2, 0), (2, 1), (3, 0)],
    "P": [(0, 0), (0, 1), (1, 0), (1, 1), (2, 0)],
    "T": [(0, 0), (0, 1), (0, 2), (1, 1), (2, 1)],
    "U": [(0, 0), (0, 2), (1, 0), (1, 1), (1, 2)],
    "V": [(0, 0), (1, 0), (2, 0), (2, 1), (2, 2)],
    "W": [(0, 0), (1, 0), (1, 1), (2, 1), (2, 2)],
    "X": [(0, 1), (1, 0), (1, 1), (1, 2), (2, 1)],
    "Y": [(0, 1), (1, 0), (1, 1), (2, 1), (3, 1)],
    "Z": [(0, 0), (0, 1), (1, 1), (2, 1), (2, 2)],
}
TETROMINOES = {
    "I4": [(0, 0), (1, 0), (2, 0), (3, 0)], "O4": [(0, 0), (0, 1), (1, 0), (1, 1)],
    "T4": [(0, 0), (0, 1), (0, 2), (1, 1)], "L4": [(0, 0), (1, 0), (2, 0), (2, 1)],
    "S4": [(0, 1), (0, 2), (1, 0), (1, 1)],
}


def _normalise(cells):
    mr = min(r for r, _ in cells)
    mc = min(c for _, c in cells)
    return tuple(sorted((r - mr, c - mc) for r, c in cells))


def orientations(cells) -> list:
    out, cur = set(), list(cells)
    for _ in range(4):
        cur = [(c, -r) for r, c in cur]
        out.add(_normalise(cur))
        out.add(_normalise([(r, -c) for r, c in cur]))
    return sorted(out)


def _no_overlap(a, b):
    return not (a & b)


def tiling_csp(region: list, pieces: dict) -> tuple[CSP, dict]:
    """pieces: {name: cells}. Returns the CSP and {name: [placement cell lists]}
    (domains hold bitmasks so the overlap test is one AND)."""
    region = [tuple(c) for c in region]
    index = {c: i for i, c in enumerate(region)}
    placements, domains = {}, {}
    for name, cells in pieces.items():
        opts, masks = [], []
        for o in orientations(cells):
            fr, fc = o[0]
            for r0, c0 in region:                       # put the shape's first square here
                shifted = [(r0 + r - fr, c0 + c - fc) for r, c in o]
                if all(x in index for x in shifted):
                    m = 0
                    for x in shifted:
                        m |= 1 << index[x]
                    if m not in masks:
                        masks.append(m)
                        opts.append(shifted)
        placements[name] = dict(zip(masks, opts))
        domains[name] = masks
    names = list(pieces)
    constraints = [BinaryRelation(a, b, _no_overlap, name="NoOverlap",
                                  label=f"pieces {a} and {b} don't overlap")
                   for a, b in combinations(names, 2)]
    return CSP(names, domains, constraints), placements


def random_tiling_puzzle(n_pieces: int, rng: random.Random, pool: dict | None = None,
                         box: int = 9) -> dict:
    """Drop random pieces next to each other; their union is the shape to fill."""
    pool = pool or PENTOMINOES
    names = rng.sample(sorted(pool), n_pieces)
    taken: set = set()
    for name in names:
        for _ in range(400):
            o = rng.choice(orientations(pool[name]))
            r0, c0 = rng.randrange(box), rng.randrange(box)
            cells = {(r0 + r, c0 + c) for r, c in o}
            if any(r >= box or c >= box for r, c in cells) or cells & taken:
                continue
            if taken and not any((r + dr, c + dc) in taken for r, c in cells
                                 for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                continue
            taken |= cells
            break
    return {"region": sorted(map(list, _normalise(taken))), "pieces": names}


TILING_PRESETS = {      # piece sets the solver confirmed can tile each rectangle
    "3×5 rectangle": {"region": [[r, c] for r in range(3) for c in range(5)], "pieces": ["P", "U", "V"]},
    "4×5 rectangle": {"region": [[r, c] for r in range(4) for c in range(5)], "pieces": ["P", "T", "V", "W"]},
    "5×6 rectangle": {"region": [[r, c] for r in range(5) for c in range(6)],
                      "pieces": ["F", "L", "N", "U", "V", "W"]},
    "5×8 rectangle": {"region": [[r, c] for r in range(5) for c in range(8)],
                      "pieces": ["I", "L", "N", "T", "U", "W", "X", "Y"]},
}


# ================================================================== tangram ====
# Every unit square is cut along both diagonals into 4 quarter-triangles
# (q = 0 bottom, 1 right, 2 top, 3 left). Tans are unions of quarters.

TAN_POLYGONS = {    # the classic dissection of a 4x4 square (x right, y up)
    "big triangle A": [(0, 0), (4, 0), (2, 2)],
    "big triangle B": [(0, 0), (2, 2), (0, 4)],
    "medium triangle": [(4, 4), (2, 4), (4, 2)],
    "square": [(2, 2), (3, 3), (2, 4), (1, 3)],
    "small triangle A": [(0, 4), (1, 3), (2, 4)],
    "small triangle B": [(2, 2), (3, 1), (3, 3)],
    "parallelogram": [(4, 0), (4, 2), (3, 3), (3, 1)],
}
_Q_CENTRE = {0: (0.5, 0.17), 1: (0.83, 0.5), 2: (0.5, 0.83), 3: (0.17, 0.5)}


def _inside(pt, poly) -> bool:
    x, y = pt
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def _quarters(poly) -> frozenset:
    xs, ys = [p[0] for p in poly], [p[1] for p in poly]
    out = set()
    for x in range(int(min(xs)), int(max(xs))):
        for y in range(int(min(ys)), int(max(ys))):
            for q, (dx, dy) in _Q_CENTRE.items():
                if _inside((x + dx, y + dy), poly):
                    out.add((x, y, q))
    return frozenset(out)


def _tan_orientations(poly) -> list:
    shapes = set()
    for flip in (False, True):
        pts = [(-x, y) if flip else (x, y) for x, y in poly]
        for _ in range(4):
            pts = [(-y, x) for x, y in pts]
            mx, my = min(p[0] for p in pts), min(p[1] for p in pts)
            shapes.add(_quarters([(x - mx, y - my) for x, y in pts]))
    return [s for s in shapes if s]


def tangram_csp(target: frozenset) -> tuple[CSP, dict]:
    index = {q: i for i, q in enumerate(sorted(target))}
    xs = [q[0] for q in target]
    ys = [q[1] for q in target]
    placements, domains = {}, {}
    for name, poly in TAN_POLYGONS.items():
        opts = {}
        for shape in _tan_orientations(poly):
            for dx in range(min(xs) - 4, max(xs) + 1):
                for dy in range(min(ys) - 4, max(ys) + 1):
                    moved = [(x + dx, y + dy, q) for x, y, q in shape]
                    if all(m in index for m in moved):
                        mask = 0
                        for m in moved:
                            mask |= 1 << index[m]
                        opts[mask] = moved
        placements[name] = opts
        domains[name] = sorted(opts)
    names = list(TAN_POLYGONS)
    constraints = [BinaryRelation(a, b, _no_overlap, name="NoOverlap",
                                  label=f"the {a} and the {b} don't overlap") for a, b in combinations(names, 2)]
    # identical pieces: insist on one order to avoid counting swaps twice
    for a, b in (("big triangle A", "big triangle B"), ("small triangle A", "small triangle B")):
        constraints.append(BinaryRelation(a, b, lambda x, y: x < y, name="Symmetry",
                                          label="identical pieces are interchangeable"))
    return CSP(names, domains, constraints), placements


def tangram_square() -> frozenset:
    return frozenset().union(*(_quarters(p) for p in TAN_POLYGONS.values()))


def random_tangram(rng: random.Random, box: int = 9) -> frozenset:
    taken: set = set()
    for name, poly in TAN_POLYGONS.items():
        shapes = _tan_orientations(poly)
        for _ in range(600):
            shape = rng.choice(shapes)
            dx, dy = rng.randrange(box), rng.randrange(box)
            moved = {(x + dx, y + dy, q) for x, y, q in shape}
            if any(x >= box or y >= box for x, y, _ in moved) or moved & taken:
                continue
            if taken and not _touches(moved, taken):
                continue
            taken |= moved
            break
    mx = min(x for x, _, _ in taken)
    my = min(y for _, y, _ in taken)
    return frozenset((x - mx, y - my, q) for x, y, q in taken)


def _touches(a: set, b: set) -> bool:
    """Do two quarter sets share an edge?"""
    for x, y, q in a:
        nbrs = [(x, y, (q + 1) % 4), (x, y, (q + 3) % 4)]
        nbrs.append({0: (x, y - 1, 2), 1: (x + 1, y, 3), 2: (x, y + 1, 0), 3: (x - 1, y, 1)}[q])
        if any(n in b for n in nbrs):
            return True
    return False


def tangram_shapes() -> dict:
    big_triangle = frozenset(_quarters([(0, 0), (8, 0), (4, 4)]))
    return {"Square": tangram_square(), "Big triangle": big_triangle}


# =================================================================== jigsaw ====

def jigsaw_instance(n: int, rng: random.Random, kinds: int | None = None) -> dict:
    """pieces[i] = (top, right, bottom, left) edge codes; 0 = flat, +k = tab,
    -k = blank. Pieces come back shuffled and randomly rotated."""
    kinds = kinds or n + 2
    h = [[rng.choice([1, -1]) * rng.randint(1, kinds) for _ in range(n - 1)] for _ in range(n)]
    v = [[rng.choice([1, -1]) * rng.randint(1, kinds) for _ in range(n)] for _ in range(n - 1)]
    solved = []
    for r in range(n):
        for c in range(n):
            top = 0 if r == 0 else -v[r - 1][c]
            bottom = 0 if r == n - 1 else v[r][c]
            left = 0 if c == 0 else -h[r][c - 1]
            right = 0 if c == n - 1 else h[r][c]
            solved.append((top, right, bottom, left))
    order = list(range(n * n))
    rng.shuffle(order)
    pieces, truth = [], {}
    for new_i, old_i in enumerate(order):
        rot = rng.randrange(4)
        pieces.append(list(rotate_edges(solved[old_i], -rot)))
        truth[old_i] = new_i
    return {"n": n, "pieces": pieces, "anchor": truth[0]}


def rotate_edges(e, k):
    """Rotate a piece k quarter-turns clockwise: (top, right, bottom, left)."""
    k %= 4
    return tuple(e[(i - k) % 4] for i in range(4))


def jigsaw_csp(inst: dict) -> CSP:
    n, pieces = inst["n"], [tuple(p) for p in inst["pieces"]]
    slots = [(r, c) for r in range(n) for c in range(n)]
    domains = {}
    for r, c in slots:
        opts = []
        for i, p in enumerate(pieces):
            for k in range(4):
                e = rotate_edges(p, k)
                want = (r == 0, c == n - 1, r == n - 1, c == 0)
                if all((e[s] == 0) == want[s] for s in range(4)):
                    opts.append((i, k))
        domains[(r, c)] = opts
    domains[(0, 0)] = [o for o in domains[(0, 0)] if o[0] == inst["anchor"]]

    def edges(o):
        return rotate_edges(pieces[o[0]], o[1])

    constraints = []
    for r, c in slots:
        if c + 1 < n:
            constraints.append(BinaryRelation((r, c), (r, c + 1),
                                              lambda a, b: edges(a)[1] == -edges(b)[3] and a[0] != b[0],
                                              name="Fits", label=f"the pieces at R{r+1}C{c+1} and R{r+1}C{c+2} fit"))
        if r + 1 < n:
            constraints.append(BinaryRelation((r, c), (r + 1, c),
                                              lambda a, b: edges(a)[2] == -edges(b)[0] and a[0] != b[0],
                                              name="Fits", label=f"the pieces at R{r+1}C{c+1} and R{r+2}C{c+1} fit"))
    for a, b in combinations(slots, 2):
        if abs(a[0] - b[0]) + abs(a[1] - b[1]) > 1:
            constraints.append(BinaryRelation(a, b, lambda x, y: x[0] != y[0], name="NotEqual",
                                              label="each piece is used once"))
    return CSP(slots, domains, constraints)


# =============================================================== cube nets ====
# orientation = which original face is (down, up, north, south, east, west)

FACES = "DUNSEW"
ROLL = {   # rolling one square in a direction: new (D,U,N,S,E,W) from old
    "E": lambda o: (o[4], o[5], o[2], o[3], o[1], o[0]),
    "W": lambda o: (o[5], o[4], o[2], o[3], o[0], o[1]),
    "N": lambda o: (o[2], o[3], o[1], o[0], o[4], o[5]),
    "S": lambda o: (o[3], o[2], o[0], o[1], o[4], o[5]),
}
IDENTITY = tuple(FACES)


def _all_orientations():
    seen, stack = {IDENTITY}, [IDENTITY]
    while stack:
        o = stack.pop()
        for f in ROLL.values():
            n = f(o)
            if n not in seen:
                seen.add(n)
                stack.append(n)
    return sorted(seen)


ORIENTATIONS = _all_orientations()
FACE_NAME = {"D": "bottom", "U": "top", "N": "back", "S": "front", "E": "right", "W": "left"}


def net_csp(cells: list) -> CSP:
    """cells: [(row, col)] of the net. Row grows southwards."""
    cells = sorted(tuple(c) for c in cells)
    domains = {c: ORIENTATIONS for c in cells}
    domains[cells[0]] = [IDENTITY]                         # the cube starts face-down on square 1
    constraints = []
    for (r, c) in cells:
        for d, (dr, dc) in (("E", (0, 1)), ("S", (1, 0))):
            nb = (r + dr, c + dc)
            if nb in domains:
                constraints.append(BinaryRelation((r, c), nb, lambda a, b, d=d: ROLL[d](a) == b,
                                                  name="Roll",
                                                  label=f"rolling the cube from R{r+1}C{c+1} {'east' if d == 'E' else 'south'}"))
    for a, b in combinations(cells, 2):
        constraints.append(BinaryRelation(a, b, lambda x, y: x[0] != y[0], name="NotEqual",
                                          label="every square is covered by a different face"))
    return CSP(cells, domains, constraints)


def hexominoes() -> list:
    """All 35 free hexominoes (generated, not typed in)."""
    shapes = {((0, 0),)}
    for _ in range(5):
        grown = set()
        for s in shapes:
            cells = set(s)
            for r, c in s:
                for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    n = (r + dr, c + dc)
                    if n not in cells:
                        grown.add(min(orientations(list(cells | {n}))))
        shapes = grown
    return sorted(shapes)
