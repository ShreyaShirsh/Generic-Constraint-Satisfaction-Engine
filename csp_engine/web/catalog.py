"""The problem catalogue: what every problem is, and how it becomes a CSP.

Pure data -- the HTTP handlers are in problems_api.py. The `formulation`
text of every entry follows the same three lines (variables / domains /
constraints) because every problem really is the same object to the engine.
"""
from __future__ import annotations

CATEGORIES = [
    ("reasoning", "Reasoning", "Logic and number puzzles: the classic home of constraint satisfaction."),
    ("search", "Search", "Find a sequence of moves. Planning becomes a CSP whose variables are the steps."),
    ("strategy", "Strategy", "Two players. Games become quantified CSPs: ∃ my move ∀ your reply …"),
    ("graphs", "Graphs and Optimization", "Colour, route and pack. Optimisation = CSP + one 'better than the best' predicate."),
    ("planning", "Planning and Learning", "Robots, schedules and teams of agents — plus one learning algorithm as a contrast."),
    ("spatial", "Visual and Spatial", "Pieces, shapes and cubes: placement variables with 'no overlap' constraints."),
]

P = []


def _p(pid, name, cat, summary, variables, domains, constraints, kind, one, extra=None):
    P.append({"id": pid, "name": name, "category": cat, "summary": summary,
              "formulation": {"variables": variables, "domains": domains, "constraints": constraints},
              "kind": kind, "one_constraint": one, **(extra or {})})


# ------------------------------------------------------------------ reasoning
_p("zebra", "Zebra Logic", "reasoning",
   "Einstein's riddle — and brand-new riddles the engine invents, with a coach that cites the clues.",
   "one per (category, value) — e.g. ‘the Englishman’, ‘the red house’",
   "which house (1–5) holds it",
   "all-different inside each category; each clue is one binary relation (same house, next to, right of …)",
   "csp", "Every clue is a BinaryRelation; every category is a set of ≠ constraints.")
_p("sudoku", "Sudoku", "reasoning",
   "Sudoku and its relatives (X-Sudoku, Killer, KenKen, Futoshiki) live in the Puzzle Studio.",
   "the 81 cells", "1–9", "≠ between every two cells sharing a row, column or box (810 of them)",
   "link", "100% of the constraints are ≠.", {"href": "/studio"})
_p("crypto", "Cryptarithmetic", "reasoning",
   "SEND + MORE = MONEY, classic puzzles and new ones generated from a word list.",
   "one per letter, plus a carry for every column", "digits 0–9 (carries 0–2)",
   "all letters different; one predicate per column: digits + carry-in = result + 10 × carry-out",
   "csp", "≠ between letters, plus one arithmetic predicate per column.")
_p("knights", "Knights and Knaves", "reasoning",
   "Knights always tell the truth, knaves always lie. Who is who? Generated puzzles with a coach.",
   "one per islander", "{knight, knave}",
   "one predicate per statement: ‘the speaker is a knight ⇔ the statement is true’",
   "csp", "Every statement is a single Predicate.")
_p("minesweeper", "Minesweeper", "reasoning",
   "Play with an AI assistant that proves which cells are safe and computes exact mine odds.",
   "every covered cell next to a revealed number", "{safe, mine}",
   "one predicate per revealed number N: ‘exactly N mines among my covered neighbours’",
   "csp", "Each number on the board is one Predicate.")

# --------------------------------------------------------------------- search
_p("maze", "Maze Escape", "search",
   "Random mazes; the shortest escape found by iterative deepening on a planning CSP.",
   "step₁ … step_T — the move taken at each time step", "{up, down, left, right}",
   "ONE predicate over all steps: ‘legal, never revisits a cell, can still reach the exit in time, ends at the exit’",
   "plan", "The whole search problem is one Predicate over the step variables.")
_p("eight", "8-Puzzle", "search",
   "Slide the tiles yourself or watch the engine find the optimal solution.",
   "step₁ … step_T", "which way the blank moves",
   "one ‘legal plan reaching the goal’ predicate; Manhattan distance bounds what is still possible",
   "plan", "One Predicate; the Manhattan bound turns plain backtracking into IDA*.")
_p("hanoi", "Tower of Hanoi", "search",
   "Any number of disks from any position — compare no heuristic, a weak one and an exact one.",
   "step₁ … step_T", "the six peg-to-peg moves",
   "one predicate: legal moves (never a big disk on a small one), ends with every disk on peg C",
   "plan", "One Predicate over the moves.")
_p("river", "River Crossing", "search",
   "Farmer, wolf, goat and cabbage; missionaries and cannibals with any numbers.",
   "step₁ … step_T", "who rides in the boat",
   "one predicate: nobody is ever eaten, everyone ends on the far bank",
   "plan", "One Predicate over the crossings.")
_p("sokoban", "Sokoban", "search",
   "Push every box onto a goal — play the levels or watch the optimal solution.",
   "step₁ … step_T", "{up, down, left, right}",
   "one predicate: legal pushes, no box in a dead square, all boxes on goals at the end",
   "plan", "One Predicate over the moves.")

# ------------------------------------------------------------------- strategy
_p("connect4", "Connect Four", "strategy",
   "Play against the engine; it looks ahead with quantified search (minimax + alpha-beta).",
   "m₁, m₂, … — the column played on each turn", "the 7 columns",
   "∃ m₁ ∀ m₂ ∃ m₃ … WIN(m₁, m₂, …) — one win predicate, alternating quantifiers",
   "game", "One WIN predicate; only the quantifiers are new.")
_p("chess", "Chess Tactics", "strategy",
   "Mate-in-1 and mate-in-2 puzzles proved by a quantified CSP; try to find the move yourself.",
   "m₁, m₂, m₃ — White, Black, White", "the legal moves",
   "∃ m₁ ∀ m₂ ∃ m₃ : CHECKMATE(m₁, m₂, m₃)",
   "game", "One CHECKMATE predicate under ∃∀∃.")
_p("nim", "Nim", "strategy",
   "The engine proves which positions are won — and rediscovers the famous nim-sum rule.",
   "m₁, m₂, … — (heap, stones taken)", "every legal take",
   "∃ m₁ ∀ m₂ … ‘I take the last stone’",
   "game", "One WIN predicate.")
_p("othello", "Othello", "strategy",
   "Reversi against the engine on an 8×8 board.",
   "m₁, m₂, …", "the legal placements",
   "∃ m₁ ∀ m₂ … maximise the disc/position score — quantified optimisation",
   "game", "One scoring predicate under alternating quantifiers.")
_p("hex", "Hex", "strategy",
   "Connect your two sides. Small boards are solved outright — the first player always wins.",
   "m₁, m₂, …", "the empty cells",
   "∃ m₁ ∀ m₂ … CONNECTED(top, bottom)",
   "game", "One connectivity predicate.")

# ------------------------------------------------------------------- graphs
_p("map", "Map Colouring", "graphs",
   "Random political maps and Australia — race algorithms, colour it yourself, find the fewest colours.",
   "one per region", "the colours",
   "≠ between every two neighbouring regions",
   "csp", "100% of the constraints are ≠.")
_p("tsp", "Travelling Salesman", "graphs",
   "The shortest tour through random cities, proved optimal by branch and bound.",
   "pos₁ … pos_n — the city visited k-th", "the cities",
   "all-different (each city once) + ONE predicate: ‘this partial tour can still beat the best so far’",
   "opt", "≠ between positions, plus one bound Predicate.")
_p("shortest", "Shortest Path", "graphs",
   "Cheapest route across a random road network — checked against Dijkstra.",
   "step₁ … step_T — the next junction", "the junctions",
   "one predicate: consecutive junctions are joined by a road, total cost within the bound",
   "plan", "One Predicate over the route.")
_p("exam", "Exam Scheduling", "graphs",
   "Random enrolments; the fewest time slots with no student clash — it is graph colouring.",
   "one per exam", "the time slots",
   "≠ between any two exams that share a student",
   "csp", "100% of the constraints are ≠.")
_p("knapsack", "Knapsack", "graphs",
   "Pack the most valuable bag within the weight limit — optimal, not greedy.",
   "take_i for every item", "{take, leave}",
   "one capacity predicate + one ‘can still beat the best value’ predicate",
   "opt", "Two Predicates.")

# ------------------------------------------------------------------ planning
_p("treasure", "Robot Treasure Hunt", "planning",
   "Collect every treasure and reach the exit by the shortest route.",
   "visit₁ … visit_k — which treasure to collect k-th", "the treasures",
   "all-different + the branch-and-bound predicate; every leg is itself a planning CSP",
   "opt", "≠ between visit slots, plus one bound Predicate.")
_p("gridworld", "Gridworld", "planning",
   "Reach the best gem without falling into a pit — planned from the rules, no trial and error.",
   "step₁ … step_T", "{up, down, left, right}",
   "one predicate: never steps on a pit, ends on a gem",
   "plan", "One Predicate over the moves.")
_p("resource", "Resource Planning", "planning",
   "Schedule a construction project with limited crew and one crane; minimise the finish time.",
   "start time of every task", "0 … horizon",
   "‘A before B’ binary relations + one capacity predicate per resource + the bound predicate",
   "opt", "BinaryRelations and Predicates — nothing else.")
_p("qlearning", "Q-Learning (contrast)", "planning",
   "The one learning algorithm in the project, run beside the CSP planner on the same gridworld.",
   "—", "—", "none: it learns by trial and error instead of reasoning from constraints",
   "contrast", "No constraints at all — that is the point of the comparison.")
_p("mapf", "Multi-Agent Coordination", "planning",
   "Several robots reach their goals at once without colliding.",
   "position of agent a at time t", "the free cells",
   "‘moves one cell per tick’ relations, ≠ between agents at every tick, no swapping",
   "csp", "Mostly ≠ constraints.")

# ------------------------------------------------------------------- spatial
_p("tangram", "Tangram", "spatial",
   "Fill a silhouette with the seven tans (on a lattice where every piece edge is straight or diagonal).",
   "the 7 tans", "every position and rotation that fits inside the silhouette",
   "for every pair of tans: ‘they don't overlap’",
   "csp", "Every constraint is a pairwise no-overlap BinaryRelation.")
_p("rubiks", "Rubik's Cube", "spatial",
   "The 2×2×2 pocket cube from any scramble, solved optimally.",
   "step₁ … step_T", "U, R, F turns (quarter, inverse, half)",
   "one predicate: the turns end in a solved cube; pattern databases bound the moves still needed",
   "plan", "One Predicate over the turns.")
_p("jigsaw", "Jigsaw", "spatial",
   "Shuffled, rotated pieces put back together by matching their edges.",
   "the slots of the frame", "(piece, rotation)",
   "neighbouring edges fit; ≠ on the piece used in any two slots; flat edges face outwards",
   "csp", "Mostly ≠ plus edge-fit BinaryRelations.")
_p("polyomino", "Polyomino Tiling", "spatial",
   "Tile a shape with pentominoes — presets and random shapes.",
   "the pieces", "every placement inside the shape",
   "for every pair of pieces: ‘they don't overlap’",
   "csp", "Every constraint is a pairwise no-overlap BinaryRelation.")
_p("folding", "Shape Folding", "spatial",
   "Does a net fold into a cube? The engine checks all 35 hexominoes and finds the 11 that do.",
   "the squares of the net", "the 24 ways a cube can rest on a square",
   "rolling onto a neighbour gives its orientation; ≠ between the faces landing on any two squares",
   "csp", "Rolling BinaryRelations plus ≠.")

BY_ID = {p["id"]: p for p in P}
