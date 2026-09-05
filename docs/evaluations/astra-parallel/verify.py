"""Reproduce the independent acceptance gate for the recorded worker outputs."""
import importlib.util
import itertools
import json
from pathlib import Path


def cases():
    for value in (None, 0, 1.5, True, [], {}, b"1h"):
        yield value, TypeError
    for value in ("", " ", "1", "h", "-1s", "+1s", "1.0s", "1H", "1d",
                  "1 h", "1m1h", "1s1m", "1h1h", "1h0h", "0s0s", "1s!",
                  "1s\n", "\t1s", "1h\t1m", "１s", "١s", "1\u00a0s",
                  "1h\n1m", "1e3s", "1s 2", "86401s", "24h1s", "1441m",
                  "999999999999999999999h"):
        yield value, ValueError
    for value, expected in (("0s", 0), ("24h", 86400), ("1440m", 86400),
                            ("86400s", 86400), (" 01h02m03s ", 3723),
                            ("0" * 5000 + "s", 0),
                            ("0" * 5000 + "86400s", 86400)):
        yield value, expected
    for h, m, s, gap in itertools.product((0, 1, 23, 24, 25), (0, 1, 59, 60), (0, 1, 59, 60), ("", " ", "   ")):
        total = h * 3600 + m * 60 + s
        yield f" {h}h{gap}{m}m{gap}{s}s ", total if total <= 86400 else ValueError
    # Every non-descending unit sequence must fail, even for zero values.
    for size in (2, 3):
        for units in itertools.product("hms", repeat=size):
            ranks = ["hms".index(unit) for unit in units]
            if any(a >= b for a, b in zip(ranks, ranks[1:])):
                yield "".join("0" + unit for unit in units), ValueError


def verify(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    failures, count = [], 0
    for value, expected in cases():
        count += 1
        try:
            actual = module.parse_duration(value)
        except Exception as error:
            actual = type(error)
        if actual != expected or (isinstance(expected, int) and type(actual) is not int):
            failures.append({"input": repr(value)[:80], "expected": str(expected), "actual": str(actual)})
    return {"cases": count, "passed": count - len(failures), "failures": failures}


if __name__ == "__main__":
    results = {name: verify(Path(__file__).with_name(name + ".py")) for name in ("low", "medium")}
    print(json.dumps(results, indent=2))
    raise SystemExit(any(result["failures"] for result in results.values()))
