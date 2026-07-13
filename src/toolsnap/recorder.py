import functools
import inspect
import time
from typing import Any, Callable, TypeVar, overload

from .models import CallRecord
from .store import CallStore, _resolve_path

_F = TypeVar("_F", bound=Callable[..., Any])


@overload
def snap(path_or_fn: _F, *, serializer: Any = ..., deserializer: Any = ...) -> _F: ...
@overload
def snap(
    path_or_fn: str | None = ..., *, serializer: Any = ..., deserializer: Any = ...
) -> Callable[[_F], _F]: ...


def snap(path_or_fn=None, *, serializer=None, deserializer=None):
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
    """
    if callable(path_or_fn):
        # @snap used bare without parentheses
        return _build_recorder(
            path_or_fn, _resolve_path(None, path_or_fn.__name__), serializer
        )

    # @snap(), @snap("dir/"), or @snap("file.jsonl")
    def decorator(fn: _F) -> _F:
        return _build_recorder(fn, _resolve_path(path_or_fn, fn.__name__), serializer)

    return decorator


def _build_recorder(fn: _F, path: str, serializer) -> _F:
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

    return wrapper  # type: ignore[return-value]
