import functools
import inspect
import time
from typing import Any, Callable, TypeVar

from .models import CallRecord
from .store import CallStore

_F = TypeVar("_F", bound=Callable[..., Any])


def snap(path: str, *, serializer=None, deserializer=None) -> Callable[[_F], _F]:
    """
    Decorator that records every call to the wrapped function into a JSONL fixture file.

    Args:
        path: Path to the JSONL fixture file.
        serializer: Optional callable to convert a non-serializable result to a
            JSON-serializable form before storing.
        deserializer: Unused in recording mode; kept for API symmetry with @replay.
    """

    def decorator(fn: _F) -> _F:
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
                        serializer(result)
                        if serializer and result is not None
                        else result
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

    return decorator  # type: ignore[return-value]
