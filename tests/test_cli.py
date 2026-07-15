import json


from toolsnap.cli import main
from toolsnap.models import CallRecord
from toolsnap.store import CallStore


# helpers
def _rec(
    fn="search", call_index=0, kwargs=None, result=None, duration_ms=100.0, error=None
):
    return CallRecord(
        call_index=call_index,
        fn=fn,
        args=[],
        kwargs=kwargs or {},
        result=result if result is not None else [],
        duration_ms=duration_ms,
        ts=1720789200.0,
        error=error,
    )


def _write(path, *records):
    store = CallStore(path)
    for r in records:
        store.append(r)


# list
def test_list_finds_jsonl_files(tmp_path, capsys):
    sub = tmp_path / "fixtures"
    sub.mkdir()
    _write(sub / "alpha.jsonl", _rec("alpha"))
    _write(sub / "beta.jsonl", _rec("beta"), _rec("beta", call_index=1))

    rc = main(["list", str(tmp_path)])

    assert rc == 0
    out = capsys.readouterr().out
    assert "alpha.jsonl" in out
    assert "beta.jsonl" in out
    assert "2 records" in out


def test_list_no_files(tmp_path, capsys):
    rc = main(["list", str(tmp_path)])

    assert rc == 0
    assert "No .jsonl" in capsys.readouterr().out


def test_list_invalid_directory(tmp_path, capsys):
    rc = main(["list", str(tmp_path / "nonexistent")])

    assert rc == 1
    assert "ERROR" in capsys.readouterr().err


# show
def test_show_prints_records(tmp_path, capsys):
    f = tmp_path / "f.jsonl"
    _write(f, _rec("search", kwargs={"query": "llm"}, result=["doc1", "doc2"]))

    rc = main(["show", str(f)])

    assert rc == 0
    out = capsys.readouterr().out
    assert "search" in out
    assert "call 0" in out
    assert "doc1" in out


def test_show_error_record(tmp_path, capsys):
    f = tmp_path / "f.jsonl"
    _write(f, _rec("boom", error={"type": "ValueError", "message": "bad"}))

    rc = main(["show", str(f)])

    assert rc == 0
    assert "ERROR=ValueError" in capsys.readouterr().out


def test_show_missing_file(tmp_path, capsys):
    rc = main(["show", str(tmp_path / "missing.jsonl")])

    assert rc == 1
    assert "ERROR" in capsys.readouterr().err


def test_show_truncates_long_result(tmp_path, capsys):
    f = tmp_path / "f.jsonl"
    _write(f, _rec("fn", result="x" * 500))

    main(["show", str(f)])

    out = capsys.readouterr().out
    # Result line must be capped (≤ ~220 chars for the result= line)
    result_line = next(line for line in out.splitlines() if "result =" in line)
    assert len(result_line) <= 220
    assert "..." in result_line


# validate
def test_validate_clean_fixture(tmp_path, capsys):
    f = tmp_path / "f.jsonl"
    _write(f, _rec("fn", result=42))

    rc = main(["validate", str(f)])

    assert rc == 0
    assert "OK" in capsys.readouterr().out


def test_validate_corrupt_fixture(tmp_path, capsys):
    f = tmp_path / "f.jsonl"
    f.write_text("not json\n", encoding="utf-8")

    rc = main(["validate", str(f)])

    assert rc == 1
    out = capsys.readouterr().out
    assert "INVALID" in out
    assert "line 1" in out


def test_validate_missing_fields(tmp_path, capsys):
    f = tmp_path / "f.jsonl"
    f.write_text('{"call_index": 0, "fn": "x"}\n', encoding="utf-8")

    rc = main(["validate", str(f)])

    assert rc == 1
    assert "missing fields" in capsys.readouterr().out


def test_validate_missing_file(tmp_path, capsys):
    rc = main(["validate", str(tmp_path / "missing.jsonl")])

    assert rc == 1
    assert "ERROR" in capsys.readouterr().err


# diff
def test_diff_no_changes(tmp_path, capsys):
    a = tmp_path / "a.jsonl"
    b = tmp_path / "b.jsonl"
    rec = _rec("search", kwargs={"query": "x"}, result=["doc1"])
    _write(a, rec)
    _write(b, rec)

    rc = main(["diff", str(a), str(b)])

    assert rc == 0
    assert "no differences" in capsys.readouterr().out


def test_diff_result_changed(tmp_path, capsys):
    a = tmp_path / "a.jsonl"
    b = tmp_path / "b.jsonl"
    _write(a, _rec("search", result=["doc1", "doc2", "doc3"]))
    _write(b, _rec("search", result=["doc1", "doc2"]))

    rc = main(["diff", str(a), str(b)])

    assert rc == 0
    out = capsys.readouterr().out
    assert "result CHANGED" in out
    assert "3 items" in out
    assert "2 items" in out


def test_diff_args_changed(tmp_path, capsys):
    a = tmp_path / "a.jsonl"
    b = tmp_path / "b.jsonl"
    _write(a, _rec("get_weather", kwargs={"city": "london"}))
    _write(b, _rec("get_weather", kwargs={"city": "paris"}))

    rc = main(["diff", str(a), str(b)])

    assert rc == 0
    out = capsys.readouterr().out
    assert "args CHANGED" in out
    assert "london" in out
    assert "paris" in out


def test_diff_call_removed(tmp_path, capsys):
    a = tmp_path / "a.jsonl"
    b = tmp_path / "b.jsonl"
    _write(a, _rec("search", call_index=0), _rec("search", call_index=1))
    _write(b, _rec("search", call_index=0))

    rc = main(["diff", str(a), str(b)])

    assert rc == 0
    out = capsys.readouterr().out
    assert "REMOVED" in out
    assert "call 1" in out


def test_diff_function_added(tmp_path, capsys):
    a = tmp_path / "a.jsonl"
    b = tmp_path / "b.jsonl"
    _write(a, _rec("search"))
    _write(b, _rec("search"), _rec("summarize"))

    rc = main(["diff", str(a), str(b)])

    assert rc == 0
    out = capsys.readouterr().out
    assert "ADDED" in out
    assert "summarize" in out


def test_diff_function_removed(tmp_path, capsys):
    a = tmp_path / "a.jsonl"
    b = tmp_path / "b.jsonl"
    _write(a, _rec("search"), _rec("summarize"))
    _write(b, _rec("search"))

    rc = main(["diff", str(a), str(b)])

    assert rc == 0
    out = capsys.readouterr().out
    assert "REMOVED" in out
    assert "summarize" in out


def test_diff_missing_file(tmp_path, capsys):
    a = tmp_path / "a.jsonl"
    _write(a, _rec("fn"))

    rc = main(["diff", str(a), str(tmp_path / "missing.jsonl")])

    assert rc == 1
    assert "ERROR" in capsys.readouterr().err


# stats
def test_stats_table_output(tmp_path, capsys):
    f = tmp_path / "f.jsonl"
    _write(
        f,
        _rec("search", call_index=0, duration_ms=200.0),
        _rec("search", call_index=1, duration_ms=300.0),
        _rec("get_weather", call_index=0, duration_ms=100.0),
        _rec(
            "get_weather",
            call_index=1,
            error={"type": "TimeoutError", "message": "t/o"},
            duration_ms=50.0,
        ),
    )

    rc = main(["stats", str(f)])

    assert rc == 0
    out = capsys.readouterr().out
    assert "search" in out
    assert "get_weather" in out
    assert "250.0" in out  # avg for search: (200+300)/2
    assert "Errors" in out
    assert "Total wall time" in out


def test_stats_error_count(tmp_path, capsys):
    f = tmp_path / "f.jsonl"
    _write(
        f,
        _rec("fn", call_index=0, duration_ms=100.0),
        _rec(
            "fn",
            call_index=1,
            duration_ms=200.0,
            error={"type": "ValueError", "message": "bad"},
        ),
    )

    main(["stats", str(f)])

    out = capsys.readouterr().out
    # 1 error should appear in the Errors column
    assert "1" in out


def test_stats_parallelism_hint(tmp_path, capsys):
    f = tmp_path / "f.jsonl"
    # search and get_weather have independent results (no data flowing between them)
    _write(
        f,
        _rec("search", call_index=0, result=["doc1"], duration_ms=300.0),
        _rec("get_weather", call_index=0, result={"temp": 20}, duration_ms=100.0),
    )

    main(["stats", str(f)])

    out = capsys.readouterr().out
    assert "Parallelism opportunity" in out
    assert "search" in out
    assert "get_weather" in out


def test_stats_missing_file(tmp_path, capsys):
    rc = main(["stats", str(tmp_path / "missing.jsonl")])

    assert rc == 1
    assert "ERROR" in capsys.readouterr().err


def test_stats_p95_single_record(tmp_path, capsys):
    f = tmp_path / "f.jsonl"
    _write(f, _rec("fn", duration_ms=123.4))

    rc = main(["stats", str(f)])

    assert rc == 0
    assert "123.4" in capsys.readouterr().out


# repair
def test_repair_removes_corrupt_lines(tmp_path, capsys):
    f = tmp_path / "f.jsonl"
    good = json.dumps(
        {
            "call_index": 0,
            "fn": "fn",
            "args": [],
            "kwargs": {},
            "result": 1,
            "duration_ms": 1.0,
            "ts": 1.0,
            "error": None,
        }
    )
    f.write_text(good + "\nNOT VALID JSON\n", encoding="utf-8")

    rc = main(["repair", str(f)])

    assert rc == 0
    out = capsys.readouterr().out
    assert "Repaired" in out
    assert "1 corrupt" in out
    # File should now be clean
    assert main(["validate", str(f)]) == 0


def test_repair_clean_fixture(tmp_path, capsys):
    f = tmp_path / "f.jsonl"
    _write(f, _rec("fn"))

    rc = main(["repair", str(f)])

    assert rc == 0
    assert "no corrupt" in capsys.readouterr().out


def test_repair_missing_file(tmp_path, capsys):
    rc = main(["repair", str(tmp_path / "missing.jsonl")])

    assert rc == 1
    assert "ERROR" in capsys.readouterr().err
