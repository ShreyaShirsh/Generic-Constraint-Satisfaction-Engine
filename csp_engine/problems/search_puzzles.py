"""Search puzzles, each described as a PlanningProblem (world rules only).
core/planning.py turns every one of them into the same planning CSP:
step variables + ONE "legal plan that reaches the goal" predicate.

  SlidingPuzzle   8-puzzle (and 15-puzzle)
  Hanoi           Tower of Hanoi, any number of disks, any start position
  RiverCrossing   farmer-wolf-goat-cabbage, missionaries & cannibals
  Sokoban         push every box onto a goal
  Maze            escape a grid maze (also used by robot / gridworld)
  PocketCube      the 2x2x2 Rubik's cube
"""
from __future__ import annotations
import random
from collections import deque
from itertools import permutations
from ..core.planning import PlanningProblem

DIRS = {"U": (-1, 0), "D": (1, 0), "L": (0, -1), "R": (0, 1)}


# ======================================================== sliding puzzle ====

class SlidingPuzzle(PlanningProblem):
    """Tiles 1..n²-1 and a blank (0). An action names where the BLANK moves."""
    alphabet = ["U", "D", "L", "R"]

    def __init__(self, board, size: int = 3):
        self.n = size
        self.initial = tuple(board)
        self.goal = tuple(list(range(1, size * size)) + [0])
        self.home = {v: divmod(i, size) for i, v in enumerate(self.goal)}

    def result(self, state, a):
        n = self.n
        i = state.index(0)
        r, c = divmod(i, n)
        dr, dc = DIRS[a]
        rr, cc = r + dr, c + dc
        if not (0 <= rr < n and 0 <= cc < n):
            return None
        j = rr * n + cc
        s = list(state)
        s[i], s[j] = s[j], s[i]
        return tuple(s)

    def is_goal(self, state):
        return state == self.goal

    def h(self, state):
        """Manhattan distance: every tile needs at least that many moves."""
        n, total = self.n, 0
        for i, v in enumerate(state):
            if v:
                r, c = divmod(i, n)
                hr, hc = self.home[v]
                total += abs(r - hr) + abs(c - hc)
        return total


def sliding_solvable(board, size: int = 3) -> bool:
    tiles = [v for v in board if v]
    inv = sum(1 for i in range(len(tiles)) for j in range(i + 1, len(tiles)) if tiles[i] > tiles[j])
    if size % 2:
        return inv % 2 == 0
    blank_row_from_bottom = size - board.index(0) // size
    return (inv + blank_row_from_bottom) % 2 == 1


def sliding_scramble(moves: int, size: int = 3, rng: random.Random | None = None) -> tuple:
    rng = rng or random.Random()
    p = SlidingPuzzle(list(range(1, size * size)) + [0], size)
    s, last = p.goal, None
    undo = {"U": "D", "D": "U", "L": "R", "R": "L"}
    for _ in range(moves):
        options = [a for a in p.alphabet if a != undo.get(last) and p.result(s, a)]
        last = rng.choice(options)
        s = p.result(s, last)
    return s


# ========================================================== Tower of Hanoi ====

PEGS = "ABC"


class Hanoi(PlanningProblem):
    """state[d] = peg (0,1,2) of disk d; disk 0 is the smallest. Goal: every
    disk on peg C. Action "AB" moves the top disk of peg A onto peg B."""
    alphabet = [a + b for a in PEGS for b in PEGS if a != b]

    def __init__(self, n: int, start=None, heuristic: str = "exact"):
        self.n = n
        self.initial = tuple(start) if start else tuple([0] * n)
        self.heuristic = heuristic

    def result(self, state, a):
        f, t = PEGS.index(a[0]), PEGS.index(a[1])
        on_f = [d for d in range(self.n) if state[d] == f]
        if not on_f:
            return None
        top = min(on_f)
        on_t = [d for d in range(self.n) if state[d] == t]
        if on_t and min(on_t) < top:
            return None                                   # never a big disk on a small one
        s = list(state)
        s[top] = t
        return tuple(s)

    def is_goal(self, state):
        return all(p == 2 for p in state)

    def h(self, state):
        if self.heuristic == "none":
            return 0
        if self.heuristic == "simple":                   # each misplaced disk moves >= once
            return sum(1 for p in state if p != 2)
        # exact distance to "all on C": the largest misplaced disk must cross,
        # which first means parking everything above it on the third peg
        target, dist = 2, 0
        for d in range(self.n - 1, -1, -1):
            if state[d] != target:
                dist += 1 << d
                target = 3 - state[d] - target
        return dist


# ============================================================ river crossing ====

class FarmerWolfGoatCabbage(PlanningProblem):
    """state = sides (0 start bank, 1 far bank) of (farmer, wolf, goat, cabbage)."""
    alphabet = ["alone", "wolf", "goat", "cabbage"]
    initial = (0, 0, 0, 0)
    ITEMS = {"wolf": 1, "goat": 2, "cabbage": 3}

    def result(self, s, a):
        f = s[0]
        nxt = list(s)
        nxt[0] = 1 - f
        if a != "alone":
            i = self.ITEMS[a]
            if s[i] != f:
                return None                               # the item isn't with the farmer
            nxt[i] = 1 - f
        _, w, g, c = nxt
        if g == w != nxt[0] or g == c != nxt[0]:
            return None                                   # something gets eaten
        return tuple(nxt)

    def is_goal(self, s):
        return s == (1, 1, 1, 1)

    def h(self, s):
        left = sum(1 for x in s[1:] if x == 0)
        return max(0, 2 * left - 1)


class MissionariesCannibals(PlanningProblem):
    """state = (missionaries on start bank, cannibals on start bank, boat on start bank?)."""

    def __init__(self, m: int = 3, c: int = 3, boat: int = 2):
        if boat < 2:
            raise ValueError("the boat must carry at least 2 people")
        self.m, self.c, self.cap = m, c, boat
        self.initial = (m, c, 1)
        self.alphabet = [f"{i}M{j}C" for i in range(boat + 1) for j in range(boat + 1)
                         if 1 <= i + j <= boat]

    def _safe(self, m, c):
        return (m == 0 or m >= c) and (self.m - m == 0 or self.m - m >= self.c - c)

    def result(self, s, a):
        dm, dc = int(a[0]), int(a[2])
        m, c, b = s
        sign = -1 if b == 1 else 1
        m2, c2 = m + sign * dm, c + sign * dc
        if not (0 <= m2 <= self.m and 0 <= c2 <= self.c) or not self._safe(m2, c2):
            return None
        return (m2, c2, 1 - b)

    def is_goal(self, s):
        return s[0] == 0 and s[1] == 0

    def h(self, s):
        """Each crossing carries at most `cap` people forward and every
        return trip brings at least one back."""
        people, k = s[0] + s[1], self.cap
        if people == 0:
            return 0
        forward = 1 + 2 * (-(-max(0, people - k) // (k - 1)))
        return forward if s[2] == 1 else forward + 1


# =================================================================== Sokoban ====

class Sokoban(PlanningProblem):
    """Level text: # wall, space floor, . goal, $ box, * box on goal,
    @ player, + player on goal. state = (player, sorted boxes)."""
    alphabet = ["U", "D", "L", "R"]

    def __init__(self, level: str):
        rows = level.strip("\n").split("\n")
        self.h_, self.w = len(rows), max(len(r) for r in rows)
        self.walls, self.goals, boxes = set(), set(), []
        player = None
        for r, row in enumerate(rows):
            for c, ch in enumerate(row.ljust(self.w)):
                if ch == "#":
                    self.walls.add((r, c))
                if ch in ".*+":
                    self.goals.add((r, c))
                if ch in "$*":
                    boxes.append((r, c))
                if ch in "@+":
                    player = (r, c)
        self.initial = (player, tuple(sorted(boxes)))
        self.dead = self._dead_squares()

    def _dead_squares(self) -> set:
        """Floor squares from which a box can never be pushed to any goal
        (computed by pulling boxes backwards from every goal)."""
        alive = set(self.goals)
        queue = deque(self.goals)
        while queue:
            r, c = queue.popleft()
            for dr, dc in DIRS.values():
                box, player = (r + dr, c + dc), (r + 2 * dr, c + 2 * dc)
                if box not in self.walls and player not in self.walls and box not in alive \
                        and 0 <= box[0] < self.h_ and 0 <= player[0] < self.h_:
                    alive.add(box)
                    queue.append(box)
        floor = {(r, c) for r in range(self.h_) for c in range(self.w) if (r, c) not in self.walls}
        return floor - alive

    def result(self, s, a):
        (pr, pc), boxes = s
        dr, dc = DIRS[a]
        nxt = (pr + dr, pc + dc)
        if nxt in self.walls:
            return None
        if nxt in boxes:
            beyond = (nxt[0] + dr, nxt[1] + dc)
            if beyond in self.walls or beyond in boxes or beyond in self.dead:
                return None
            boxes = tuple(sorted(beyond if b == nxt else b for b in boxes))
        return (nxt, boxes)

    def is_goal(self, s):
        return all(b in self.goals for b in s[1])

    def h(self, s):
        return sum(min(abs(b[0] - g[0]) + abs(b[1] - g[1]) for g in self.goals) for b in s[1])


SOKOBAN_LEVELS = {
    "Warm-up": """
#####
#@$.#
#####""",
    "Corner": """
######
#    #
# #@ #
# $* #
# .  #
######""",
    "Two boxes": """
#######
#     #
# $$ @#
# ..  #
#######""",
    "Detour": """
  ####
###  #
#.$@ #
# $  #
#.  ##
#####""",
    "Storeroom": """
########
#  .   #
# $#$  #
#  @ . #
########""",
}


# ====================================================================== maze ====

class Maze(PlanningProblem):
    """grid[r][c] True = wall. state = (r, c)."""
    alphabet = ["U", "D", "L", "R"]

    def __init__(self, grid, start, goal):
        self.grid = grid
        self.rows, self.cols = len(grid), len(grid[0])
        self.initial, self.goal = tuple(start), tuple(goal)

    def result(self, s, a):
        dr, dc = DIRS[a]
        r, c = s[0] + dr, s[1] + dc
        if 0 <= r < self.rows and 0 <= c < self.cols and not self.grid[r][c]:
            return (r, c)
        return None

    def is_goal(self, s):
        return s == self.goal

    def h(self, s):
        return abs(s[0] - self.goal[0]) + abs(s[1] - self.goal[1])


def generate_maze(rows: int, cols: int, rng: random.Random, loops: float = 0.08):
    """Randomised depth-first carving on an odd-sized grid, then knock out a
    few extra walls so there is more than one route."""
    R, C = rows | 1, cols | 1
    grid = [[True] * C for _ in range(R)]
    stack = [(1, 1)]
    grid[1][1] = False
    while stack:
        r, c = stack[-1]
        options = [(r + dr, c + dc, dr, dc) for dr, dc in ((2, 0), (-2, 0), (0, 2), (0, -2))
                   if 0 < r + dr < R - 1 and 0 < c + dc < C - 1 and grid[r + dr][c + dc]]
        if not options:
            stack.pop()
            continue
        nr, nc, dr, dc = rng.choice(options)
        grid[r + dr // 2][c + dc // 2] = False
        grid[nr][nc] = False
        stack.append((nr, nc))
    for r in range(1, R - 1):
        for c in range(1, C - 1):
            if grid[r][c] and rng.random() < loops:
                if (not grid[r - 1][c] and not grid[r + 1][c]) or (not grid[r][c - 1] and not grid[r][c + 1]):
                    grid[r][c] = False
    return grid, (1, 1), (R - 2, C - 2)


# =============================================================== pocket cube ====
# Corner-cubie model (Kociemba's conventions). Positions:
URF, UFL, ULB, UBR, DFR, DLF, DBL, DRB = range(8)
CUBE_MOVES = {
    "U": ((UBR, URF, UFL, ULB, DFR, DLF, DBL, DRB), (0, 0, 0, 0, 0, 0, 0, 0)),
    "R": ((DFR, UFL, ULB, URF, DRB, DLF, DBL, UBR), (2, 0, 0, 1, 1, 0, 0, 2)),
    "F": ((UFL, DLF, ULB, UBR, URF, DFR, DBL, DRB), (1, 2, 0, 0, 2, 1, 0, 0)),
}
SOLVED_CUBE = (tuple(range(8)), (0,) * 8)


def _apply(state, move):
    cp, co = state
    mp, mo = CUBE_MOVES[move]
    return (tuple(cp[mp[i]] for i in range(8)), tuple((co[mp[i]] + mo[i]) % 3 for i in range(8)))


def cube_turn(state, move: str):
    """move like "R", "R'", "R2"."""
    times = {"": 1, "2": 2, "'": 3}[move[1:]]
    for _ in range(times):
        state = _apply(state, move[0])
    return state


def _distance_table(project, start):
    table = {project(start): 0}
    queue = deque([start])
    while queue:
        s = queue.popleft()
        d = table[project(s)]
        for m in PocketCube.alphabet:
            n = cube_turn(s, m)
            k = project(n)
            if k not in table:
                table[k] = d + 1
                queue.append(n)
    return table


_PDB = {}


def _pdbs():
    if not _PDB:
        # exact move counts for the two halves of the puzzle, found once by BFS
        _PDB["perm"] = _distance_table(lambda s: s[0], SOLVED_CUBE)
        _PDB["orient"] = _distance_table(lambda s: s[1], SOLVED_CUBE)
    return _PDB


class PocketCube(PlanningProblem):
    """2x2x2 cube; the DBL corner never moves, so only U, R and F faces turn."""
    alphabet = [f + s for f in "URF" for s in ("", "'", "2")]

    def __init__(self, state):
        self.initial = state
        _pdbs()

    def result(self, s, a):
        return cube_turn(s, a)

    def is_goal(self, s):
        return s == SOLVED_CUBE

    def h(self, s):
        """Pattern databases: the moves needed to fix just the corner
        positions, or just the twists, can't exceed the moves for both."""
        return max(_PDB["perm"][s[0]], _PDB["orient"][s[1]])


def cube_scramble(moves: int, rng: random.Random):
    s, seq, last = SOLVED_CUBE, [], None
    for _ in range(moves):
        face = rng.choice([f for f in "URF" if f != last])
        m = face + rng.choice(["", "'", "2"])
        s = cube_turn(s, m)
        seq.append(m)
        last = face
    return s, seq


# sticker layout for drawing: corner position -> (face, index) of its 3 facelets
CORNER_FACELETS = {
    URF: (("U", 3), ("R", 0), ("F", 1)),
    UFL: (("U", 2), ("F", 0), ("L", 1)),
    ULB: (("U", 0), ("L", 0), ("B", 1)),
    UBR: (("U", 1), ("B", 0), ("R", 1)),
    DFR: (("D", 1), ("F", 3), ("R", 2)),
    DLF: (("D", 0), ("L", 3), ("F", 2)),
    DBL: (("D", 2), ("B", 3), ("L", 2)),
    DRB: (("D", 3), ("R", 3), ("B", 2)),
}


def cube_faces(state) -> dict:
    """Facelet colours (as face letters) for a 2x2 net: {face: [4 letters]}."""
    cp, co = state
    faces = {f: [None] * 4 for f in "URFDLB"}
    colours = {c: tuple(f for f, _ in CORNER_FACELETS[c]) for c in range(8)}
    for pos in range(8):
        ori = co[pos]
        for n in range(3):
            face, idx = CORNER_FACELETS[pos][(n + ori) % 3]
            faces[face][idx] = colours[cp[pos]][n]
    return faces
