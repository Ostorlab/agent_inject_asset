"""Shared pytest fixtures for the inject asset test suite."""

from collections.abc import Callable
from typing import Any

import pytest
from ostorlab.agent.message import message

_REPOSITORY_ARCHIVE_SELECTOR = "v3.asset.file.repository_archive"


class _MockMessage:
    """A parsed message stand-in exposing the fields the agent reads."""

    def __init__(self, selector: str, raw: bytes, data: dict[str, Any]) -> None:
        self.selector = selector
        self.raw = raw
        self.data = data


class _MockFromRaw:
    """A `message.Message.from_raw` stand-in returning `data` for the repository archive selector."""

    def __init__(
        self, original: Callable[[str, bytes], Any], data: dict[str, Any]
    ) -> None:
        self._original = original
        self._data = data

    def __call__(self, selector: str, raw: bytes) -> Any:
        if selector == _REPOSITORY_ARCHIVE_SELECTOR:
            return _MockMessage(selector, raw, self._data)

        return self._original(selector, raw)


@pytest.fixture
def mock_repository_archive_message(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[dict[str, Any]], None]:
    """Return a setter that makes `message.Message.from_raw` return `data` for the repository archive selector.

    The real `v3.asset.file.repository_archive` proto is not yet published in the
    `ostorlab` package, so the repository archive path has no real-parsing fallback.
    """
    original_from_raw = message.Message.from_raw

    def _set(data: dict[str, Any]) -> None:
        monkeypatch.setattr(
            message.Message, "from_raw", _MockFromRaw(original_from_raw, data)
        )

    return _set
