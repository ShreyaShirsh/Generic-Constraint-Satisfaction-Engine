"""Two-player games, described as rules only (core/adversarial.Game).

The engine treats each game question as a Quantified CSP over move
variables:  ∃ my move ∀ your reply ∃ my move ... WIN(moves)  -- the same
one-predicate idea as everywhere else, with alternating quantifiers.

  ConnectFour   7x6, four in a row
  Nim           take any number from one heap; taking the last stone wins
  Othello       8x8 (or 6x6) reversi
  Hex           n x n; player 1 links top-bottom, player 2 left-right
  ChessTactics  mate-in-N puzzles (move rules from the python-chess library)
"""
from __future__ import annotations
from collections import deque
from ..core.adversarial import Game

# ============================================================ Connect Four ====

C4_COLS, C4_ROWS = 7, 6


def _c4_lines():
    lines = []
    for r in range(C4_ROWS):
        for c in range(C4_COLS):
            for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                cells = [(r + i * dr, c + i * dc) for i in range(4)]
                if all(0 <= rr < C4_ROWS and 0 <= cc < C4_COLS for rr, cc in cells):
                    lines.append(cells)
    return lines


C4_LINES = _c4_lines()
C4_THROUGH = {(r, c): [l for l in C4_LINES if (r, c) in l] for r in range(C4_ROWS) for c in range(C4_COLS)}


class ConnectFour(Game):
    """state = (columns: tuple of 7 tuples bottom-up, player to move, last cell)."""

    def initial(self):
        return (tuple(() for _ in range(C4_COLS)), 1, None)

    def to_move(self, s):
        return s[1]

    def moves(self, s):
        return [c for c in range(C4_COLS) if len(s[0][c]) < C4_ROWS]

    def order(self, s, moves):
        return sorted(moves, key=lambda c: abs(c - 3))

    def result(self, s, c):
        cols = list(s[0])
        cols[c] = cols[c] + (s[1],)
        return (tuple(cols), 3 - s[1], (len(cols[c]) - 1, c))

    @staticmethod
    def at(s, r, c):
        col = s[0][c]
        return col[r] if r < len(col) else 0

    def winner(self, s):
        if s[2] is not None:
            r, c = s[2]
            p = self.at(s, r, c)
            for line in C4_THROUGH[(r, c)]:
                if all(self.at(s, rr, cc) == p for rr, cc in line):
                    return p
        if all(len(col) == C4_ROWS for col in s[0]):
            return "draw"
        return None

    def evaluate(self, s, player):
        score = 0
        opp = 3 - player
        for line in C4_LINES:
            vals = [self.at(s, r, c) for r, c in line]
            mine, theirs = vals.count(player), vals.count(opp)
            if mine and not theirs:
                score += (1, 4, 20)[mine - 1] if mine < 4 else 0
            elif theirs and not mine:
                score -= (1, 5, 25)[theirs - 1] if theirs < 4 else 0
        score += 3 * (sum(1 for x in s[0][3] if x == player) - sum(1 for x in s[0][3] if x == opp))
        return score

    def key(self, s):
        return (s[0], s[1])


# ===================================================================== Nim ====

class Nim(Game):
    """state = (heaps, player to move 0/1). Normal play: taking the last stone wins."""

    def initial_from(self, heaps):
        return (tuple(heaps), 0)

    def to_move(self, s):
        return s[1]

    def moves(self, s):
        return [(i, k) for i, h in enumerate(s[0]) for k in range(1, h + 1)]

    def order(self, s, moves):
        return sorted(moves, key=lambda m: -m[1])

    def result(self, s, m):
        i, k = m
        heaps = list(s[0])
        heaps[i] -= k
        return (tuple(heaps), 1 - s[1])

    def winner(self, s):
        if sum(s[0]) == 0:
            return 1 - s[1]                     # whoever just moved took the last stone
        return None

    def key(self, s):
        return (tuple(sorted(s[0])), s[1])


# ================================================================== Othello ====

DIR8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


class Othello(Game):
    """state = (board tuple n*n with 0/1/2, player to move, passes in a row)."""

    def __init__(self, n: int = 8):
        self.n = n
        w = [[0] * n for _ in range(n)]
        for r in range(n):
            for c in range(n):
                edge_r, edge_c = r in (0, n - 1), c in (0, n - 1)
                near_r, near_c = r in (1, n - 2), c in (1, n - 2)
                w[r][c] = 1
                if edge_r and edge_c:
                    w[r][c] = 30
                elif (near_r and near_c) :
                    w[r][c] = -12
                elif (edge_r and near_c) or (near_r and edge_c):
                    w[r][c] = -6
                elif edge_r or edge_c:
                    w[r][c] = 5
        self.weights = [x for row in w for x in row]

    def initial(self):
        n = self.n
        b = [0] * (n * n)
        m = n // 2
        b[(m - 1) * n + m - 1] = b[m * n + m] = 2
        b[(m - 1) * n + m] = b[m * n + m - 1] = 1
        return (tuple(b), 1, 0)

    def to_move(self, s):
        return s[1]

    def _flips(self, b, idx, p):
        n = self.n
        r0, c0 = divmod(idx, n)
        out = []
        for dr, dc in DIR8:
            r, c, run = r0 + dr, c0 + dc, []
            while 0 <= r < n and 0 <= c < n and b[r * n + c] == 3 - p:
                run.append(r * n + c)
                r, c = r + dr, c + dc
            if run and 0 <= r < n and 0 <= c < n and b[r * n + c] == p:
                out.extend(run)
        return out

    def legal(self, b, p):
        return [i for i in range(len(b)) if b[i] == 0 and self._flips(b, i, p)]

    def moves(self, s):
        ms = self.legal(s[0], s[1])
        if ms:
            return ms
        if s[2] == 0 and self.legal(s[0], 3 - s[1]):
            return ["pass"]
        return []

    def order(self, s, moves):
        return sorted(moves, key=lambda m: -self.weights[m] if m != "pass" else 0)

    def result(self, s, m):
        if m == "pass":
            return (s[0], 3 - s[1], s[2] + 1)
        b = list(s[0])
        for i in self._flips(s[0], m, s[1]) + [m]:
            b[i] = s[1]
        return (tuple(b), 3 - s[1], 0)

    def winner(self, s):
        if self.moves(s):
            return None
        a, b = s[0].count(1), s[0].count(2)
        return 1 if a > b else 2 if b > a else "draw"

    def evaluate(self, s, player):
        b = s[0]
        pos = sum(self.weights[i] * (1 if v == player else -1) for i, v in enumerate(b) if v)
        mob = len(self.legal(b, player)) - len(self.legal(b, 3 - player))
        return pos + 4 * mob


# ===================================================================== Hex ====

HEX_NBRS = [(-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0)]


class Hex(Game):
    """state = (board tuple n*n, player to move). Player 1 links top to
    bottom, player 2 links left to right."""

    def __init__(self, n: int = 5):
        self.n = n

    def initial(self):
        return (tuple([0] * (self.n * self.n)), 1)

    def to_move(self, s):
        return s[1]

    def moves(self, s):
        return [i for i, v in enumerate(s[0]) if v == 0]

    def order(self, s, moves):
        n = self.n
        mid = (n - 1) / 2
        return sorted(moves, key=lambda i: abs(i // n - mid) + abs(i % n - mid))

    def result(self, s, i):
        b = list(s[0])
        b[i] = s[1]
        return (tuple(b), 3 - s[1])

    def connected(self, b, p) -> bool:
        n = self.n
        starts = [i for i in range(n) if b[i] == p] if p == 1 else \
                 [r * n for r in range(n) if b[r * n] == p]
        seen = set(starts)
        q = deque(starts)
        while q:
            i = q.popleft()
            r, c = divmod(i, n)
            if (p == 1 and r == n - 1) or (p == 2 and c == n - 1):
                return True
            for dr, dc in HEX_NBRS:
                rr, cc = r + dr, c + dc
                j = rr * n + cc
                if 0 <= rr < n and 0 <= cc < n and j not in seen and b[j] == p:
                    seen.add(j)
                    q.append(j)
        return False

    def winner(self, s):
        if self.connected(s[0], 1):
            return 1
        if self.connected(s[0], 2):
            return 2
        return None

    def distance(self, b, p) -> int:
        """Fewest empty cells p still needs to fill to connect (0-1 BFS)."""
        n = self.n
        INF = 10 ** 6
        dist = [INF] * (n * n)
        dq = deque()
        for k in range(n):
            i = k if p == 1 else k * n
            if b[i] == 3 - p:
                continue
            dist[i] = 0 if b[i] == p else 1
            (dq.appendleft if b[i] == p else dq.append)(i)
        while dq:
            i = dq.popleft()
            r, c = divmod(i, n)
            for dr, dc in HEX_NBRS:
                rr, cc = r + dr, c + dc
                if 0 <= rr < n and 0 <= cc < n:
                    j = rr * n + cc
                    if b[j] == 3 - p:
                        continue
                    w = 0 if b[j] == p else 1
                    if dist[i] + w < dist[j]:
                        dist[j] = dist[i] + w
                        (dq.appendleft if w == 0 else dq.append)(j)
        ends = [(n - 1) * n + k for k in range(n)] if p == 1 else [k * n + n - 1 for k in range(n)]
        return min(dist[i] for i in ends)

    def evaluate(self, s, player):
        return 10 * (self.distance(s[0], 3 - player) - self.distance(s[0], player))


# ============================================================ Chess tactics ====

class ChessTactics(Game):
    """Positions are FEN strings; legal moves come from python-chess."""

    def __init__(self):
        import chess
        self.chess = chess

    def board(self, fen):
        return self.chess.Board(fen)

    def to_move(self, fen):
        return "white" if " w " in fen else "black"

    def moves(self, fen):
        return [m.uci() for m in self.board(fen).legal_moves]

    def order(self, fen, moves):
        b = self.board(fen)

        def rank(u):
            m = self.chess.Move.from_uci(u)
            return (not b.gives_check(m), not b.is_capture(m))
        return sorted(moves, key=rank)

    def result(self, fen, u):
        b = self.board(fen)
        b.push(self.chess.Move.from_uci(u))
        return b.fen()

    def winner(self, fen):
        b = self.board(fen)
        if b.is_checkmate():
            return "black" if b.turn else "white"
        if b.is_stalemate() or b.is_insufficient_material():
            return "draw"
        return None

    def key(self, fen):
        return " ".join(fen.split(" ")[:4])

    def san_line(self, fen, line):
        b = self.board(fen)
        out = []
        for u in line:
            m = self.chess.Move.from_uci(u)
            out.append(b.san(m))
            b.push(m)
        return out


CHESS_PUZZLES = [
    {"id": "backrank", "name": "Back-rank mate", "moves": 1,
     "fen": "6k1/5ppp/8/8/8/8/5PPP/R5K1 w - - 0 1"},
    {"id": "scholar", "name": "Scholar's mate", "moves": 1,
     "fen": "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4"},
    {"id": "arabian", "name": "Arabian mate", "moves": 1,
     "fen": "7k/7p/5N2/8/8/8/8/6RK w - - 0 1"},
    {"id": "morphy", "name": "Morphy's problem", "moves": 2,
     "fen": "kbK5/pp6/1P6/8/8/8/8/R7 w - - 0 1"},
    {"id": "smothered", "name": "Smothered mate", "moves": 2,
     "fen": "5r1k/6pp/7N/3Q4/8/8/8/7K w - - 0 1"},
    {"id": "ladder", "name": "Rook ladder", "moves": 2,
     "fen": "6k1/8/8/8/8/8/R7/1R4K1 w - - 0 1"},
]
