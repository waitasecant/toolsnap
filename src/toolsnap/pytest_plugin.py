from __future__ import annotations

import inspect
import sys
import warnings
from pathlib import Path
from typing import Generator

import pytest

from .session import SnapSession
from .store import CallStore


# command-line options
def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("toolsnap", "toolsnap fixture management")
    group.addoption(
        "--toolsnap-record",
        action="store_true",
        default=False,
        help="Re-record all toolsnap fixtures (snap mode). Default: replay mode.",
    )
    group.addoption(
        "--toolsnap-strict",
        default="true",
        metavar="BOOL",
        help=(
            "Raise UnexpectedToolCall on unexpected calls. "
            'Set to "false" to fall through to the real function. Default: true.'
        ),
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "toolsnap_fixture(path): path to the .jsonl fixture file for this test",
    )


# staleness detection
def _find_fn_in_modules(name: str):
    """Return the unique callable named *name* across all loaded modules, or None.

    Deduplicates by object identity so a function imported in multiple modules
    is counted once, not once per importing module.
    """
    seen: set[int] = set()
    candidates = []
    for module in list(sys.modules.values()):
        if module is None:
            continue
        try:
            obj = getattr(module, name, None)
        except Exception:
            continue
        if obj is None:
            continue
        try:
            if callable(obj) and getattr(obj, "__name__", None) == name:
                oid = id(obj)
                if oid not in seen:
                    seen.add(oid)
                    candidates.append(obj)
        except Exception:
            continue
    return candidates[0] if len(candidates) == 1 else None


def _check_stale_fixtures(rootdir: Path) -> None:
    """Scan ``fixtures/`` dirs under *rootdir* and warn about stale fixtures.

    A fixture is stale when the kwarg keys it recorded are no longer present in
    the corresponding function's signature (and the function doesn't accept
    **kwargs).
    """
    for fixture_file in rootdir.rglob("fixtures/*.jsonl"):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            records = CallStore(fixture_file).load()
        if not records:
            continue

        for fn_name in {r.fn for r in records}:
            fn = _find_fn_in_modules(fn_name)
            if fn is None:
                continue

            fixture_kwargs: set[str] = {
                k for r in records if r.fn == fn_name for k in r.kwargs
            }
            if not fixture_kwargs:
                continue  # all positional — nothing to check

            try:
                sig = inspect.signature(fn)
            except (ValueError, TypeError):
                continue

            if any(
                p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
            ):
                continue  # **kwargs accepts anything

            unknown = fixture_kwargs - set(sig.parameters)
            if unknown:
                warnings.warn(
                    f"fixture {fixture_file.name} may be stale: "
                    f"{fn_name}() signature changed "
                    f"(fixture uses unknown kwargs: {sorted(unknown)})",
                    UserWarning,
                    stacklevel=1,
                )


def pytest_collection_finish(session: pytest.Session) -> None:
    _check_stale_fixtures(session.config.rootpath)


# toolsnap_session fixture
@pytest.fixture
def toolsnap_session(
    request: pytest.FixtureRequest,
) -> Generator[SnapSession, None, None]:
    """Provide a :class:`SnapSession` configured for replay or record mode.

    The fixture path is read from ``@pytest.mark.toolsnap_fixture("path")``.
    When the marker is absent the path defaults to
    ``fixtures/{test_name}.jsonl``.

    CLI options
    -----------
    ``--toolsnap-record``
        Switch from replay to snap mode; the fixture file is cleared and
        re-recorded.
    ``--toolsnap-strict=false``
        Allow unexpected calls to fall through to the real function instead of
        raising :class:`~toolsnap.UnexpectedToolCall`.
    """
    marker = request.node.get_closest_marker("toolsnap_fixture")
    path: str = (
        marker.args[0]
        if marker and marker.args
        else f"fixtures/{request.node.name}.jsonl"
    )

    record: bool = request.config.getoption("--toolsnap-record", default=False)
    strict: bool = (
        str(request.config.getoption("--toolsnap-strict", default="true")).lower()
        != "false"
    )

    mode = "snap" if record else "replay"
    snap_session = SnapSession(path, mode=mode, strict=strict)

    if mode == "snap":
        snap_session._store.clear()  # fresh fixture on every record run
    else:
        snap_session._index = snap_session._store.load_index()

    yield snap_session
