"""Q-learning -- deliberately OUTSIDE the engine.

The engine never learns: it reasons from the rules. This module is the one
place in the project that learns from experience, and it exists only as a
contrast on the gridworld page: the CSP planner derives the best route
directly from the rules in one search, while a Q-learning agent has to
stumble through hundreds of episodes of trial and error to discover the
same route. Nothing in core/ or problems/ imports this file.
"""
from __future__ import annotations
import random

MOVES = {"U": (-1, 0), "D": (1, 0), "L": (0, -1), "R": (0, 1)}


def q_learning(inst: dict, episodes: int = 400, alpha: float = 0.5, gamma: float = 0.95,
               epsilon: float = 0.2, slip: float = 0.0, seed: int | None = 0,
               max_steps: int = 200) -> dict:
    rng = random.Random(seed)
    grid = inst["grid"]
    rows, cols = len(grid), len(grid[0])
    gems = {tuple(g["cell"]): g["reward"] for g in inst["gems"]}
    pits = {tuple(p) for p in inst["pits"]}
    step = -inst.get("step_cost", 1)
    start = tuple(inst["start"])
    Q: dict = {}

    def q(s):
        return Q.setdefault(s, {a: 0.0 for a in MOVES})

    def move(s, a):
        if slip and rng.random() < slip:
            a = rng.choice(list(MOVES))
        dr, dc = MOVES[a]
        r, c = s[0] + dr, s[1] + dc
        if 0 <= r < rows and 0 <= c < cols and not grid[r][c]:
            return (r, c)
        return s

    history, first_success, experience = [], None, 0
    for ep in range(episodes):
        s, total = start, 0.0
        for _ in range(max_steps):
            qs = q(s)
            a = rng.choice(list(MOVES)) if rng.random() < epsilon else max(qs, key=qs.get)
            n = move(s, a)
            if n in gems:
                r, done = gems[n] + step, True
            elif n in pits:
                r, done = -10 + step, True
            else:
                r, done = step, False
            target = r if done else r + gamma * max(q(n).values())
            qs[a] += alpha * (target - qs[a])
            total += r
            experience += 1
            s = n
            if done:
                if n in gems and first_success is None:
                    first_success = ep + 1
                break
        history.append(round(total, 2))

    policy = {}
    for r in range(rows):
        for c in range(cols):
            if not grid[r][c] and (r, c) not in gems and (r, c) not in pits and (r, c) in Q:
                policy[f"{r},{c}"] = max(Q[(r, c)], key=Q[(r, c)].get)

    # follow the learned greedy policy from the start
    path, s, seen = [list(start)], start, {start}
    for _ in range(rows * cols):
        if s in gems or s in pits or s not in Q:
            break
        a = max(Q[s], key=Q[s].get)
        dr, dc = MOVES[a]
        n = (s[0] + dr, s[1] + dc)
        if not (0 <= n[0] < rows and 0 <= n[1] < cols) or grid[n[0]][n[1]] or n in seen:
            break
        path.append(list(n))
        seen.add(n)
        s = n
    reached = gems.get(s)
    return {"policy": policy, "returns": history, "first_success": first_success,
            "greedy_path": path, "greedy_reward": (reached + step * (len(path) - 1)) if reached else None,
            "episodes": episodes, "experience_steps": experience}
