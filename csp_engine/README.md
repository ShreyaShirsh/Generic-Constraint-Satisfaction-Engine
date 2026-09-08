# CSP Engine (BITE308L)

One general constraint-satisfaction engine, stdlib-only, that solves many
problems from a single untouched solver.

## Layout
- `core/`      — problem-agnostic engine (model, constraints, search, metrics)
- `problems/`  — adapters that only *describe* a problem as a `CSP`

`core/` never imports `problems/` or `viz/`, and uses the standard library only.

## Run (Phase 1)
From the directory that contains `csp_engine/`:

    python3 -m csp_engine.problems.graph_colouring

## Status
- [x] Phase 1 — model, binary constraints, naive backtracking, map colouring
- [ ] Phase 2 — forward checking, AC-3, MRV/degree/LCV, Sudoku
- [ ] Phase 3 — N-Queens, cryptarithmetic, min-conflicts (+ Zebra, timetable)
- [ ] Phase 4 — instrumentation study, charts, reduction demo, report
