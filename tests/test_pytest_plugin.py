from __future__ import annotations

import json
import sys
import types
import warnings

from toolsnap.models import CallRecord
from toolsnap.store import CallStore


# helpers
def _base_record(fn="tool", call_index=0, kwargs=None, result=None, duration_ms=10.0):
    return {
        "call_index": call_index,
        "fn": fn,
        "args": [],
        "kwargs": kwargs or {},
        "result": result if result is not None else [],
        "duration_ms": duration_ms,
        "ts": 1720789200.0,
        "error": None,
    }


def _write_fixture(path, *records):
    path = path if hasattr(path, "write_text") else type(path)(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(r) for r in records) + "\n",
        encoding="utf-8",
    )


_CONFTEST = 'pytest_plugins = ["toolsnap.pytest_plugin"]'


# unit: _find_fn_in_modules
def test_find_fn_returns_unique_callable():
    from toolsnap.pytest_plugin import _find_fn_in_modules

    fn_name = "_ts_unique_fn_plugin_abc123"

    def the_fn():
        pass

    the_fn.__name__ = fn_name
    mod = types.ModuleType("_ts_plugin_mod_unique_a")
    setattr(mod, fn_name, the_fn)
    sys.modules["_ts_plugin_mod_unique_a"] = mod

    try:
        assert _find_fn_in_modules(fn_name) is the_fn
    finally:
        del sys.modules["_ts_plugin_mod_unique_a"]


def test_find_fn_deduplicates_same_object_across_modules():
    """A function imported in multiple modules should still count as one candidate."""
    from toolsnap.pytest_plugin import _find_fn_in_modules

    fn_name = "_ts_dedup_fn_plugin_abc123"

    def the_fn():
        pass

    the_fn.__name__ = fn_name

    mod_a = types.ModuleType("_ts_dedup_mod_a")
    mod_b = types.ModuleType("_ts_dedup_mod_b")
    setattr(mod_a, fn_name, the_fn)
    setattr(mod_b, fn_name, the_fn)  # same object in two modules
    sys.modules["_ts_dedup_mod_a"] = mod_a
    sys.modules["_ts_dedup_mod_b"] = mod_b

    try:
        assert _find_fn_in_modules(fn_name) is the_fn  # not ambiguous
    finally:
        del sys.modules["_ts_dedup_mod_a"]
        del sys.modules["_ts_dedup_mod_b"]


def test_find_fn_returns_none_for_missing():
    from toolsnap.pytest_plugin import _find_fn_in_modules

    assert _find_fn_in_modules("__zz_nonexistent_toolsnap_fn_xyz_abc__") is None


# unit: _check_stale_fixtures
def _register_fn(name, fn, mod_name):
    """Add a uniquely-named function to sys.modules under *mod_name*."""
    fn.__name__ = name
    mod = types.ModuleType(mod_name)
    setattr(mod, name, fn)
    sys.modules[mod_name] = mod
    return mod_name


def test_stale_fixture_warns_on_unknown_kwarg(tmp_path):
    from toolsnap.pytest_plugin import _check_stale_fixtures

    fn_name = "_ts_stale_fn_zxqabc"
    (tmp_path / "fixtures").mkdir()
    CallStore(tmp_path / "fixtures" / "stale.jsonl").append(
        CallRecord(
            call_index=0,
            fn=fn_name,
            args=[],
            kwargs={"old_param": "value"},
            result=None,
            duration_ms=0.0,
            ts=0.0,
            error=None,
        )
    )

    def fn(new_param: str):
        pass

    mod_name = _register_fn(fn_name, fn, "_ts_stale_mod_zxqabc")
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            _check_stale_fixtures(tmp_path)
    finally:
        del sys.modules[mod_name]

    stale_warnings = [w for w in caught if "stale" in str(w.message).lower()]
    assert stale_warnings, "expected a staleness warning"
    assert any("old_param" in str(w.message) for w in stale_warnings)


def test_no_stale_warning_when_params_match(tmp_path):
    from toolsnap.pytest_plugin import _check_stale_fixtures

    fn_name = "_ts_fresh_fn_zxqabc"
    (tmp_path / "fixtures").mkdir()
    CallStore(tmp_path / "fixtures" / "fresh.jsonl").append(
        CallRecord(
            call_index=0,
            fn=fn_name,
            args=[],
            kwargs={"param": "value"},
            result=None,
            duration_ms=0.0,
            ts=0.0,
            error=None,
        )
    )

    def fn(param: str):
        pass

    mod_name = _register_fn(fn_name, fn, "_ts_fresh_mod_zxqabc")
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            _check_stale_fixtures(tmp_path)
    finally:
        del sys.modules[mod_name]

    assert not any("stale" in str(w.message).lower() for w in caught)


def test_no_stale_warning_for_var_kwargs_function(tmp_path):
    from toolsnap.pytest_plugin import _check_stale_fixtures

    fn_name = "_ts_varkw_fn_zxqabc"
    (tmp_path / "fixtures").mkdir()
    CallStore(tmp_path / "fixtures" / "varkw.jsonl").append(
        CallRecord(
            call_index=0,
            fn=fn_name,
            args=[],
            kwargs={"anything": "value"},
            result=None,
            duration_ms=0.0,
            ts=0.0,
            error=None,
        )
    )

    def fn(**kwargs):
        pass

    mod_name = _register_fn(fn_name, fn, "_ts_varkw_mod_zxqabc")
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            _check_stale_fixtures(tmp_path)
    finally:
        del sys.modules[mod_name]

    assert not any("stale" in str(w.message).lower() for w in caught)


# integration: 5 agent tests via pytester
def test_plugin_replay_mode_passes(pytester):
    """Agent test 1: toolsnap_session in replay mode returns recorded results."""
    _write_fixture(
        pytester.path / "fixtures" / "search.jsonl",
        _base_record("search", 0, kwargs={"q": "llm"}, result=["doc1", "doc2"]),
        _base_record("search", 1, kwargs={"q": "agents"}, result=["doc3"]),
    )
    pytester.makeconftest(_CONFTEST)
    pytester.makepyfile("""
        import pytest

        def search(q):
            raise RuntimeError("real search must not run in replay mode")

        @pytest.mark.toolsnap_fixture("fixtures/search.jsonl")
        def test_agent_search(toolsnap_session):
            toolsnap_session.wrap(search)
            r1 = search(q="llm")
            r2 = search(q="agents")
            assert r1 == ["doc1", "doc2"]
            assert r2 == ["doc3"]
    """)

    pytester.runpytest("-v").assert_outcomes(passed=1)


def test_plugin_record_mode_writes_fixture(pytester):
    """Agent test 2: --toolsnap-record writes a fresh fixture file."""
    pytester.makeconftest(_CONFTEST)
    pytester.makepyfile("""
        import pytest

        def get_weather(city):
            return {"temp": 22, "city": city}

        @pytest.mark.toolsnap_fixture("fixtures/get_weather.jsonl")
        def test_weather_agent(toolsnap_session):
            toolsnap_session.wrap(get_weather)
            result = get_weather(city="london")
            assert result == {"temp": 22, "city": "london"}
    """)

    pytester.runpytest("--toolsnap-record", "-v").assert_outcomes(passed=1)

    fixture_path = pytester.path / "fixtures" / "get_weather.jsonl"
    assert fixture_path.exists(), "fixture file was not created"
    record = json.loads(fixture_path.read_text(encoding="utf-8").splitlines()[0])
    assert record["fn"] == "get_weather"
    assert record["kwargs"] == {"city": "london"}
    assert record["result"] == {"temp": 22, "city": "london"}


def test_plugin_strict_mode_raises_on_extra_call(pytester):
    """Agent test 3: extra call beyond fixture raises UnexpectedToolCall (strict=True)."""
    _write_fixture(
        pytester.path / "fixtures" / "summarize.jsonl",
        _base_record("summarize", 0, kwargs={"text": "hello"}, result="summary"),
    )
    pytester.makeconftest(_CONFTEST)
    pytester.makepyfile("""
        import pytest

        def summarize(text):
            return "real-summary"

        @pytest.mark.toolsnap_fixture("fixtures/summarize.jsonl")
        def test_extra_call_raises(toolsnap_session):
            toolsnap_session.wrap(summarize)
            summarize(text="hello")   # call 0 — replayed from fixture
            summarize(text="world")  # call 1 — no fixture record, strict raises
    """)

    result = pytester.runpytest("-v")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*UnexpectedToolCall*"])


def test_plugin_non_strict_falls_through(pytester):
    """Agent test 4: --toolsnap-strict=false lets extra calls fall through."""
    _write_fixture(
        pytester.path / "fixtures" / "lookup.jsonl",
        _base_record("lookup", 0, kwargs={"key": "a"}, result="recorded-value"),
    )
    pytester.makeconftest(_CONFTEST)
    pytester.makepyfile("""
        import pytest

        def lookup(key):
            return "real-value"

        @pytest.mark.toolsnap_fixture("fixtures/lookup.jsonl")
        def test_non_strict_falls_through(toolsnap_session):
            toolsnap_session.wrap(lookup)
            r1 = lookup(key="a")  # replayed
            r2 = lookup(key="b")  # extra call falls through
            assert r1 == "recorded-value"
            assert r2 == "real-value"
    """)

    pytester.runpytest("--toolsnap-strict=false", "-v").assert_outcomes(passed=1)


def test_plugin_assert_helpers_in_replay(pytester):
    """Agent test 5: assert_called / assert_called_with / assert_no_errors work in replay."""
    _write_fixture(
        pytester.path / "fixtures" / "session.jsonl",
        _base_record("search", 0, kwargs={"q": "llm"}, result=["doc1"]),
        _base_record("search", 1, kwargs={"q": "agents"}, result=["doc2"]),
        _base_record("get_weather", 0, kwargs={"city": "paris"}, result={"temp": 18}),
    )
    pytester.makeconftest(_CONFTEST)
    pytester.makepyfile("""
        import pytest

        def search(q):
            raise RuntimeError("no real calls")

        def get_weather(city):
            raise RuntimeError("no real calls")

        @pytest.mark.toolsnap_fixture("fixtures/session.jsonl")
        def test_multi_tool_agent(toolsnap_session):
            toolsnap_session.wrap(search)
            toolsnap_session.wrap(get_weather)

            r1 = search(q="llm")
            r2 = search(q="agents")
            r3 = get_weather(city="paris")

            assert r1 == ["doc1"]
            assert r2 == ["doc2"]
            assert r3 == {"temp": 18}

            toolsnap_session.assert_called("search", times=2)
            toolsnap_session.assert_called("get_weather", times=1)
            toolsnap_session.assert_called_with("search", q="llm")
            toolsnap_session.assert_no_errors()
    """)

    pytester.runpytest("-v").assert_outcomes(passed=1)
