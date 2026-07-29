"""Shared pytest fixtures for the inject asset test suite."""

from collections.abc import Callable
from typing import Any

import pytest
from ostorlab.agent.message import message

_REPOSITORY_ARCHIVE_SELECTOR = "v3.asset.file.repository_archive"


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
        def mock_from_raw(selector: str, raw: bytes) -> Any:
            if selector == _REPOSITORY_ARCHIVE_SELECTOR:

                class _MockMessage:
                    def __init__(self) -> None:
                        self.data = data
                        self.selector = selector
                        self.raw = raw

                return _MockMessage()

            return original_from_raw(selector, raw)

        monkeypatch.setattr(message.Message, "from_raw", mock_from_raw)

    return _set
