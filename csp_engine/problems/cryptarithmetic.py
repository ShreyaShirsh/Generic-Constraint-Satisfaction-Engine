"""Adapter: cryptarithmetic (SEND + MORE = MONEY) -> CSP. Universal: any
number of addend words and any result word.

Built from the SAME primitives every other problem uses:
  variables   = one per distinct letter (its digit), plus one carry per column
  domains     = 0-9 for letters, 0..(number of addends - 1) for carries
  constraints = all_different(letters)                    -- distinct digits
                one Predicate per leading letter         -- "can't be 0"
                one Predicate per column:
                    sum of the column's digits + carry_in
                        == result digit + 10 * carry_out
                exactly how you'd add the numbers by hand.

Expressing addition as one constraint per column (instead of one giant
constraint over every letter) is what lets propagation prune a column as
soon as its letters start to be known.
"""
from __future__ import annotations
import random
from ..core.model import CSP
from ..core.constraints import all_different, Predicate

PLACE = ["units", "tens", "hundreds", "thousands", "ten-thousands", "hundred-thousands",
         "millions", "ten-millions"]


def crypt_csp(addends: list[str], result: str, givens: dict | None = None) -> CSP:
    addends = [w.upper() for w in addends]
    result = result.upper()
    if not addends or not all(w.isalpha() for w in addends + [result]):
        raise ValueError("words must be letters only")
    if len(result) < max(len(w) for w in addends):
        raise ValueError("the result must be at least as long as the longest addend")
    if len(result) > max(len(w) for w in addends) + len(str(len(addends) * 9)):
        raise ValueError("the result is too long to be a sum of these addends")
    letters = sorted(set("".join(addends) + result))
    if len(letters) > 10:
        raise ValueError("more than 10 different letters can't all get different digits")

    n_cols = len(result)
    carry_max = 0
    while (9 * len(addends) + carry_max) // 10 > carry_max:
        carry_max = (9 * len(addends) + carry_max) // 10
    carries = [f"carry{i + 1}" for i in range(n_cols)]          # carry OUT of column i
    variables = letters + carries
    domains = {L: list(range(10)) for L in letters}
    for c in carries:
        domains[c] = list(range(carry_max + 1))

    constraints = list(all_different(letters, label="the letters (all different digits)"))
    for L in sorted({w[0] for w in addends + [result] if len(w) > 1}):
        constraints.append(Predicate([L], lambda l: all(v != 0 for v in l.values()),
                                     name="NoLeadingZero", check_when_partial=True,
                                     label=f"the rule that {L} starts a word (so it can't be 0)"))

    def col(word: str, i: int):
        pos = len(word) - 1 - i
        return word[pos] if pos >= 0 else None

    for i in range(n_cols):
        digits = [col(w, i) for w in addends]
        digits = [d for d in digits if d]
        r = col(result, i)
        cin = carries[i - 1] if i > 0 else None
        cout = carries[i]
        scope = list(dict.fromkeys(digits + [r] + ([cin] if cin else []) + [cout]))

        def check(local, digits=digits, r=r, cin=cin, cout=cout):
            total = sum(local[d] for d in digits) + (local[cin] if cin else 0)
            return total == local[r] + 10 * local[cout]

        constraints.append(Predicate(scope, check, name="Column",
                                     label=f"the {PLACE[i] if i < len(PLACE) else f'column {i + 1}'} column"))
    for L, d in sorted((givens or {}).items()):
        constraints.append(Predicate([L], lambda l, d=d: all(v == d for v in l.values()),
                                     name="Given", check_when_partial=True,
                                     label=f"the clue {L} = {d}"))
    constraints.append(Predicate([carries[-1]], lambda l: all(v == 0 for v in l.values()),
                                 name="NoOverflow", check_when_partial=True,
                                 label="the rule that nothing carries past the first letter"))
    return CSP(variables, domains, constraints)


def cryptarithmetic_csp(addend1: str, addend2: str, result: str) -> CSP:
    return crypt_csp([addend1, addend2], result)


def crypt_name(var) -> str:
    if var.startswith("carry"):
        return f"the carry out of column {var[5:]}"
    return var


def solution_str(solution: dict, addend1: str, addend2: str, result: str) -> str:
    def word_value(word: str) -> int:
        return int("".join(str(solution[L]) for L in word.upper()))

    a, b, r = word_value(addend1), word_value(addend2), word_value(result)
    mapping = " ".join(f"{L}={solution[L]}" for L in sorted(set(addend1.upper() +
                                                                 addend2.upper() +
                                                                 result.upper())))
    return f"{a} + {b} = {r}   ({mapping})"


CLASSICS = [
    (["SEND", "MORE"], "MONEY"),
    (["BASE", "BALL"], "GAMES"),
    (["EAT", "THAT"], "APPLE"),
    (["CROSS", "ROADS"], "DANGER"),
    (["FORTY", "TEN", "TEN"], "SIXTY"),
    (["DONALD", "GERALD"], "ROBERT"),
    (["COCA", "COLA"], "OASIS"),
    (["TO", "GO"], "OUT"),
]

WORDS = """able acid aged also area army away baby back ball band bank base bath bear beat been beer bell
belt best bird blow blue boat body bomb bond bone book boot born boss both bowl bulk burn bush busy
cake call calm came camp card care cart case cash cast cell chat chip city clay club coal coat code
cold come cook cool cope copy core cost crew crop dark data date dawn days dead deal dean dear debt
deep deny desk dial diet disc disk does done door dose down draw drew drop drug dual duke dust duty
each earn ease east easy edge else even ever evil exit face fact fail fair fall farm fast fate fear
feed feel feet fell felt file fill film find fine fire firm fish five flat flow food foot ford form
fort four free from fuel full fund gain game gate gave gear gene gift girl give glad goal goes gold
golf gone good gray grew grow gulf hair half hall hand hang hard harm hate have head hear heat held
hell help here hero high hill hire hold hole holy home hope host hour huge hung hunt hurt idea inch
into iron item jack jane jean john join jump jury just keen keep kent kept kick kill kind king knee
knew know lack lady laid lake land lane last late lead left less life lift like line link list live
load loan lock logo long look lord lose loss lost love luck made mail main make male many mark mass
meal mean meat meet menu mere mile milk mill mind mine miss mode mood moon more most move much must
name navy near neck need news next nice nick nine none nose note okay once only onto open oral over
pace pack page paid pain pair palm park part pass past path peak pick pink pipe plan play plot plug
plus poll pool poor port post pull pure push race rail rain rank rare rate read real rear rely rent
rest rice rich ride ring rise risk road rock role roll roof room root rose rule rush safe said sake
sale salt same sand save seat seed seek seem seen self sell send sent ship shop shot show shut sick
side sign site size skin slip slow snow soft soil sold sole some song soon sort soul spot star stay
step stop such suit sure take tale talk tall tank tape task team tech tell tend term test text than
that them then they thin this thus till time tiny told tone took tool tour town tree trip true tune
turn twin type unit upon used user vast very vice view vote wage wait wake walk wall want ward warm
wash wave ways weak wear week well went were west what when whom wide wife wild will wind wine wing
wire wise wish with wood word wore work yard yeah year your zero zone ant bee cat cow dog eel elk emu
fox gnu hen owl pig rat yak art box cup ear egg eye fan hat ice ink jar key leg map net oil pen pot
rug sun toy van web""".split()


def _spells(word: str, digits: str, mapping: dict) -> bool:
    """Can `word` spell `digits`, extending the letter->digit mapping
    consistently (distinct letters, distinct digits)?"""
    if len(word) != len(digits) or digits[0] == "0":
        return False
    m = dict(mapping)
    used = {d: L for L, d in m.items()}
    for L, d in zip(word, digits):
        d = int(d)
        if L in m:
            if m[L] != d:
                return False
        elif d in used:
            return False
        else:
            m[L] = d
            used[d] = L
    return True


def generate_crypt(seed: int | None = None, time_budget: float = 5.0) -> dict | None:
    """Invent a word sum: guess digits for two random words, look for a real
    word that spells their total, then -- exactly like a Sudoku generator --
    reveal letters until the engine proves the answer is unique and drop any
    reveal that turns out to be unnecessary."""
    import time
    from ..core.generator import count_solutions
    rng = random.Random(seed)
    words = [w.upper() for w in WORDS]
    by_len: dict[int, list[str]] = {}
    for w in words:
        by_len.setdefault(len(w), []).append(w)
    deadline = time.perf_counter() + time_budget
    while time.perf_counter() < deadline:
        a, b = rng.sample(words, 2)
        letters = sorted(set(a + b))
        if len(letters) > 9:
            continue
        for _ in range(200):
            digits = rng.sample(range(10), len(letters))
            mapping = dict(zip(letters, digits))
            if mapping[a[0]] == 0 or mapping[b[0]] == 0:
                continue
            total = str(int("".join(str(mapping[L]) for L in a)) +
                        int("".join(str(mapping[L]) for L in b)))
            match = next((r for r in by_len.get(len(total), [])
                          if r not in (a, b) and _spells(r, total, mapping)), None)
            if match is None:
                continue
            full = dict(mapping)
            for L, d in zip(match, total):
                full[L] = int(d)
            order = sorted(full)
            rng.shuffle(order)
            givens: dict = {}
            for L in [None] + order:
                if L is not None:
                    givens[L] = full[L]
                if count_solutions(crypt_csp([a, b], match, givens), limit=2, budget=20_000) == 1:
                    break
            for L in list(givens):
                trial = {k: v for k, v in givens.items() if k != L}
                if count_solutions(crypt_csp([a, b], match, trial), limit=2, budget=20_000) == 1:
                    givens = trial
            return {"addends": [a, b], "result": match, "givens": givens}
    return None


if __name__ == "__main__":      # self-test (the canonical puzzle, known-solvable)
    from ..core.backtracking import backtracking_search
    from ..core.inference import mac
    from ..core.heuristics import mrv

    csp = cryptarithmetic_csp("SEND", "MORE", "MONEY")
    solution, metrics = backtracking_search(csp, select_var=mrv, inference=mac)
    assert solution is not None
    assert csp.is_solution(solution)
    print("cryptarithmetic self-test passed.")
    print(solution_str(solution, "SEND", "MORE", "MONEY"))
    print(metrics.summary())
