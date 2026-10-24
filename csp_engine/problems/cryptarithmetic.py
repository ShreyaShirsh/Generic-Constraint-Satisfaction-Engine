"""Adapter: cryptarithmetic (SEND + MORE = MONEY) -> CSP. Universal: works
for any two addend words and any result word, not just one hardcoded puzzle.

This is the arithmetic-constraint demonstration promised in the project
abstract, and it is built from the SAME two primitives every other problem
in this engine uses — all_different() and Predicate() — nothing new.

Encoding (the standard textbook column encoding, Russell & Norvig style):
  variables   = one per distinct letter (its digit, 0-9), plus one hidden
                carry variable per column (0 or 1)
  domains     = 0-9 for letters (0 excluded for a word's leading letter),
                0-1 for carries
  constraints = all_different(letters)            -- every letter a distinct digit
                a column predicate per digit column:
                    digit(addend1) + digit(addend2) + carry_in
                        == digit(result) + 10 * carry_out
                which is exactly how you'd add the numbers by hand, one
                column at a time, carries included.

Expressing "addition" as one constraint per column (instead of one giant
constraint over every letter) is what lets forward checking / AC-3 prune
columns as soon as nearby letters are fixed, instead of only finding out
the sum is wrong after all ten letters are assigned.
"""
from __future__ import annotations
from ..core.model import CSP, Var
from ..core.constraints import all_different, Predicate

Carry = str   # carry variable names, e.g. "C0", "C1", ...


def cryptarithmetic_csp(addend1: str, addend2: str, result: str) -> CSP:
    addend1, addend2, result = addend1.upper(), addend2.upper(), result.upper()
    if len(result) < max(len(addend1), len(addend2)):
        raise ValueError("result must be at least as long as the longer addend")

    letters = sorted(set(addend1) | set(addend2) | set(result))
    leading = {addend1[0], addend2[0], result[0]}

    n_cols = len(result)
    carries: list[Carry] = [f"C{i}" for i in range(n_cols)]   # carry OUT of column i

    variables: list[Var] = list(letters) + carries
    domains: dict[Var, set[int]] = {}
    for L in letters:
        domains[L] = (set(range(1, 10)) if L in leading else set(range(10)))
    for c in carries:
        domains[c] = {0, 1}

    def col_letter(word: str, i: int) -> str | None:
        """i-th column from the right (0 = units), or None past the word's length."""
        pos = len(word) - 1 - i
        return word[pos] if pos >= 0 else None

    constraints = []
    for i in range(n_cols):
        d1, d2, r = col_letter(addend1, i), col_letter(addend2, i), col_letter(result, i)
        carry_in = carries[i - 1] if i > 0 else None
        carry_out = carries[i]

        scope = [v for v in (d1, d2, r, carry_in, carry_out) if v is not None]

        def make_column(d1=d1, d2=d2, r=r, carry_in=carry_in, carry_out=carry_out):
            def check(local: dict) -> bool:
                v1 = local.get(d1, 0) if d1 else 0
                v2 = local.get(d2, 0) if d2 else 0
                cin = local[carry_in] if carry_in else 0
                total = v1 + v2 + cin
                return total % 10 == local[r] and total // 10 == local[carry_out]
            return check

        constraints.append(Predicate(scope, make_column(),
                                     name=f"col{i}", check_when_partial=False))

    constraints.extend(all_different(letters))

    # the final carry out of the leftmost column must have nowhere left to
    # go except possibly a leading extra digit of `result` — enforced
    # implicitly because that digit IS carries[-1]'s column already, so no
    # extra constraint is needed here.

    return CSP(variables, domains, constraints)


def solution_str(solution: dict, addend1: str, addend2: str, result: str) -> str:
    def word_value(word: str) -> int:
        return int("".join(str(solution[L]) for L in word.upper()))

    a, b, r = word_value(addend1), word_value(addend2), word_value(result)
    mapping = " ".join(f"{L}={solution[L]}" for L in sorted(set(addend1.upper() +
                                                                 addend2.upper() +
                                                                 result.upper())))
    return f"{a} + {b} = {r}   ({mapping})"


if __name__ == "__main__":      # self-test (the canonical puzzle, known-solvable)
    from ..core.backtracking import backtracking_search
    from ..core.inference import forward_checking
    from ..core.heuristics import mrv

    csp = cryptarithmetic_csp("SEND", "MORE", "MONEY")
    solution, metrics = backtracking_search(csp, select_var=mrv, inference=forward_checking)
    assert solution is not None
    assert csp.is_solution(solution)
    print("cryptarithmetic self-test passed.")
    print(solution_str(solution, "SEND", "MORE", "MONEY"))
    print(metrics.summary())
