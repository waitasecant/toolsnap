import functools
import inspect
import warnings
from contextlib import contextmanager
from typing import TypeVar, cast

from .models import CallRecord
from .replayer import UnexpectedToolCall, _resolve_exception
from .store import CallStore

_F = TypeVar("_F")


class _CallLog:
    """Accumulated call log for a single wrapped function during a session."""

    def __init__(self, fn_name: str):
        self.fn_name = fn_name
        self.calls: list[dict] = []  # each entry: {args, kwargs, result, error}

    def record(self, args, kwargs, result, error):
        self.calls.append(
            {"args": args, "kwargs": kwargs, "result": result, "error": error}
        )


class SnapSession:
    """
    Context manager that wraps multiple functions for recording or replaying in a
    single session, and exposes assertion helpers after the block exits.

    Usage:
        with SnapSession.snap("fixtures/session.jsonl") as s:
            s.wrap(search)
            agent.run(...)
        s.assert_called("search", times=2)

        with SnapSession.replay("fixtures/session.jsonl") as s:
            s.wrap(search)
            agent.run(...)
        s.assert_called("search")
    """

    def __init__(self, path: str, *, mode: str, strict: bool = True):
        self._path = path
        self._mode = mode  # "snap" or "replay"
        self._strict = strict
        self._store = CallStore(path)
        self._index: dict[str, list[CallRecord]] = {}
        self._logs: dict[str, _CallLog] = {}

    @classmethod
    @contextmanager
    def snap(cls, path: str, *, strict: bool = True):
        session = cls(path, mode="snap", strict=strict)
        yield session

    @classmethod
    @contextmanager
    def replay(cls, path: str, *, strict: bool = True):
        session = cls(path, mode="replay", strict=strict)
        session._index = session._store.load_index()
        yield session

    def wrap(self, fn: _F) -> _F:
        """
        Wrap a function for this session. Returns a new callable; the caller must
        reassign or pass this to the agent. Also patches the function in its own
        module namespace so existing references pick up the wrap automatically.
        """
        fn_name = getattr(fn, "__name__", repr(fn))
        if getattr(fn, "_is_snap_wrapped", False):
            warnings.warn(
                f"{fn_name!r} is already decorated with @snap. "
                "Wrapping it in a SnapSession will double-record in snap mode. "
                "Remove @snap from the function definition when using SnapSession.",
                stacklevel=2,
            )
        log = _CallLog(fn_name)
        self._logs[fn_name] = log

        if self._mode == "snap":
            wrapped = self._make_snap_wrapper(fn, log)
        else:
            call_counts: dict[str, int] = {}
            wrapped = self._make_replay_wrapper(fn, log, call_counts)

        # Patch the function in its own module so agent code using the original
        # name gets the wrapped version.
        module = inspect.getmodule(fn)
        if module is not None:
            setattr(module, fn_name, wrapped)

        return cast(_F, wrapped)

    def _make_snap_wrapper(self, fn, log: _CallLog):
        import time

        if inspect.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args, **kwargs):
                error = None
                result = None
                t0 = time.perf_counter()
                try:
                    result = await fn(*args, **kwargs)
                except Exception as e:
                    error = {"type": type(e).__name__, "message": str(e)}
                    raise
                finally:
                    duration_ms = (time.perf_counter() - t0) * 1000
                    idx = len(log.calls)
                    log.record(list(args), kwargs, result, error)
                    self._store.append(
                        CallRecord(
                            call_index=idx,
                            fn=fn.__name__,
                            args=list(args),
                            kwargs=kwargs,
                            result=result,
                            duration_ms=duration_ms,
                            ts=time.time(),
                            error=error,
                        )
                    )
                return result

            return async_wrapper

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            error = None
            result = None
            t0 = time.perf_counter()
            try:
                result = fn(*args, **kwargs)
            except Exception as e:
                error = {"type": type(e).__name__, "message": str(e)}
                raise
            finally:
                duration_ms = (time.perf_counter() - t0) * 1000
                idx = len(log.calls)
                log.record(list(args), kwargs, result, error)
                self._store.append(
                    CallRecord(
                        call_index=idx,
                        fn=fn.__name__,
                        args=list(args),
                        kwargs=kwargs,
                        result=result,
                        duration_ms=duration_ms,
                        ts=time.time(),
                        error=error,
                    )
                )
            return result

        return wrapper

    def _make_replay_wrapper(self, fn, log: _CallLog, call_counts: dict):
        if inspect.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args, **kwargs):
                idx = call_counts.get(fn.__name__, 0)
                call_counts[fn.__name__] = idx + 1
                records = self._index.get(fn.__name__, [])
                if idx >= len(records):
                    if self._strict:
                        raise UnexpectedToolCall(
                            f"{fn.__name__} called {idx + 1} times but fixture only has "
                            f"{len(records)} record(s)"
                        )
                    result = await fn(*args, **kwargs)
                    log.record(list(args), kwargs, result, None)
                    return result
                record = records[idx]
                log.record(list(args), kwargs, record.result, record.error)
                if record.error:
                    exc_type = _resolve_exception(record.error["type"])
                    raise exc_type(record.error["message"])
                return record.result

            return async_wrapper

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            idx = call_counts.get(fn.__name__, 0)
            call_counts[fn.__name__] = idx + 1
            records = self._index.get(fn.__name__, [])
            if idx >= len(records):
                if self._strict:
                    raise UnexpectedToolCall(
                        f"{fn.__name__} called {idx + 1} times but fixture only has "
                        f"{len(records)} record(s)"
                    )
                result = fn(*args, **kwargs)
                log.record(list(args), kwargs, result, None)
                return result
            record = records[idx]
            log.record(list(args), kwargs, record.result, record.error)
            if record.error:
                exc_type = _resolve_exception(record.error["type"])
                raise exc_type(record.error["message"])
            return record.result

        return wrapper

    # Assertion helpers

    def assert_called(self, fn_name: str, *, times: int | None = None) -> None:
        log = self._logs.get(fn_name)
        actual = len(log.calls) if log else 0
        if times is None:
            if actual == 0:
                raise AssertionError(
                    f'assert_called("{fn_name}") failed\n\n'
                    f"  Expected: at least one call\n"
                    f"  Got: never called"
                )
        else:
            if actual != times:
                raise AssertionError(
                    f'assert_called("{fn_name}", times={times}) failed\n\n'
                    f"  Expected: {times} call(s)\n"
                    f"  Got: {actual} call(s)"
                )

    def assert_not_called(self, fn_name: str) -> None:
        log = self._logs.get(fn_name)
        actual = len(log.calls) if log else 0
        if actual > 0:
            raise AssertionError(
                f'assert_not_called("{fn_name}") failed\n\n'
                f"  Expected: never called\n"
                f"  Got: {actual} call(s)"
            )

    def assert_called_with(
        self, fn_name: str, *, call: int | None = None, **kwargs
    ) -> None:
        log = self._logs.get(fn_name)
        calls = log.calls if log else []
        if not calls:
            raise AssertionError(
                f'assert_called_with("{fn_name}", ...) failed\n\n'
                f"  Expected: at least one call\n"
                f"  Got: never called"
            )

        def _matches_call(c: dict) -> bool:
            for k, v in kwargs.items():
                actual_val = c["kwargs"].get(k)
                if callable(v):
                    if not v(actual_val):
                        return False
                elif actual_val != v:
                    return False
            return True

        if call is not None:
            if call >= len(calls):
                raise AssertionError(
                    f'assert_called_with("{fn_name}", call={call}, ...) failed\n\n'
                    f"  Expected: call index {call} to exist\n"
                    f"  Got: only {len(calls)} call(s)"
                )
            c = calls[call]
            if not _matches_call(c):
                actual_kwargs = ", ".join(f"{k}={v!r}" for k, v in c["kwargs"].items())
                raise AssertionError(
                    f'assert_called_with("{fn_name}", call={call}, '
                    f"{', '.join(f'{k}={v!r}' for k, v in kwargs.items())}) failed\n\n"
                    f"  Call {call}: {actual_kwargs}"
                )
        else:
            lines = []
            for i, c in enumerate(calls):
                match = _matches_call(c)
                actual_kwargs = ", ".join(f"{k}={v!r}" for k, v in c["kwargs"].items())
                marker = "matches" if match else "does not match"
                lines.append(f"    call {i}: {actual_kwargs}  <- {marker}")
                if match:
                    return
            predicate_str = ", ".join(f"{k}={v!r}" for k, v in kwargs.items())
            raise AssertionError(
                f'assert_called_with("{fn_name}", {predicate_str}) failed\n\n'
                f'  Actual calls to "{fn_name}":\n' + "\n".join(lines) + "\n\n"
                "  Expected: at least one call matching the predicate\n"
                "  Got: no matching call"
            )

    def assert_call_order(self, fn_names: list[str]) -> None:
        """Assert the given function names were called in this order (not necessarily consecutive)."""
        timeline: list[str] = []
        # Build a flat timeline using call_index ordering stored in the log
        all_fns = list(self._logs.keys())
        events: list[tuple[int, str]] = []
        for fn_name in all_fns:
            log = self._logs[fn_name]
            for i in range(len(log.calls)):
                events.append((i, fn_name))
        # Sort by call_index then fn_name for stable ordering within same index
        events.sort(key=lambda x: x[0])
        timeline = [fn for _, fn in events if fn in fn_names]

        # Check subsequence
        it = iter(timeline)
        for name in fn_names:
            if not any(t == name for t in it):
                raise AssertionError(
                    f"assert_call_order({fn_names!r}) failed\n\n"
                    f"  Expected order: {fn_names}\n"
                    f"  Actual order in timeline: {timeline}"
                )

    def assert_no_errors(self) -> None:
        for fn_name, log in self._logs.items():
            for i, c in enumerate(log.calls):
                if c["error"]:
                    raise AssertionError(
                        f"assert_no_errors() failed\n\n"
                        f'  "{fn_name}" call {i} raised '
                        f"{c['error']['type']}: {c['error']['message']}"
                    )

    def assert_raised(self, fn_name: str, error_type: str) -> None:
        log = self._logs.get(fn_name)
        calls = log.calls if log else []
        for c in calls:
            if c["error"] and c["error"]["type"] == error_type:
                return
        actual_errors = [c["error"]["type"] for c in calls if c["error"]]
        raise AssertionError(
            f'assert_raised("{fn_name}", "{error_type}") failed\n\n'
            f"  Expected: at least one call raising {error_type}\n"
            f"  Got errors: {actual_errors or 'none'}"
        )
