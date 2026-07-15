import warnings

import pytest

from toolsnap import snap
from toolsnap.serialize import _TRUNCATED_MARKER
from toolsnap.store import CallStore


def test_pydantic_model_is_auto_serialized(tmp_fixture):
    try:
        from pydantic import BaseModel
    except ImportError:
        pytest.skip("pydantic not installed")

    class Point(BaseModel):
        x: float
        y: float

    @snap(tmp_fixture)
    def get_point() -> Point:
        return Point(x=1.0, y=2.0)

    get_point()

    records = CallStore(tmp_fixture).load()
    assert records[0].result == {"x": 1.0, "y": 2.0}


def test_dataclass_is_auto_serialized(tmp_fixture):
    import dataclasses

    @dataclasses.dataclass
    class Color:
        r: int
        g: int
        b: int

    @snap(tmp_fixture)
    def get_color() -> Color:
        return Color(255, 128, 0)

    get_color()

    records = CallStore(tmp_fixture).load()
    assert records[0].result == {"r": 255, "g": 128, "b": 0}


def test_dict_attr_object_is_auto_serialized(tmp_fixture):
    class MyPoint:
        def __init__(self, x, y):
            self.x = x
            self.y = y

    @snap(tmp_fixture)
    def get_point():
        return MyPoint(3, 4)

    get_point()

    records = CallStore(tmp_fixture).load()
    assert records[0].result == {"x": 3, "y": 4}


def test_fallback_to_str_with_warning(tmp_fixture):
    class Unserializable:
        def __str__(self):
            return "custom-string"

    @snap(tmp_fixture)
    def get_obj():
        return Unserializable()

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        get_obj()

    assert any("str()" in str(w.message) for w in caught)
    records = CallStore(tmp_fixture).load()
    assert records[0].result == "custom-string"


def test_dict_attr_non_serializable_falls_to_str(tmp_fixture):
    class Inner:
        __slots__ = ()

        def __str__(self):
            return "inner-str"

    class Outer:
        def __init__(self):
            self.value = Inner()

        def __str__(self):
            return "outer-str"

    @snap(tmp_fixture)
    def get_outer():
        return Outer()

    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        get_outer()

    records = CallStore(tmp_fixture).load()
    assert records[0].result == "outer-str"


def test_pydantic_model_dump_raises_falls_to_str(tmp_fixture):
    class BrokenPydantic:
        def model_dump(self):
            raise RuntimeError("model_dump exploded")

        def __str__(self):
            return "broken-pydantic"

    @snap(tmp_fixture)
    def get_broken():
        return BrokenPydantic()

    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        get_broken()

    records = CallStore(tmp_fixture).load()
    assert records[0].result == "broken-pydantic"


def test_dataclass_asdict_raises_falls_through(tmp_fixture):
    import dataclasses

    class BadCopy:
        def __deepcopy__(self, memo):
            raise RuntimeError("cannot deepcopy")

        def __str__(self):
            return "bad-copy"

    @dataclasses.dataclass
    class Wrapper:
        value: object

    @snap(tmp_fixture)
    def get_wrapper():
        return Wrapper(value=BadCopy())

    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        get_wrapper()

    records = CallStore(tmp_fixture).load()
    assert records[0].result is not None


def test_check_size_returns_none_when_model_dump_not_json_serializable(tmp_fixture):
    import datetime

    try:
        from pydantic import BaseModel
    except ImportError:
        pytest.skip("pydantic not installed")

    class Event(BaseModel):
        ts: datetime.datetime

    @snap(tmp_fixture)
    def get_event():
        return Event(ts=datetime.datetime(2026, 1, 1))

    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        get_event()

    records = CallStore(tmp_fixture).load()
    assert records[0].result is not None


def test_large_result_stored_as_truncation_marker(tmp_fixture):
    big = "x" * 200

    @snap(tmp_fixture, max_result_bytes=100)
    def get_big() -> str:
        return big

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        get_big()

    assert any("truncat" in str(w.message).lower() for w in caught)
    records = CallStore(tmp_fixture).load()
    assert records[0].result.get(_TRUNCATED_MARKER) is True
    assert "sha256" in records[0].result


def test_result_within_limit_stored_as_is(tmp_fixture):
    @snap(tmp_fixture, max_result_bytes=1024)
    def get_small() -> str:
        return "hello"

    get_small()

    records = CallStore(tmp_fixture).load()
    assert records[0].result == "hello"


def test_max_result_bytes_zero_disables_limit(tmp_fixture):
    # max_result_bytes=0 should mean "no limit" — large results are stored as-is.
    big = "x" * 10_000

    @snap(tmp_fixture, max_result_bytes=0)
    def get_big() -> str:
        return big

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        get_big()

    assert not any("truncat" in str(w.message).lower() for w in caught)
    records = CallStore(tmp_fixture).load()
    assert records[0].result == big
