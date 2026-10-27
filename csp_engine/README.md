# A Generic Constraint Satisfaction Engine (BITE308L)

One general-purpose constraint-satisfaction solver that solves **thirty**
structurally different problems — logic riddles, Sudoku, sliding puzzles,
Sokoban, chess tactics, Connect Four, map colouring, TSP, scheduling, robot
teams, jigsaws, tangrams and more — from a single, untouched `core/`
package. No problem is hardcoded into the solver; every problem is described
as data and handed to the same engine.

## The thirty problems, and how each becomes the same CSP

| Category | Problems | Variables | The constraint(s) |
|---|---|---|---|
| Reasoning | Zebra, Sudoku, Cryptarithmetic, Knights & Knaves, Minesweeper | cells / letters / people | ≠ (all-different) + one Predicate per clue, column, statement or number |
| Search | Maze, 8-Puzzle, Tower of Hanoi, River Crossing, Sokoban | the move at step 1 … T | **one** Predicate: "the plan is legal and reaches the goal" |
| Strategy | Connect Four, Chess tactics, Nim, Othello, Hex | m₁, m₂, … (quantified ∃ ∀ ∃ …) | **one** WIN predicate (or a score, for minimax) |
| Graphs & optimisation | Map colouring, TSP, Shortest path, Exam scheduling, Knapsack | regions / tour positions / items | ≠, plus **one** "better than the best so far" Predicate |
| Planning & learning | Robot treasure hunt, Gridworld, Resource planning, Multi-agent paths, Q-learning (contrast) | visit order / start times / positions over time | ≠, "A before B", capacity Predicates, the plan predicate |
| Visual & spatial | Tangram, Rubik's cube (2×2), Jigsaw, Polyomino tiling, Cube-net folding | pieces / slots / squares | pairwise "no overlap" / "edges fit" / ≠ |

Every problem page shows a **constraint census** of the instance on screen —
how many variables and constraints it compiled into, by kind, and what share
are plain ≠. That table is the per-problem answer to the faculty question
below. Q-learning is the one deliberate exception: it lives in
`contrast/`, outside the engine, purely to show what *learning* by trial and
error costs compared with *reasoning* from constraints.

## "What is the one constraint your engine is built on?"

Not a single rule like "all-different" — the **predicate abstraction
itself**. Every constraint in this project, no matter the problem, reduces
to one definition:

```
a Constraint is a boolean predicate over a tuple of variables:
    is_satisfied(assignment) -> bool
```

The solver (`core/backtracking.py`) never asks what a variable *means*. It
calls `constraint.is_satisfied(assignment)` and nothing else. It cannot
tell "two queens share a diagonal" apart from "two exams share a student" —
to the solver, those are the same shape of object.

Concretely, every constraint in the engine is built from exactly **two**
reusable primitives in `core/constraints.py`:

| Primitive | Arity | Used for |
|---|---|---|
| `BinaryRelation(x, y, predicate)` | 2 | "not equal" (queens, map colouring, Sudoku peers), "equal"/"right-of"/"next-to" (Zebra puzzle) |
| `Predicate(variables, predicate)` | n | the column-sum-with-carry equations of cryptarithmetic, `sum_equals` in the custom-CSP playground |

`AllDifferent` is **not** a third primitive — `core/constraints.py:all_different()`
is sugar that expands an n-ary "all distinct" requirement into pairwise
`BinaryRelation` objects, which is why Sudoku's "every row/column/box has 9
different digits" reuses the exact same machinery (and the exact same AC-3
propagator) as N-Queens' "no two queens share a row".

The clearest proof this is genuinely generic, not five solvers wearing a
trenchcoat, is the **Custom CSP playground** in the web demo: you type any
`(variables, domains, constraints)` JSON description at runtime and it is
solved by the identical engine, through `web/custom_csp.py`, which itself
is built from nothing but `BinaryRelation`, `Predicate` and `all_different`.

## Novelty: the Puzzle Studio

The Studio (`/studio` in the web demo) turns the engine into something you
can watch, play with and extend. Every feature is generic — it works on any
grid puzzle, including ones that didn't exist until a user drew them:

| Mode | What it does | Engine piece behind it |
|---|---|---|
| **Watch the AI** | Two search strategies race on the same puzzle; candidates disappear as propagation prunes them, guesses go in, dead ends flash red | `tracer` hook in `core/backtracking.py` records every assign / prune / restore / backtrack |
| **Play** | You solve; broken rules light up live; the coach gives the easiest *logical* next step and explains it in plain English ("R5C5 must be 5: 1, 3, 4, 8 are already used in row 5; ...") | `core/explain.py` — a human-style reasoner that only fills a cell when constraints force it, remembering which constraint ruled out each value |
| **Generate** | Endless puzzles (Sudoku, X-Sudoku, Futoshiki, KenKen, Killer Sudoku) with a guaranteed unique solution, graded Easy / Medium / Hard / Expert | `core/generator.py` — random solution, then remove givens while still unique (proved by re-solving), then grade and add givens back if too hard |
| **Build your own** | Pick a grid, switch rules on, draw regions / cages / inequalities — then Analyze (compiled constraint counts, solution count), Make it a puzzle, Play it, Watch it | `problems/grid_puzzle.py` — one declarative spec compiles *any* grid puzzle into `BinaryRelation` / `Predicate` objects |

**Difficulty grading is defined by reasoning, not by clue count.** The
reasoner always takes the easiest available step; a puzzle's grade is the
hardest step it ever *needed*:

1. **Easy** — direct elimination (a value is already used by a constraint whose other cells are filled)
2. **Medium** — "only place left": a value fits in just one cell of a group that must contain every value
3. **Hard** — advanced reasoning: generalised arc consistency over cage arithmetic and inequality chains, naked subsets, group intersections
4. **Expert** — logic alone runs out; the engine itself would have to guess

**Engine upgrades the Studio needed (all problem-agnostic):**
- *Generalised arc consistency* — AC-3/MAC now also revise n-ary constraints
  (cage sums, cryptarithmetic columns) by enumerating satisfying tuples.
  SEND+MORE=MONEY went from ~9,900 search nodes to 24.
- *Pigeonhole propagation* (`mac_plus`) — if k all-different variables have
  only k candidate values between them, each value must appear exactly once;
  pairwise not-equal constraints can't see this. The Expert Sudoku preset
  goes from a 200,000-node timeout (naive) to 81 nodes and zero backtracks.
- A precomputed constraint graph and a copy-free consistency check made
  plain backtracking roughly 200x faster.

## Three generalisations — still one constraint

Search, optimisation and games don't look like Sudoku, so the engine has
three thin layers that turn them into the same object instead of adding new
solvers:

- **Planning as CSP** (`core/planning.py`) — variables are the action at each
  time step; ONE Predicate re-simulates the prefix and accepts it only if it
  is legal, never revisits a state, can still reach the goal within the
  budget (an admissible lower bound), and ends at the goal. Iterative
  deepening on the number of steps makes plain backtracking behave like IDA*:
  the first horizon with a solution is optimal.
- **Optimisation as CSP** (`core/optimize.py`) — branch and bound is the
  ordinary CSP plus ONE more Predicate, "bound(partial) < best so far", that
  silently tightens every time a better solution is found.
- **Games as quantified CSPs** (`core/adversarial.py`) — "can White force mate
  in 2?" is ∃ m₁ ∀ m₂ ∃ m₃ : CHECKMATE(m₁, m₂, m₃). The solver is backtracking
  generalised to quantifiers (∃ needs one value, ∀ needs all); with a score
  instead of a yes/no predicate it is minimax with alpha-beta pruning.

## Layout

```
core/            problem-agnostic engine -- the only file that may NOT import from problems/, cli, or web/
  model.py         CSP container: variables, domains, constraints, neighbours
  constraints.py   BinaryRelation, Predicate, NotEqual, all_different
  backtracking.py  systematic search: first-solution / all-solutions, pluggable hooks, tracer, max_nodes cap
  inference.py     forward checking, generalised AC-3, MAC, MAC + pigeonhole groups
  heuristics.py    MRV, MRV+degree, LCV, shuffled (for generation)
  local_search.py  min-conflicts (a second, contrasting search paradigm)
  explain.py       human-style reasoner: justified steps, hints in words, pencil marks, difficulty grading
  generator.py     generic puzzle generator: random solution, uniqueness-preserving digging, difficulty targeting
  planning.py      planning as CSP: step variables + one "legal plan" predicate, iterative deepening (IDA*)
  optimize.py      branch and bound: the CSP + one "better than the best so far" predicate
  adversarial.py   quantified CSPs for games: prove_win (∃∀∃…), winning_moves, best_move (alpha-beta)
  census.py        what an instance compiled into: constraints by kind, share of ≠
  metrics.py       SearchMetrics -- nodes / backtracks / pruned / time, mandatory instrumentation

problems/        adapters: each file only *describes* a problem as a CSP -- zero solving logic
  nqueens.py           any board size n
  graph_colouring.py   any graph, any palette (Australia map is one named preset)
  sudoku.py            any N^2 x N^2 grid
  cryptarithmetic.py   any two addends + result (SEND+MORE=MONEY is one preset)
  zebra.py             the classic 5-house Einstein puzzle, built from relational BinaryRelations
  exam_scheduling.py   reduces timetabling to graph_colouring_csp -- no new solver code
  grid_puzzle.py       ANY grid puzzle from a JSON spec: rows/cols/boxes/diagonals/regions, cages, inequalities
  puzzle_presets.py    the Studio's ready-made puzzles (generated with fixed seeds -> puzzle_presets.json)
  logic_puzzles.py     Zebra riddles (classic + generator) and Knights & Knaves (generator)
  minesweeper.py       the hidden-mine CSP, exact probabilities, the assistant and autoplayer
  search_puzzles.py    8-puzzle, Hanoi, river crossings, Sokoban, mazes, the 2x2 pocket cube
  games.py             Connect Four, Nim, Othello, Hex, chess tactics (rules only)
  graph_problems.py    random maps, TSP, shortest paths, knapsack, random exam data
  planning_problems.py treasure hunt, gridworld, resource-constrained scheduling, multi-agent paths
  spatial.py           polyomino tiling, lattice tangram, jigsaw, cube-net folding

contrast/        q_learning.py -- the ONLY learning code; never imported by core/ or problems/

web/             Flask demo for the faculty review (optional -- core/ never depends on it)
  app.py            pages: / (gallery), /p/<problem>, /studio, /engine; the original six-problem API
  catalog.py        the 30 problems: category, summary, variables / domains / constraints
  problems_api.py   /api/p/<problem>/<action> -- shared solve / trace / hint / check / census helpers
  studio.py         Puzzle Studio endpoints: trace, check, hint, candidates, generate, analyze, make, solve
  custom_csp.py     builds a CSP from a user-typed JSON spec using the SAME two primitives above
  templates/, static/   engine overview page (index) + Puzzle Studio page (studio)

cli.py           interactive terminal front-end -- the other I/O layer, same engine
benchmark.py     instrumentation study: same CSPs, same solver, only the technique changes
```

`core/` never imports `problems/`, `cli`, `web`, or any third-party
library. `problems/*.py` never imports a search function from `core/` —
only the CSP container and constraint builders. Delete every file in
`problems/` and the engine still imports and compiles; it would just have
nothing left to solve.

## Techniques implemented

- **Search**: systematic backtracking (`backtracking_search`, first
  solution) and `find_all_solutions` (every distinct solution, capped
  optionally), both sharing one recursive core with pluggable hooks.
- **Propagation**: `forward_checking` (prune newly-inconsistent neighbour
  values after each assignment; n-ary constraints once one variable is left),
  a generalised `ac3` / `mac` (maintaining arc consistency over binary AND
  n-ary constraints), and `mac_plus` (MAC + pigeonhole reasoning over
  all-different groups).
- **Ordering heuristics**: `mrv` (Minimum Remaining Values), `mrv_degree`
  (MRV, ties broken by the degree heuristic), `lcv` (Least Constraining
  Value).
- **Local search**: `min_conflicts` — starts from a complete, usually
  inconsistent assignment and repeatedly repairs the most-conflicted
  variable; a genuinely different paradigm from backtracking, included for
  contrast and dramatically faster on large N-Queens instances.
- **Explanation & grading**: `explain.py` — step-by-step human-style
  deduction with a recorded reason for every eliminated value.
- **Generation**: `generator.py` — uniquely-solvable puzzles for any rule set.
- **Reduction**: `exam_scheduling.py` solves timetabling by building a
  conflict graph (shared students = edges) and handing it straight to
  `graph_colouring_csp` — the instance-level demonstration that one
  "different" problem is really the same problem in disguise.

## Run it

From the directory that contains `csp_engine/` (repo root):

**Terminal / CLI** (standard library only):
```
python -m csp_engine.cli
```
Pick a pattern (N-Queens, map colouring, Sudoku, cryptarithmetic, Zebra,
exam scheduling), pick an algorithm (naive / forward checking / MAC / MAC+MRV
/ MAC+MRV+degree+LCV / MAC+MRV+pigeonhole), then supply your own input —
nothing is hardcoded.

**Web demo** (needs `flask` + `flask-cors`, see `requirements.txt`):
```
pip install -r requirements.txt
python -m csp_engine.web.app
```
Open http://127.0.0.1:5000 — the gallery of all thirty problems, each with
its own interactive page (play it, watch two solvers race, get hints, see
the constraint census). The **Puzzle Studio** is at /studio, and the original
engine page (techniques, Custom CSP playground, benchmark chart) at /engine.

**Instrumentation study** (the "quantify each technique" deliverable):
```
python -m csp_engine.benchmark
```
Runs naive backtracking through MAC+MRV+pigeonhole on seven problems
(including an Expert Sudoku and a Killer Sudoku),
prints a table, and writes `benchmark_results.json` (used by the web demo's
Benchmark tab so the page doesn't need to re-run a 40-second naive search
live). Naive backtracking is capped at 200,000 nodes so a hard instance
(Sudoku, cryptarithmetic) can't run away — a `[TIMED OUT]` row is itself
part of the story: it shows how badly naive search degrades without
propagation.

## Self-tests (fixed inputs on purpose — a test needs a known answer)
```
python -m csp_engine.problems.nqueens          # 4->2, 6->4, 8->92 solutions
python -m csp_engine.problems.graph_colouring  # 3 colours ok, 2 impossible
python -m csp_engine.problems.sudoku           # solves the built-in easy grid
python -m csp_engine.problems.cryptarithmetic  # SEND+MORE=MONEY -> 9567+1085=10652
python -m csp_engine.problems.zebra            # the Japanese owns the zebra
python -m csp_engine.problems.exam_scheduling  # 4-slot timetable, reduced to colouring
```

## Automated test suite

`tests/` has 148 pytest cases covering `core/` in isolation (hand-built tiny
CSPs, independent of any problem adapter), every problem adapter against a
known fact about the puzzle, the Custom CSP spec builder's validation, the
Studio engine (grid compiler, n-ary propagation, tracer replay, every
logical hint matching the unique solution, uniqueness of generated puzzles)
every gallery problem against an independent answer (brute force for TSP
and knapsack, Dijkstra for shortest paths, BFS for the 8-puzzle, 2ⁿ−1 for
Hanoi, nim-sum theory for Nim, the 11 cube nets, verified chess mates), and
every Flask route. Run from the repo root (the one containing `csp_engine/`):
```
pip install -r requirements-dev.txt
python -m pytest tests/ -v
```

## Status
- [x] Engine core — model, binary + n-ary constraints, naive backtracking, metrics
- [x] Forward checking, generic AC-3 / MAC, MRV / degree / LCV ordering heuristics
- [x] Min-conflicts local search (contrasting paradigm)
- [x] All-solutions search
- [x] Patterns — N-Queens, map/graph colouring, Sudoku, cryptarithmetic, Zebra puzzle
- [x] Reduction demo — exam scheduling -> graph colouring, zero new solver code
- [x] Instrumentation study — `benchmark.py`, naive vs FC vs AC-3 vs heuristics
- [x] Interactive CLI — dynamic input, no hardcoded instances
- [x] Web front-end — Flask demo, one tab per problem, live viz, Custom CSP playground, benchmark chart
- [x] Puzzle Studio — watch / play with coach / generate & grade / build your own puzzle type
- [x] Generalised arc consistency (n-ary), pigeonhole propagation, search tracer
- [x] Human-style reasoner (hints, grading) and generic puzzle generator
- [x] Thirty-problem gallery across six categories, each page with a live constraint census
- [x] Planning-as-CSP, branch-and-bound optimisation, quantified CSPs for games
- [x] Automated pytest suite — 148 tests

Regenerate the Studio presets with `python -m csp_engine.problems.puzzle_presets`.
