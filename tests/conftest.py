import pytest


@pytest.fixture
def tmp_fixture(tmp_path):
    return str(tmp_path / "calls.jsonl")
