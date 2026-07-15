import threading
import warnings

import pytest

from toolsnap import snap
from toolsnap.serialize import _TRUNCATED_MARKER
from toolsnap.store import CallStore


def test_sync_record_creates_fixture(tmp_fixture):
    @snap(tmp_fixture)
    def add(a, b):
        return a + b

    add(1, 2)
    add(3, 4)
    add(5, 6)

    records = CallStore(tmp_fixture).load()
    assert len(records) == 3
    assert records[0].result == 3
    assert records[1].result == 7
    assert records[2].result == 11


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

    records = CallStore(tmp_fixture).load()
    alpha_records = [r for r in records if r.fn == "alpha"]
    beta_records = [r for r in records if r.fn == "beta"]
    assert alpha_records[0].call_index == 0
    assert alpha_records[1].call_index == 1
    assert beta_records[0].call_index == 0


def test_snap_bare_decorator(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    @snap
    def get_value():
        return 42

    get_value()

    records = CallStore(str(tmp_path / "fixtures" / "get_value.jsonl")).load()
    assert records[0].result == 42


def test_overwrite_default_clears_on_rerun(tmp_fixture):
    @snap(tmp_fixture)
    def fn():
        return 1

    fn()  # first process-simulated call — clears then writes

    records = CallStore(tmp_fixture).load()
    assert len(records) == 1


def test_overwrite_false_accumulates(tmp_fixture):
    @snap(tmp_fixture, overwrite=False)
    def fn():
        return 1

    fn()
    fn()

    records = CallStore(tmp_fixture).load()
    assert len(records) == 2


def test_concurrent_calls_thread_safe(tmp_fixture):
    @snap(tmp_fixture, overwrite=False)
    def work(n: int) -> int:
        return n * 2

    threads = [threading.Thread(target=work, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    records = CallStore(tmp_fixture).load()
    assert len(records) == 10
    indices = [r.call_index for r in records]
    assert len(set(indices)) == 10


def test_max_result_bytes_truncates_large_result(tmp_fixture):
    big = "x" * 200  # 200 bytes > 100 byte limit

    @snap(tmp_fixture, max_result_bytes=100)
    def get_big() -> str:
        return big

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        get_big()

    assert any("truncat" in str(w.message).lower() for w in caught)
    records = CallStore(tmp_fixture).load()
    assert isinstance(records[0].result, dict)
    assert records[0].result.get(_TRUNCATED_MARKER) is True
    assert "sha256" in records[0].result


def test_max_result_bytes_passes_small_result(tmp_fixture):
    @snap(tmp_fixture, max_result_bytes=1024)
    def get_small() -> str:
        return "hello"

    get_small()

    records = CallStore(tmp_fixture).load()
    assert records[0].result == "hello"


@pytest.mark.asyncio
async def test_async_snap_records(tmp_fixture):
    @snap(tmp_fixture)
    async def fetch(url):
        return f"content of {url}"

    await fetch("http://a.com")
    await fetch("http://b.com")

    records = CallStore(tmp_fixture).load()
    assert len(records) == 2
    assert records[0].result == "content of http://a.com"
    assert records[1].result == "content of http://b.com"
