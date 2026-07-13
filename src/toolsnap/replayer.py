import functools
import inspect
from typing import Any, Callable, TypeVar

_F = TypeVar("_F", bound=Callable[..., Any])


class UnexpectedToolCall(Exception):
    pass


def _resolve_exception(type_name: str) -> type[Exception]:
    import builtins

    cls = getattr(builtins, type_name, None)
    if cls is not None and isinstance(cls, type) and issubclass(cls, Exception):
        return cls
    return RuntimeError


def replay(path: str, *, strict: bool = True) -> Callable[[_F], _F]:
    """
    Decorator that replays recorded calls from a JSONL fixture file instead of
    calling the real function.

    Args:
        path: Path to the JSONL fixture file produced by @snap.
        strict: If True (default), raise UnexpectedToolCall when the function is
            called more times than the fixture contains. If False, fall through
            to the real function.
    """

    def decorator(fn: _F) -> _F:
        from .store import CallStore

        store = CallStore(path)
        index = store.load_index()
        call_count = 0

        if inspect.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args, **kwargs):
                nonlocal call_count
                idx = call_count
                call_count += 1
                records = index.get(fn.__name__, [])
                if idx >= len(records):
                    if strict:
                        raise UnexpectedToolCall(
                            f"{fn.__name__} called {idx + 1} times but fixture only has "
                            f"{len(records)} record(s)"
                        )
                    return await fn(*args, **kwargs)
                record = records[idx]
                if record.error:
                    exc_type = _resolve_exception(record.error["type"])
                    raise exc_type(record.error["message"])
                return record.result

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            nonlocal call_count
            idx = call_count
            call_count += 1
            records = index.get(fn.__name__, [])
            if idx >= len(records):
                if strict:
                    raise UnexpectedToolCall(
                        f"{fn.__name__} called {idx + 1} times but fixture only has "
                        f"{len(records)} record(s)"
                    )
                return fn(*args, **kwargs)
            record = records[idx]
            if record.error:
                exc_type = _resolve_exception(record.error["type"])
                raise exc_type(record.error["message"])
            return record.result

        return wrapper  # type: ignore[return-value]

    return decorator  # type: ignore[return-value]
