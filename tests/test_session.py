import warnings

import pytest

from toolsnap import (
    SnapSession,
    UnexpectedToolCall,
    any_of,
    contains,
    gt,
    lt,
    matches,
    snap,
)


def test_session_snap_and_assert_called(tmp_path):
    fixture = str(tmp_path / "s.jsonl")

    def search(query):
        return ["result"]

    with SnapSession.snap(fixture) as s:
        search = s.wrap(search)
        search("navassist")
        search("fall detection")

    s.assert_called("search")
    s.assert_called("search", times=2)


def test_session_assert_not_called(tmp_path):
    fixture = str(tmp_path / "s.jsonl")

    def search(query):
        return []

    with SnapSession.snap(fixture) as s:
        s.wrap(search)
        # never call search

    s.assert_not_called("search")


def test_session_assert_called_with_exact(tmp_path):
    fixture = str(tmp_path / "s.jsonl")

    def search(query):
        return []

    with SnapSession.snap(fixture) as s:
        search = s.wrap(search)
        search(query="navassist")

    s.assert_called_with("search", query="navassist")


def test_session_assert_called_with_predicate(tmp_path):
    fixture = str(tmp_path / "s.jsonl")

    def search(query):
        return []

    with SnapSession.snap(fixture) as s:
        search = s.wrap(search)
        search(query="find navassist docs")

    s.assert_called_with("search", query=contains("navassist"))
    s.assert_called_with("search", query=matches(r"^find"))


def test_session_assert_called_with_failure_message(tmp_path):
    fixture = str(tmp_path / "s.jsonl")

    def search(query):
        return []

    with SnapSession.snap(fixture) as s:
        search = s.wrap(search)
        search(query="weather today")

    with pytest.raises(AssertionError) as exc_info:
        s.assert_called_with("search", query=contains("navassist"))

    msg = str(exc_info.value)
    assert "weather today" in msg
    assert "navassist" in msg


def test_session_assert_call_order(tmp_path):
    fixture = str(tmp_path / "s.jsonl")

    def search(q):
        return []

    def get_weather(city):
        return {}

    with SnapSession.snap(fixture) as s:
        search = s.wrap(search)
        get_weather = s.wrap(get_weather)
        search(q="docs")
        get_weather(city="london")

    s.assert_call_order(["search", "get_weather"])


def test_session_assert_no_errors(tmp_path):
    fixture = str(tmp_path / "s.jsonl")

    def safe():
        return "ok"

    with SnapSession.snap(fixture) as s:
        safe = s.wrap(safe)
        safe()

    s.assert_no_errors()


def test_session_assert_no_errors_failure(tmp_path):
    fixture = str(tmp_path / "s.jsonl")

    def boom():
        raise RuntimeError("oops")

    with SnapSession.snap(fixture) as s:
        boom = s.wrap(boom)
        with pytest.raises(RuntimeError):
            boom()

    with pytest.raises(AssertionError, match="oops"):
        s.assert_no_errors()


def test_session_replay_assertions(tmp_path):
    fixture = str(tmp_path / "s.jsonl")

    def search(query):
        return ["doc1", "doc2"]

    with SnapSession.snap(fixture) as s:
        search = s.wrap(search)
        search(query="navassist")

    def _search_replay_stub(query):
        raise RuntimeError("should not run")

    _search_replay_stub.__name__ = "search"

    with SnapSession.replay(fixture) as s:
        search = s.wrap(_search_replay_stub)
        search(query="anything")

    s.assert_called("search", times=1)
    s.assert_called_with("search", query="anything")


def test_session_assert_raised(tmp_path):
    fixture = str(tmp_path / "s.jsonl")

    def risky(x):
        raise ValueError("bad input")

    with SnapSession.snap(fixture) as s:
        risky = s.wrap(risky)
        with pytest.raises(ValueError):
            risky(0)

    s.assert_raised("risky", "ValueError")


def test_gt_predicate(tmp_path):
    fixture = str(tmp_path / "s.jsonl")

    def threshold_check(value):
        return value > 0.5

    with SnapSession.snap(fixture) as s:
        threshold_check = s.wrap(threshold_check)
        threshold_check(value=0.8)

    s.assert_called_with("threshold_check", value=gt(0.5))


# Predicate __repr__ and missing predicates


def test_predicate_reprs():
    assert repr(contains("x")) == "contains('x')"
    assert repr(matches(r"\d+")) == "matches('\\\\d+')"
    assert repr(any_of("a", "b")) == "any_of('a', 'b')"
    assert repr(gt(5)) == "gt(5)"
    assert repr(lt(3)) == "lt(3)"


def test_predicate_any_of():
    from toolsnap import any_of

    p = any_of("CAUTION", "IMMEDIATE")
    assert p("CAUTION") is True
    assert p("IMMEDIATE") is True
    assert p("OK") is False


def test_predicate_lt():
    from toolsnap import lt

    p = lt(0.5)
    assert p(0.3) is True
    assert p(0.7) is False


# Async SnapSession snap / replay


@pytest.mark.asyncio
async def test_session_snap_async(tmp_path):
    fixture = str(tmp_path / "s.jsonl")

    async def fetch(url):
        return f"data:{url}"

    with SnapSession.snap(fixture) as s:
        fetch = s.wrap(fetch)
        await fetch(url="http://a.com")

    s.assert_called("fetch", times=1)
    s.assert_called_with("fetch", url="http://a.com")


@pytest.mark.asyncio
async def test_session_replay_async(tmp_path):
    fixture = str(tmp_path / "s.jsonl")

    async def fetch(url):
        return f"data:{url}"

    with SnapSession.snap(fixture) as s:
        fetch = s.wrap(fetch)
        await fetch("http://a.com")

    async def _fetch_stub(url):
        raise RuntimeError("should not run")

    _fetch_stub.__name__ = "fetch"

    with SnapSession.replay(fixture) as s:
        fetch = s.wrap(_fetch_stub)
        result = await fetch("anything")

    assert result == "data:http://a.com"
    s.assert_called("fetch", times=1)


@pytest.mark.asyncio
async def test_session_replay_async_non_strict(tmp_path):
    fixture = str(tmp_path / "s.jsonl")

    async def fetch(url):
        return f"data:{url}"

    with SnapSession.snap(fixture) as s:
        fetch = s.wrap(fetch)
        await fetch("http://a.com")

    async def _fetch_stub(url):
        return f"real:{url}"

    _fetch_stub.__name__ = "fetch"

    with SnapSession.replay(fixture, strict=False) as s:
        fetch = s.wrap(_fetch_stub)
        r1 = await fetch("x")  # replayed from fixture
        r2 = await fetch("b")  # falls through to real stub

    assert r1 == "data:http://a.com"
    assert r2 == "real:b"


@pytest.mark.asyncio
async def test_session_replay_async_error(tmp_path):
    fixture = str(tmp_path / "s.jsonl")

    async def risky():
        raise ValueError("async boom")

    with SnapSession.snap(fixture) as s:
        risky = s.wrap(risky)
        with pytest.raises(ValueError):
            await risky()

    async def _risky_stub():
        return "fine"

    _risky_stub.__name__ = "risky"

    with SnapSession.replay(fixture) as s:
        replayed_risky = s.wrap(_risky_stub)
        with pytest.raises(ValueError, match="async boom"):
            await replayed_risky()


# wrap() with module=None


def test_session_wrap_module_none(tmp_path):
    fixture = str(tmp_path / "s.jsonl")

    def orphan():
        return 42

    orphan.__module__ = "__nonexistent_xyz__"  # forces inspect.getmodule() → None

    with SnapSession.snap(fixture) as s:
        wrapped = s.wrap(orphan)
        result = wrapped()

    assert result == 42
    s.assert_called("orphan", times=1)


# Assertion failure branches


def test_session_assert_called_times_failure(tmp_path):
    fixture = str(tmp_path / "s.jsonl")

    def search(q):
        return []

    with SnapSession.snap(fixture) as s:
        search = s.wrap(search)
        search(q="hello")  # called once

    with pytest.raises(AssertionError, match="times=2"):
        s.assert_called("search", times=2)


def test_session_assert_not_called_never_wrapped(tmp_path):
    fixture = str(tmp_path / "s.jsonl")

    with SnapSession.snap(fixture) as s:
        pass  # nothing wrapped

    s.assert_not_called("never_seen")  # log is None → actual=0 → passes silently


def test_session_assert_called_with_fn_not_called(tmp_path):
    fixture = str(tmp_path / "s.jsonl")

    def search(q):
        return []

    with SnapSession.snap(fixture) as s:
        s.wrap(search)  # wrapped but never called

    with pytest.raises(AssertionError, match="never called"):
        s.assert_called_with("search", q="x")


def test_session_assert_called_with_call_out_of_bounds(tmp_path):
    fixture = str(tmp_path / "s.jsonl")

    def search(q):
        return []

    with SnapSession.snap(fixture) as s:
        search = s.wrap(search)
        search(q="hello")

    with pytest.raises(AssertionError, match="call index 5"):
        s.assert_called_with("search", call=5, q="hello")


def test_session_assert_called_with_specific_call_no_match(tmp_path):
    fixture = str(tmp_path / "s.jsonl")

    def search(q):
        return []

    with SnapSession.snap(fixture) as s:
        search = s.wrap(search)
        search(q="hello")

    with pytest.raises(AssertionError):
        s.assert_called_with("search", call=0, q="wrong")


def test_session_assert_call_order_failure(tmp_path):
    fixture = str(tmp_path / "s.jsonl")

    def a():
        return 1

    def b():
        return 2

    with SnapSession.snap(fixture) as s:
        b = s.wrap(b)  # b registered first → appears first in timeline
        a = s.wrap(a)
        a()
        b()

    with pytest.raises(AssertionError, match="assert_call_order"):
        s.assert_call_order(
            ["a", "b"]
        )  # timeline is [b, a] → b consumed before b can follow a


def test_session_assert_raised_failure(tmp_path):
    fixture = str(tmp_path / "s.jsonl")

    def safe():
        return "ok"

    with SnapSession.snap(fixture) as s:
        safe = s.wrap(safe)
        safe()  # call 0: no error
        safe()  # call 1: no error — exercises the loop back-edge in assert_raised

    with pytest.raises(AssertionError, match="assert_raised"):
        s.assert_raised("safe", "ValueError")


# Remaining session paths


def test_session_assert_called_failure_never_called(tmp_path):
    """assert_called() with no times= raises when fn was never called."""
    fixture = str(tmp_path / "s.jsonl")

    def search(q):
        return []

    with SnapSession.snap(fixture) as s:
        s.wrap(search)  # wrapped but never called

    with pytest.raises(AssertionError, match="never called"):
        s.assert_called("search")


def test_session_assert_not_called_failure(tmp_path):
    """assert_not_called raises when fn was actually called."""
    fixture = str(tmp_path / "s.jsonl")

    def search(q):
        return []

    with SnapSession.snap(fixture) as s:
        search = s.wrap(search)
        search(q="hello")

    with pytest.raises(AssertionError, match="never called"):
        s.assert_not_called("search")


def test_session_assert_called_with_specific_call_success(tmp_path):
    """assert_called_with with call=N that matches exits the function normally."""
    fixture = str(tmp_path / "s.jsonl")

    def search(q):
        return []

    with SnapSession.snap(fixture) as s:
        search = s.wrap(search)
        search(q="hello")

    s.assert_called_with("search", call=0, q="hello")  # matches → normal exit


def test_session_replay_sync_non_strict(tmp_path):
    """SnapSession.replay strict=False falls through to real fn on extra calls."""
    fixture = str(tmp_path / "s.jsonl")

    def search(q):
        return [f"recorded:{q}"]

    with SnapSession.snap(fixture) as s:
        search = s.wrap(search)
        search(q="hello")

    def _search_stub(q):
        return ["real"]

    _search_stub.__name__ = "search"

    with SnapSession.replay(fixture, strict=False) as s:
        search = s.wrap(_search_stub)
        r1 = search(q="anything")  # replayed
        r2 = search(q="extra")  # falls through to real stub

    assert r1 == ["recorded:hello"]
    assert r2 == ["real"]


def test_session_replay_sync_error(tmp_path):
    """SnapSession.replay replays a recorded exception for a sync function."""
    fixture = str(tmp_path / "s.jsonl")

    def boom():
        raise ValueError("recorded boom")

    with SnapSession.snap(fixture) as s:
        boom = s.wrap(boom)
        with pytest.raises(ValueError):
            boom()

    def _boom_stub():
        return "fine"

    _boom_stub.__name__ = "boom"

    with SnapSession.replay(fixture) as s:
        replayed_boom = s.wrap(_boom_stub)
        with pytest.raises(ValueError, match="recorded boom"):
            replayed_boom()


@pytest.mark.asyncio
async def test_session_replay_async_strict_over_call(tmp_path):
    """SnapSession.replay with async fn raises UnexpectedToolCall on extra call."""
    fixture = str(tmp_path / "s.jsonl")

    async def fetch(url):
        return f"data:{url}"

    with SnapSession.snap(fixture) as s:
        fetch = s.wrap(fetch)
        await fetch(url="http://a.com")

    async def _fetch_stub(url):
        return "stub"

    _fetch_stub.__name__ = "fetch"

    with SnapSession.replay(fixture) as s:
        fetch = s.wrap(_fetch_stub)
        await fetch("x")  # replayed
        with pytest.raises(UnexpectedToolCall):
            await fetch("x")  # over-call → strict=True raises


def test_session_replay_sync_strict_over_call(tmp_path):
    """SnapSession.replay with sync fn raises UnexpectedToolCall on extra call."""
    fixture = str(tmp_path / "s.jsonl")

    def search(q):
        return []

    with SnapSession.snap(fixture) as s:
        search = s.wrap(search)
        search(q="hello")

    def _search_stub(q):
        return []

    _search_stub.__name__ = "search"

    with SnapSession.replay(fixture) as s:
        search = s.wrap(_search_stub)
        search(q="x")  # replayed
        with pytest.raises(UnexpectedToolCall):
            search(q="x")  # over-call → strict=True raises


def test_wrap_warns_when_fn_is_snap_decorated(tmp_path):
    """wrap() emits a UserWarning when the function is already @snap-decorated."""
    fixture = str(tmp_path / "s.jsonl")

    @snap(fixture)
    def my_tool():
        return "real"

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with SnapSession.snap(fixture) as s:
            s.wrap(my_tool)

    assert any("@snap" in str(w.message) for w in caught)
