import pytest

from toolsnap import UnexpectedToolCall, replay, snap


def test_replay_returns_recorded_results(tmp_fixture):
    @snap(tmp_fixture)
    def greet(name):
        return f"hello {name}"

    greet("alice")
    greet("bob")
    greet("carol")

    call_log = []

    def _stub(name):
        call_log.append(name)
        return "real"

    _stub.__name__ = "greet"
    greet = replay(tmp_fixture)(_stub)

    assert greet("x") == "hello alice"
    assert greet("y") == "hello bob"
    assert greet("z") == "hello carol"
    assert call_log == [], "real function should not have been called"


def test_replay_strict_raises_on_extra_call(tmp_fixture):
    @snap(tmp_fixture)
    def fn(x):
        return x * 2

    fn(1)

    def _stub(x):
        return x * 2

    _stub.__name__ = "fn"
    fn = replay(tmp_fixture, strict=True)(_stub)

    fn(0)
    with pytest.raises(UnexpectedToolCall):
        fn(0)


def test_replay_non_strict_falls_through(tmp_fixture):
    @snap(tmp_fixture)
    def fn(x):
        return x * 2

    fn(3)

    def _stub(x):
        return x * 10

    _stub.__name__ = "fn"
    fn = replay(tmp_fixture, strict=False)(_stub)

    assert fn(0) == 6  # replayed
    assert fn(5) == 50  # fell through to real


def test_replay_raises_recorded_exception(tmp_fixture):
    @snap(tmp_fixture)
    def boom(x):
        raise ValueError("recorded error")

    with pytest.raises(ValueError):
        boom(1)

    def _stub(x):
        return "should not reach"

    _stub.__name__ = "boom"
    replayed = replay(tmp_fixture)(_stub)

    with pytest.raises(ValueError, match="recorded error"):
        replayed(1)


def test_replay_bare_decorator(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    @snap
    def get_value():
        return 99

    get_value()

    def _stub():
        raise RuntimeError("should not run")

    _stub.__name__ = "get_value"
    replayed = replay(_stub)

    assert replayed() == 99


def test_resolve_exception_unknown_type():
    from toolsnap.replayer import _resolve_exception

    assert _resolve_exception("SomeCustomException") is RuntimeError


@pytest.mark.asyncio
async def test_async_replay_returns_recorded_results(tmp_fixture):
    @snap(tmp_fixture)
    async def fetch(url):
        return f"content of {url}"

    await fetch("http://a.com")
    await fetch("http://b.com")

    async def _stub(url):
        raise RuntimeError("should not call real function")

    _stub.__name__ = "fetch"
    fetch = replay(tmp_fixture)(_stub)

    assert await fetch("x") == "content of http://a.com"
    assert await fetch("y") == "content of http://b.com"


@pytest.mark.asyncio
async def test_async_replay_strict_raises(tmp_fixture):
    @snap(tmp_fixture)
    async def task(n):
        return n * 3

    await task(1)

    async def _stub(n):
        return n * 3

    _stub.__name__ = "task"
    task = replay(tmp_fixture, strict=True)(_stub)

    await task(0)
    with pytest.raises(UnexpectedToolCall):
        await task(0)


@pytest.mark.asyncio
async def test_async_replay_raises_recorded_exception(tmp_fixture):
    @snap(tmp_fixture)
    async def risky():
        raise TypeError("async error")

    with pytest.raises(TypeError):
        await risky()

    async def _stub():
        return "fine"

    _stub.__name__ = "risky"
    replayed = replay(tmp_fixture)(_stub)

    with pytest.raises(TypeError, match="async error"):
        await replayed()


@pytest.mark.asyncio
async def test_async_replay_non_strict_falls_through(tmp_fixture):
    @snap(tmp_fixture)
    async def task(n):
        return n * 2

    await task(5)

    async def _stub(n):
        return n * 99

    _stub.__name__ = "task"
    task = replay(tmp_fixture, strict=False)(_stub)

    assert await task(0) == 10  # replayed: 5 * 2
    assert await task(0) == 0  # fell through: 0 * 99
