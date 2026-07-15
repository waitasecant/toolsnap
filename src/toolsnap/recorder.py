import functools
import inspect
import time
from typing import Any, Callable, TypeVar, overload

from .models import CallRecord
from .store import CallStore, _resolve_path

_F = TypeVar("_F", bound=Callable[..., Any])

# Tracks fixture paths already overwritten in this process run.
# Ensures each path is truncated at most once, even when multiple
# decorated functions share the same fixture file.
_overwritten_paths: set[str] = set()


@overload
def snap(
    path_or_fn: _F,
    *,
    serializer: Any = ...,
    deserializer: Any = ...,
    overwrite: bool = ...,
) -> _F: ...
@overload
def snap(
    path_or_fn: str | None = ...,
    *,
    serializer: Any = ...,
    deserializer: Any = ...,
    overwrite: bool = ...,
) -> Callable[[_F], _F]: ...


def snap(path_or_fn=None, *, serializer=None, deserializer=None, overwrite=True):
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
        deserializer: Unused in recording mode; kept for API symmetry with @replay.
        overwrite: If True (default), the fixture file is cleared on the first call of
            each process run so re-running the script always produces a fresh fixture.
            Set to False to accumulate calls across multiple runs.
    """
    if callable(path_or_fn):
        # @snap used bare without parentheses
        return _build_recorder(
            path_or_fn, _resolve_path(None, path_or_fn.__name__), serializer, overwrite
        )

    # @snap(), @snap("dir/"), or @snap("file.jsonl")
    def decorator(fn: _F) -> _F:
        return _build_recorder(
            fn, _resolve_path(path_or_fn, fn.__name__), serializer, overwrite
        )

    return decorator


def _build_recorder(fn: _F, path: str, serializer, overwrite: bool) -> _F:
    store = CallStore(path)
    call_count = 0

    if inspect.iscoroutinefunction(fn):

        @functools.wraps(fn)
        async def async_wrapper(*args, **kwargs):
            nonlocal call_count
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
                    serializer(result) if serializer and result is not None else result
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
                serializer(result) if serializer and result is not None else result
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
