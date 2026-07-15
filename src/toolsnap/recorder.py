import functools
import inspect
import threading
import time
from typing import Any, Callable, TypeVar, overload

from .models import CallRecord
from .store import CallStore, _resolve_path
from .serialize import auto_serialize

_F = TypeVar("_F", bound=Callable[..., Any])

# Tracks fixture paths already overwritten in this process run.
# Ensures each path is truncated at most once, even when multiple
# decorated functions share the same fixture file.
_overwritten_paths: set[str] = set()

_MAX_RESULT_BYTES_DEFAULT = 64 * 1024  # 64 KB


@overload
def snap(
    path_or_fn: _F,
    *,
    serializer: Any = ...,
    deserializer: Any = ...,
    overwrite: bool = ...,
    max_result_bytes: int = ...,
) -> _F: ...
@overload
def snap(
    path_or_fn: str | None = ...,
    *,
    serializer: Any = ...,
    deserializer: Any = ...,
    overwrite: bool = ...,
    max_result_bytes: int = ...,
) -> Callable[[_F], _F]: ...


def snap(
    path_or_fn=None,
    *,
    serializer=None,
    deserializer=None,
    overwrite=True,
    max_result_bytes=_MAX_RESULT_BYTES_DEFAULT,
):
    """
    Decorator that records every call to the wrapped function into a JSONL fixture file.

    Usage::

        @snap                        # auto-named: fixtures/{fn_name}.jsonl
        @snap()                      # same
        @snap("my_fixtures/")        # directory:  my_fixtures/{fn_name}.jsonl
        @snap("path/to/file.jsonl")  # explicit path

    Args:
        path_or_fn: Optional path string, or the decorated function when used bare.
        serializer: Optional callable to convert a non-serializable result before storing.
            If omitted, toolsnap auto-detects Pydantic models, dataclasses, and dicts.
        deserializer: Unused in recording mode; kept for API symmetry with @replay.
        overwrite: If True (default), the fixture file is cleared on the first call of
            each process run so re-running the script always produces a fresh fixture.
            Set to False to accumulate calls across multiple runs.
        max_result_bytes: Maximum serialized size of a result before it is replaced with
            a truncation marker. Default 64 KB. Set to 0 to disable the limit.
    """
    if callable(path_or_fn):
        # @snap used bare without parentheses
        return _build_recorder(
            path_or_fn,
            _resolve_path(None, path_or_fn.__name__),
            serializer,
            overwrite,
            max_result_bytes,
        )

    # @snap(), @snap("dir/"), or @snap("file.jsonl")
    def decorator(fn: _F) -> _F:
        return _build_recorder(
            fn,
            _resolve_path(path_or_fn, fn.__name__),
            serializer,
            overwrite,
            max_result_bytes,
        )

    return decorator


def _build_recorder(
    fn: _F, path: str, serializer, overwrite: bool, max_result_bytes: int
) -> _F:
    store = CallStore(path)
    call_count = 0
    _count_lock = threading.Lock()

    if inspect.iscoroutinefunction(fn):

        @functools.wraps(fn)
        async def async_wrapper(*args, **kwargs):
            nonlocal call_count
            with _count_lock:
                idx = call_count
                call_count += 1
            t0 = time.perf_counter()
            error = None
            result = None
            try:
                result = await fn(*args, **kwargs)
            except Exception as e:
                error = {"type": type(e).__name__, "message": str(e)}
                raise
            finally:
                duration_ms = (time.perf_counter() - t0) * 1000
                stored_result = (
                    serializer(result)
                    if serializer and result is not None
                    else auto_serialize(result, max_result_bytes)
                )
                if overwrite and path not in _overwritten_paths:
                    store.clear()
                    _overwritten_paths.add(path)
                store.append(
                    CallRecord(
                        call_index=idx,
                        fn=fn.__name__,
                        args=list(args),
                        kwargs=kwargs,
                        result=stored_result,
                        duration_ms=duration_ms,
                        ts=time.time(),
                        error=error,
                    )
                )
            return result

        async_wrapper._is_snap_wrapped = True  # type: ignore[attr-defined]
        return async_wrapper  # type: ignore[return-value]

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        nonlocal call_count
        with _count_lock:
            idx = call_count
            call_count += 1
        t0 = time.perf_counter()
        error = None
        result = None
        try:
            result = fn(*args, **kwargs)
        except Exception as e:
            error = {"type": type(e).__name__, "message": str(e)}
            raise
        finally:
            duration_ms = (time.perf_counter() - t0) * 1000
            stored_result = (
                serializer(result)
                if serializer and result is not None
                else auto_serialize(result, max_result_bytes)
            )
            if overwrite and path not in _overwritten_paths:
                store.clear()
                _overwritten_paths.add(path)
            store.append(
                CallRecord(
                    call_index=idx,
                    fn=fn.__name__,
                    args=list(args),
                    kwargs=kwargs,
                    result=stored_result,
                    duration_ms=duration_ms,
                    ts=time.time(),
                    error=error,
                )
            )
        return result

    wrapper._is_snap_wrapped = True  # type: ignore[attr-defined]
    return wrapper  # type: ignore[return-value]
