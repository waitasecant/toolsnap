import pytest

from toolsnap import UnexpectedToolCall, replay, snap


def test_sync_record_creates_fixture(tmp_fixture):
    @snap(tmp_fixture)
    def add(a, b):
        return a + b

    add(1, 2)
    add(3, 4)
    add(5, 6)

    from toolsnap.store import CallStore

    records = CallStore(tmp_fixture).load()
    assert len(records) == 3
    assert records[0].result == 3
    assert records[1].result == 7
    assert records[2].result == 11


def test_sync_replay_returns_recorded_results(tmp_fixture):
    @snap(tmp_fixture)
    def greet(name):
        return f"hello {name}"

    greet("alice")
    greet("bob")
    greet("carol")

    call_log = []

    def _greet_stub(name):
        call_log.append(name)  # should never run
        return "real"

    _greet_stub.__name__ = "greet"
    greet = replay(tmp_fixture)(_greet_stub)

    assert greet("x") == "hello alice"
    assert greet("y") == "hello bob"
    assert greet("z") == "hello carol"
    assert call_log == [], "real function should not have been called"


def test_sync_replay_strict_raises_on_extra_call(tmp_fixture):
    @snap(tmp_fixture)
    def fn(x):
        return x * 2

    fn(1)

    def _fn_stub(x):
        return x * 2

    _fn_stub.__name__ = "fn"
    fn = replay(tmp_fixture, strict=True)(_fn_stub)

    fn(0)  # first call: replayed
    with pytest.raises(UnexpectedToolCall):
        fn(0)  # second call: no fixture entry


def test_sync_replay_non_strict_falls_through(tmp_fixture):
    @snap(tmp_fixture)
    def fn(x):
        return x * 2

    fn(3)

    def _fn_stub(x):
        return x * 10  # real impl

    _fn_stub.__name__ = "fn"
    fn = replay(tmp_fixture, strict=False)(_fn_stub)

    assert fn(0) == 6  # replayed
    assert fn(5) == 50  # fell through to real


def test_sync_replay_raises_recorded_exception(tmp_fixture):
    @snap(tmp_fixture)
    def boom(x):
        raise ValueError("recorded error")

    with pytest.raises(ValueError):
        boom(1)

    def _boom_stub(x):
        return "should not reach"

    _boom_stub.__name__ = "boom"
    replayed_boom = replay(tmp_fixture)(_boom_stub)

    with pytest.raises(ValueError, match="recorded error"):
        replayed_boom(1)


def test_call_index_is_per_function(tmp_fixture):
    @snap(tmp_fixture)
    def alpha(x):
        return x + 1

    @snap(tmp_fixture)
    def beta(x):
        return x + 100

    alpha(0)
    alpha(1)
    beta(0)

    from toolsnap.store import CallStore

    records = CallStore(tmp_fixture).load()
    alpha_records = [r for r in records if r.fn == "alpha"]
    beta_records = [r for r in records if r.fn == "beta"]
    assert alpha_records[0].call_index == 0
    assert alpha_records[1].call_index == 1
    assert beta_records[0].call_index == 0


@pytest.mark.asyncio
async def test_async_record_and_replay(tmp_fixture):
    @snap(tmp_fixture)
    async def fetch(url):
        return f"content of {url}"

    await fetch("http://a.com")
    await fetch("http://b.com")

    async def _fetch_stub(url):
        raise RuntimeError("should not call real function")

    _fetch_stub.__name__ = "fetch"
    fetch = replay(tmp_fixture)(_fetch_stub)

    assert await fetch("x") == "content of http://a.com"
    assert await fetch("y") == "content of http://b.com"


@pytest.mark.asyncio
async def test_async_replay_strict_raises(tmp_fixture):
    @snap(tmp_fixture)
    async def task(n):
        return n * 3

    await task(1)

    async def _task_stub(n):
        return n * 3

    _task_stub.__name__ = "task"
    task = replay(tmp_fixture, strict=True)(_task_stub)

    await task(0)  # replayed
    with pytest.raises(UnexpectedToolCall):
        await task(0)  # over fixture limit


@pytest.mark.asyncio
async def test_async_replay_recorded_exception(tmp_fixture):
    @snap(tmp_fixture)
    async def risky():
        raise TypeError("async error")

    with pytest.raises(TypeError):
        await risky()

    async def _risky_stub():
        return "fine"

    _risky_stub.__name__ = "risky"
    replayed_risky = replay(tmp_fixture)(_risky_stub)

    with pytest.raises(TypeError, match="async error"):
        await replayed_risky()
