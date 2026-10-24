# A Generic Constraint Satisfaction Engine (BITE308L)

One general-purpose constraint-satisfaction solver that solves six
structurally different problems — N-Queens, map/graph colouring, Sudoku,
cryptarithmetic, the Zebra logic puzzle, and exam timetabling — from a
single, untouched codebase. No problem is hardcoded into the solver; every
pattern is described as data and handed to the same engine.

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

## Layout

```
core/            problem-agnostic engine -- the only file that may NOT import from problems/, cli, or web/
  model.py         CSP container: variables, domains, constraints, neighbours
  constraints.py   BinaryRelation, Predicate, NotEqual, all_different
  backtracking.py  systematic search: first-solution / all-solutions, pluggable hooks, max_nodes safety cap
  inference.py     forward checking, generic AC-3, MAC (maintaining arc consistency)
  heuristics.py    MRV, MRV+degree, LCV
  local_search.py  min-conflicts (a second, contrasting search paradigm)
  metrics.py       SearchMetrics -- nodes / backtracks / pruned / time, mandatory instrumentation

problems/        adapters: each file only *describes* a problem as a CSP -- zero solving logic
  nqueens.py           any board size n
  graph_colouring.py   any graph, any palette (Australia map is one named preset)
  sudoku.py            any N^2 x N^2 grid
  cryptarithmetic.py   any two addends + result (SEND+MORE=MONEY is one preset)
  zebra.py             the classic 5-house Einstein puzzle, built from relational BinaryRelations
  exam_scheduling.py   reduces timetabling to graph_colouring_csp -- no new solver code

web/             Flask demo for the faculty review (optional -- core/ never depends on it)
  app.py            REST endpoints, one per problem + /api/solve/custom + /api/benchmark
  custom_csp.py     builds a CSP from a user-typed JSON spec using the SAME two primitives above
  templates/, static/   single-page UI: one tab per problem, a Custom CSP playground, a benchmark chart

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
  values after each assignment) and a generic `ac3` / `mac` (maintaining
  arc consistency — AC-3 restricted to the arcs touched by the latest
  assignment).
- **Ordering heuristics**: `mrv` (Minimum Remaining Values), `mrv_degree`
  (MRV, ties broken by the degree heuristic), `lcv` (Least Constraining
  Value).
- **Local search**: `min_conflicts` — starts from a complete, usually
  inconsistent assignment and repeatedly repairs the most-conflicted
  variable; a genuinely different paradigm from backtracking, included for
  contrast and dramatically faster on large N-Queens instances.
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
/ MAC+MRV+degree+LCV), then supply your own input — nothing is hardcoded.

**Web demo** (needs `flask` + `flask-cors`, see `requirements.txt`):
```
pip install -r requirements.txt
python -m csp_engine.web.app
```
Open http://127.0.0.1:5000 — one tab per problem, live visualisations
(chessboard, graph, Sudoku grid, equation, house table, timetable), a
Custom CSP playground, and a benchmark tab with a live chart.

**Instrumentation study** (the "quantify each technique" deliverable):
```
python -m csp_engine.benchmark
```
Runs naive backtracking through full MAC+MRV+degree+LCV on five problems,
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

`tests/` has 61 pytest cases covering `core/` in isolation (hand-built tiny
CSPs, independent of any problem adapter), every problem adapter against a
known fact about the puzzle, the Custom CSP spec builder's validation, and
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
- [x] Automated pytest suite — 61 tests across core, problems, custom CSP builder, and the web API
