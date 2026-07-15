"""toolsnap CLI — fixture file management."""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

from .store import CallStore


# helpers
def _hr(width: int = 52) -> str:
    return "─" * width


def _load_silent(path: Path):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return CallStore(path).load()


def _load_index_silent(path: Path):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return CallStore(path).load_index()


# list
def _cmd_list(args: argparse.Namespace) -> int:
    directory = Path(args.directory)
    if not directory.is_dir():
        print(f"ERROR: not a directory: {directory}", file=sys.stderr)
        return 1
    files = sorted(directory.rglob("*.jsonl"))
    if not files:
        print("No .jsonl fixture files found.")
        return 0
    for f in files:
        records = _load_silent(f)
        fn_names = sorted({r.fn for r in records})
        fns_str = f"  [{', '.join(fn_names)}]" if fn_names else ""
        print(f"  {f}  ({len(records)} records, {len(fn_names)} functions){fns_str}")
    return 0


# show
def _cmd_show(args: argparse.Namespace) -> int:
    path = Path(args.fixture)
    if not path.exists():
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        return 1
    records = _load_silent(path)
    if not records:
        print(f"No records in {path}")
        return 0
    print(f"Fixture: {path}  ({len(records)} records)")
    print(_hr())
    for r in records:
        error_str = f"  ERROR={r.error['type']}" if r.error else ""
        print(f"  [{r.fn}] call {r.call_index}  {r.duration_ms:.1f}ms{error_str}")
        if r.args:
            print(f"    args   = {json.dumps(r.args)}")
        if r.kwargs:
            print(f"    kwargs = {json.dumps(r.kwargs)}")
        result_str = json.dumps(r.result)
        if len(result_str) > 200:
            result_str = result_str[:197] + "..."
        print(f"    result = {result_str}")
    return 0


# validate
_REQUIRED_FIELDS = {
    "call_index",
    "fn",
    "args",
    "kwargs",
    "result",
    "duration_ms",
    "ts",
    "error",
}


def _cmd_validate(args: argparse.Namespace) -> int:
    path = Path(args.fixture)
    if not path.exists():
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        return 1
    corrupt = 0
    total = 0
    with path.open(encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            stripped = line.strip()
            if not stripped:
                continue
            total += 1
            try:
                data = json.loads(stripped)
                missing = _REQUIRED_FIELDS - data.keys()
                if missing:
                    print(f"  line {lineno}: missing fields: {sorted(missing)}")
                    corrupt += 1
            except json.JSONDecodeError as exc:
                print(f"  line {lineno}: invalid JSON — {exc}")
                corrupt += 1
    if corrupt == 0:
        print(f"OK  {path}  ({total} records, 0 corrupt)")
        return 0
    print(f"INVALID  {path}  ({total} records, {corrupt} corrupt)")
    return 1


# diff
def _result_summary(result: object) -> str:
    if isinstance(result, list):
        return f"{len(result)} items"
    if isinstance(result, dict):
        return f"{len(result)} keys"
    if isinstance(result, str):
        return f"{len(result)} chars"
    return repr(result)[:40]


def _kwargs_diff_detail(r_a, r_b) -> str:
    changes = []
    all_keys = set(r_a.kwargs) | set(r_b.kwargs)
    for k in sorted(all_keys):
        v_a = r_a.kwargs.get(k, "<missing>")
        v_b = r_b.kwargs.get(k, "<missing>")
        if v_a != v_b:
            changes.append(f"{k}: {json.dumps(v_a)} → {json.dumps(v_b)}")
    if r_a.args != r_b.args:
        changes.append(f"args: {r_a.args!r} → {r_b.args!r}")
    return "  ".join(changes)


def _cmd_diff(args: argparse.Namespace) -> int:
    path_a, path_b = Path(args.fixture_a), Path(args.fixture_b)
    for p in (path_a, path_b):
        if not p.exists():
            print(f"ERROR: file not found: {p}", file=sys.stderr)
            return 1

    index_a = _load_index_silent(path_a)
    index_b = _load_index_silent(path_b)

    print(f"Diff: {path_a} → {path_b}")
    print(_hr())

    all_fns = list(index_a) + [f for f in index_b if f not in index_a]
    has_diff = False

    for fn in all_fns:
        calls_a = index_a.get(fn, [])
        calls_b = index_b.get(fn, [])

        if not calls_a:
            for r in calls_b:
                print(f"+ {fn:<14} call {r.call_index}  ADDED")
                has_diff = True
            continue

        if not calls_b:
            for r in calls_a:
                print(f"- {fn:<14} call {r.call_index}  REMOVED")
                has_diff = True
            continue

        # Function exists in both — compare call by call
        for i in range(max(len(calls_a), len(calls_b))):
            if i >= len(calls_a):
                print(f"+ {fn:<14} call {i}  ADDED")
                has_diff = True
            elif i >= len(calls_b):
                print(f"- {fn:<14} call {i}  REMOVED")
                has_diff = True
            else:
                r_a, r_b = calls_a[i], calls_b[i]
                args_changed = (r_a.args != r_b.args) or (r_a.kwargs != r_b.kwargs)
                result_changed = r_a.result != r_b.result
                if not args_changed and not result_changed:
                    continue  # identical — skip
                parts = []
                if args_changed:
                    detail = _kwargs_diff_detail(r_a, r_b)
                    parts.append(
                        f"args CHANGED  {detail}" if detail else "args CHANGED"
                    )
                else:
                    parts.append("args unchanged")
                if result_changed:
                    sa = _result_summary(r_a.result)
                    sb = _result_summary(r_b.result)
                    parts.append(f"result CHANGED ({sa} → {sb})")
                print(f"  {fn:<14} call {i}  {'   '.join(parts)}")
                has_diff = True

    if not has_diff:
        print("  (no differences)")
    return 0


# stats
def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    sv = sorted(values)
    k = (len(sv) - 1) * p / 100
    lo = int(k)
    hi = min(lo + 1, len(sv) - 1)
    return sv[lo] + (k - lo) * (sv[hi] - sv[lo])


def _parallelism_hint(index: dict) -> str | None:
    """Return the best parallelism hint, or None if no independent pairs exist."""
    fn_names = list(index)
    if len(fn_names) < 2:
        return None

    fn_results: dict[str, set[str]] = {}
    fn_inputs: dict[str, list[str]] = {}
    fn_total_ms: dict[str, float] = {}

    for fn, records in index.items():
        fn_total_ms[fn] = sum(r.duration_ms for r in records)
        result_strs: set[str] = set()
        input_strs: list[str] = []
        for r in records:
            try:
                result_strs.add(json.dumps(r.result))
            except Exception:
                result_strs.add(str(r.result))
            try:
                input_strs.append(json.dumps(r.kwargs) + json.dumps(r.args))
            except Exception:
                input_strs.append(str(r.kwargs) + str(r.args))
        fn_results[fn] = result_strs
        fn_inputs[fn] = input_strs

    best: tuple[str, str, float] | None = None
    for i, fn_a in enumerate(fn_names):
        for fn_b in fn_names[i + 1 :]:
            # Skip trivial primitives (len ≤ 4) which spuriously match everywhere
            a_feeds_b = any(
                res in inp
                for res in fn_results[fn_a]
                for inp in fn_inputs[fn_b]
                if len(res) > 4
            )
            b_feeds_a = any(
                res in inp
                for res in fn_results[fn_b]
                for inp in fn_inputs[fn_a]
                if len(res) > 4
            )
            if not a_feeds_b and not b_feeds_a:
                saving = min(fn_total_ms[fn_a], fn_total_ms[fn_b])
                if best is None or saving > best[2]:
                    best = (fn_a, fn_b, saving)

    if best is None:
        return None
    fn_a, fn_b, saving = best
    return f"{fn_a} + {fn_b} are independent (potential saving: ~{saving:,.0f} ms)"


def _cmd_stats(args: argparse.Namespace) -> int:
    path = Path(args.fixture)
    if not path.exists():
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        return 1
    records = _load_silent(path)
    if not records:
        print(f"No records in {path}")
        return 0

    index: dict = {}
    for r in records:
        index.setdefault(r.fn, []).append(r)

    col_w = max(len(fn) for fn in index) + 2
    header = f"  {'Function':<{col_w}}  {'Calls':>5}  {'Avg ms':>8}  {'p95 ms':>8}  {'Errors':>6}"
    hr = _hr(max(52, len(header)))

    print(f"Fixture: {path}  ({len(records)} records, {len(index)} functions)")
    print(hr)
    print(header)

    total_wall_ms = 0.0
    for fn, fn_records in index.items():
        durations = [r.duration_ms for r in fn_records]
        errors = sum(1 for r in fn_records if r.error)
        avg_ms = sum(durations) / len(durations)
        p95 = _percentile(durations, 95)
        total_wall_ms += sum(durations)
        print(
            f"  {fn:<{col_w}}  {len(fn_records):>5}  {avg_ms:>8.1f}  {p95:>8.1f}  {errors:>6}"
        )

    print(hr)
    print(f"  Total wall time (sequential): {total_wall_ms:,.0f} ms")

    hint = _parallelism_hint(index)
    if hint:
        print(f"  Parallelism opportunity: {hint}")

    return 0


# repair
def _cmd_repair(args: argparse.Namespace) -> int:
    path = Path(args.fixture)
    if not path.exists():
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        return 1
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        removed = CallStore(path).repair()
    if removed == 0:
        print(f"OK  {path}  (no corrupt records found)")
    else:
        print(f"Repaired  {path}  ({removed} corrupt record(s) removed)")
    return 0


# entry point
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="toolsnap",
        description="toolsnap — LLM agent fixture management",
    )
    sub = parser.add_subparsers(dest="command", metavar="command")

    p_list = sub.add_parser("list", help="list all .jsonl fixture files")
    p_list.add_argument(
        "directory", nargs="?", default=".", help="directory to scan (default: .)"
    )

    p_show = sub.add_parser("show", help="pretty-print all records in a fixture")
    p_show.add_argument("fixture")

    p_diff = sub.add_parser("diff", help="show what changed between two fixture runs")
    p_diff.add_argument("fixture_a")
    p_diff.add_argument("fixture_b")

    p_validate = sub.add_parser(
        "validate", help="check fixture is valid (parseable, no corrupt records)"
    )
    p_validate.add_argument("fixture")

    p_stats = sub.add_parser(
        "stats", help="call counts, avg duration, error rate per function"
    )
    p_stats.add_argument("fixture")

    p_repair = sub.add_parser("repair", help="rewrite fixture removing corrupt lines")
    p_repair.add_argument("fixture")

    parsed = parser.parse_args(argv)
    if not parsed.command:
        parser.print_help()
        return 0
    dispatch = {
        "list": _cmd_list,
        "show": _cmd_show,
        "diff": _cmd_diff,
        "validate": _cmd_validate,
        "stats": _cmd_stats,
        "repair": _cmd_repair,
    }
    return dispatch[parsed.command](parsed)


if __name__ == "__main__":
    sys.exit(main())
