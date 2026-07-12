import pytest

from toolsnap import SnapSession, contains, gt, matches


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
