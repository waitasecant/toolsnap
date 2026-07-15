import warnings
from typing import Any

_TRUNCATED_MARKER = "_toolsnap_truncated"


def auto_serialize(result: Any, max_result_bytes: int) -> Any:
    """Make *result* JSON-serializable, truncating if it exceeds *max_result_bytes*.

    Tries in order:
    1. Direct JSON serialization (pass-through if already serializable)
    2. Pydantic ``model_dump()``
    3. ``dataclasses.asdict()``
    4. ``__dict__``
    5. ``str()`` with a warning

    If the serialized size exceeds *max_result_bytes*, stores a hash + size marker
    instead of the full result and emits a warning.
    """
    import dataclasses
    import hashlib
    import json

    if result is None:
        return None

    def _check_size(candidate: Any) -> Any:
        """Return candidate if within size limit, else a truncation marker."""
        try:
            encoded = json.dumps(candidate).encode()
        except (TypeError, ValueError):
            return None  # not serializable even after conversion
        if len(encoded) <= max_result_bytes:
            return candidate
        digest = hashlib.sha256(encoded).hexdigest()[:16]
        warnings.warn(
            f"Result ({len(encoded):,} bytes) exceeds max_result_bytes={max_result_bytes:,}; "
            f"storing truncation marker (sha256={digest}). "
            "Replay will return the marker. Use @snap(max_result_bytes=...) to raise the limit.",
            stacklevel=4,
        )
        return {_TRUNCATED_MARKER: True, "sha256": digest, "size_bytes": len(encoded)}

    # 1. Already JSON-serializable?
    try:
        import json as _json

        _json.dumps(result)
        return _check_size(result)
    except (TypeError, ValueError):
        pass

    # 2. Pydantic model
    if hasattr(result, "model_dump"):
        try:
            candidate = result.model_dump()
            out = _check_size(candidate)
            if out is not None:
                return out
        except Exception:
            pass

    # 3. dataclass
    if dataclasses.is_dataclass(result) and not isinstance(result, type):
        try:
            candidate = dataclasses.asdict(result)
            out = _check_size(candidate)
            if out is not None:
                return out
        except Exception:
            pass

    # 4. __dict__ (skip if empty — empty __dict__ carries no useful data)
    if hasattr(result, "__dict__") and result.__dict__:
        out = _check_size(result.__dict__)
        if out is not None:
            return out

    # 5. str() fallback
    warnings.warn(
        f"Could not auto-serialize result of type {type(result).__name__!r}; "
        "falling back to str(). Use @snap(serializer=...) for custom serialization.",
        stacklevel=4,
    )
    return _check_size(str(result))
