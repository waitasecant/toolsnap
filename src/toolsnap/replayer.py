import functools
import inspect
from typing import Any, Callable, TypeVar, overload

from .store import CallStore, _resolve_path

_F = TypeVar("_F", bound=Callable[..., Any])


class UnexpectedToolCall(Exception):
    pass


def _resolve_exception(type_name: str) -> type[Exception]:
    import builtins

    cls = getattr(builtins, type_name, None)
    if cls is not None and isinstance(cls, type) and issubclass(cls, Exception):
        return cls
    return RuntimeError


@overload
def replay(path_or_fn: _F, *, strict: bool = ...) -> _F: ...
@overload
def replay(
    path_or_fn: str | None = ..., *, strict: bool = ...
) -> Callable[[_F], _F]: ...


def replay(path_or_fn=None, *, strict: bool = True):
    """
    Decorator that replays recorded calls from a JSONL fixture file instead of
    calling the real function.

    Usage::

        @replay                        # auto-named: fixtures/{fn_name}.jsonl
        @replay()                      # same
        @replay("my_fixtures/")        # directory:  my_fixtures/{fn_name}.jsonl
        @replay("path/to/file.jsonl")  # explicit path

    Args:
        path_or_fn: Optional path string, or the decorated function when used bare.
        strict: If True (default), raise UnexpectedToolCall when called more times
            than the fixture contains. If False, fall through to the real function.
    """
    if callable(path_or_fn):
        return _build_replayer(
            path_or_fn, _resolve_path(None, path_or_fn.__name__), strict
        )

    def decorator(fn: _F) -> _F:
        return _build_replayer(fn, _resolve_path(path_or_fn, fn.__name__), strict)

    return decorator


def _build_replayer(fn: _F, path: str, strict: bool) -> _F:
    index = CallStore(path).load_index()
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
