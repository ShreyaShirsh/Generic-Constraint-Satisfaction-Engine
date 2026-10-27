"""Games as Quantified CSPs.

A game question like "can White force mate in 2?" or "is this Nim position a
win?" is a CSP over move variables m1, m2, m3, ... with ONE constraint,

    WIN(m1, m2, ..., mD):  "playing these moves is legal and the position
                            reached is won for the player who moved first"

-- except that the variables are QUANTIFIED, alternating between the two
players:   ∃ m1  ∀ m2  ∃ m3  ...  WIN(m1, ..., mD)
("there is a move of mine such that for every reply there is a move of mine
such that ... I win"). A plain CSP is the special case where every variable
is ∃. The solver below is backtracking generalised to quantifiers: an ∃
variable needs ONE value that works, a ∀ variable needs ALL values to work.

When a game is too big to prove a forced result, the same quantified search
optimises a heuristic score instead of a yes/no WIN predicate (minimax with
alpha-beta pruning) -- the ∃/∀ structure is unchanged.
"""
from __future__ import annotations
import math
import time
from typing import Any, Hashable, Optional


class Game:
    """Describe the rules; never search."""
    def to_move(self, state) -> int: raise NotImplementedError
    def moves(self, state) -> list: raise NotImplementedError
    def result(self, state, move): raise NotImplementedError

    def winner(self, state):
        """None while the game is running, else the winning player id, or
        'draw' for a finished game with no winner."""
        raise NotImplementedError

    def evaluate(self, state, player: int) -> float:
        """Heuristic score of a non-final position from `player`'s view."""
        return 0.0

    def key(self, state) -> Hashable:
        return state

    def order(self, state, moves: list) -> list:
        return moves


class Stats:
    def __init__(self):
        self.nodes = 0
        self.t0 = time.perf_counter()

    def elapsed_ms(self) -> float:
        return round((time.perf_counter() - self.t0) * 1000, 2)


class Budget(Exception):
    pass


def prove_win(game: Game, state, depth: int, max_nodes: int = 2_000_000) -> dict:
    """Solve ∃ m1 ∀ m2 ∃ m3 ... WIN for the player to move, within `depth`
    moves (plies). Returns {"win": bool|None, "line": [...], "nodes", "ms"}
    -- win is None if the node budget ran out."""
    player = game.to_move(state)
    stats = Stats()
    memo: dict = {}

    def won(s, d) -> bool:
        stats.nodes += 1
        if stats.nodes > max_nodes:
            raise Budget()
        w = game.winner(s)
        if w is not None:
            return w == player
        if d == 0:
            return False
        k = (game.key(s), d)
        if k in memo:
            return memo[k]
        ms = game.order(s, game.moves(s))
        if game.to_move(s) == player:                          # ∃: one move suffices
            r = any(won(game.result(s, m), d - 1) for m in ms)
        else:                                                   # ∀: every reply must lose
            r = bool(ms) and all(won(game.result(s, m), d - 1) for m in ms)
        memo[k] = r
        return r

    def line(s, d) -> list:
        out = []
        while d > 0 and game.winner(s) is None:
            ms = game.order(s, game.moves(s))
            if not ms:
                break
            if game.to_move(s) == player:
                m = next((m for m in ms if won(game.result(s, m), d - 1)), None)
            else:                                               # the toughest defence
                m = max(ms, key=lambda m: _resistance(game.result(s, m), d - 1))
            if m is None:
                break
            out.append(m)
            s, d = game.result(s, m), d - 1
        return out

    def _resistance(s, d) -> int:
        for dd in range(0, d + 1):
            if won(s, dd):
                return -dd
        return 1

    try:
        # iterative deepening finds the SHORTEST forced win
        for d in range(1, depth + 1):
            if won(state, d):
                return {"win": True, "depth": d, "line": line(state, d),
                        "nodes": stats.nodes, "ms": stats.elapsed_ms()}
        return {"win": False, "depth": depth, "line": [], "nodes": stats.nodes,
                "ms": stats.elapsed_ms()}
    except Budget:
        return {"win": None, "depth": depth, "line": [], "nodes": stats.nodes,
                "ms": stats.elapsed_ms()}


WIN_SCORE = 1_000_000


def best_move(game: Game, state, depth: int, time_budget: float = 3.0) -> dict:
    """Quantified optimisation: ∃ my move ∀ reply ∃ ... maximise the score,
    i.e. minimax with alpha-beta pruning and a transposition table, deepened
    iteratively until the time budget runs out. Returns {"move", "score",
    "line", "depth", "nodes", "ms"}."""
    player = game.to_move(state)
    stats = Stats()
    deadline = time.perf_counter() + time_budget
    table: dict = {}

    def value(s, d, alpha, beta, ply) -> float:
        stats.nodes += 1
        if stats.nodes % 2048 == 0 and time.perf_counter() > deadline:
            raise Budget()
        w = game.winner(s)
        if w is not None:
            if w == "draw":
                return 0
            return (WIN_SCORE - ply) if w == player else -(WIN_SCORE - ply)
        if d == 0:
            return game.evaluate(s, player)
        k = (game.key(s), d)
        if k in table:
            return table[k]
        a0, b0 = alpha, beta
        ms = game.order(s, game.moves(s))
        if not ms:
            return game.evaluate(s, player)
        if game.to_move(s) == player:                           # ∃ -> max
            v = -math.inf
            for m in ms:
                v = max(v, value(game.result(s, m), d - 1, alpha, beta, ply + 1))
                alpha = max(alpha, v)
                if alpha >= beta:
                    break
        else:                                                   # ∀ -> min
            v = math.inf
            for m in ms:
                v = min(v, value(game.result(s, m), d - 1, alpha, beta, ply + 1))
                beta = min(beta, v)
                if alpha >= beta:
                    break
        if a0 < v < b0:
            table[k] = v
        return v

    best = {"move": None, "score": 0, "depth": 0}
    moves = game.order(state, game.moves(state))
    if not moves:
        return {**best, "line": [], "nodes": 0, "ms": 0}
    best["move"] = moves[0]
    try:
        for d in range(1, depth + 1):
            scored = []
            alpha = -math.inf
            for m in moves:
                v = value(game.result(state, m), d - 1, alpha, math.inf, 1)
                alpha = max(alpha, v)
                scored.append((v, m))
            scored.sort(key=lambda x: -x[0])
            best = {"move": scored[0][1], "score": scored[0][0], "depth": d}
            moves = [m for _, m in scored]                       # best first next round
            if abs(scored[0][0]) >= WIN_SCORE - 100:
                break
    except Budget:
        pass
    return {**best, "nodes": stats.nodes, "ms": stats.elapsed_ms()}


def winning_moves(game: Game, state, depth: int, max_nodes: int = 2_000_000) -> dict:
    """Which values of the first ∃-variable satisfy  ∀ m2 ∃ m3 ... WIN
    within `depth` plies? Returns {"moves": {move: True/False}, "nodes"}."""
    player = game.to_move(state)
    stats = Stats()
    memo: dict = {}

    def won(s, d) -> bool:
        stats.nodes += 1
        if stats.nodes > max_nodes:
            raise Budget()
        w = game.winner(s)
        if w is not None:
            return w == player
        if d == 0:
            return False
        k = (game.key(s), d)
        if k in memo:
            return memo[k]
        ms = game.order(s, game.moves(s))
        if game.to_move(s) == player:
            r = any(won(game.result(s, m), d - 1) for m in ms)
        else:
            r = bool(ms) and all(won(game.result(s, m), d - 1) for m in ms)
        memo[k] = r
        return r

    out = {}
    try:
        for m in game.order(state, game.moves(state)):
            out[m] = won(game.result(state, m), depth - 1)
    except Budget:
        return {"moves": None, "nodes": stats.nodes, "ms": stats.elapsed_ms()}
    return {"moves": out, "nodes": stats.nodes, "ms": stats.elapsed_ms()}
