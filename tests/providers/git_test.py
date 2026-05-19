"""Unittests for the git helper."""

import subprocess

import pytest

from agent.providers import errors
from agent.providers import git


def testIsPublicRepository_whenLsRemoteSucceeds_returnsTrue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A repository reachable without authentication reports as public."""
    monkeypatch.setattr(
        git.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, b"", b""),
    )

    is_public = git.is_public_repository("https://github.com/owner/repo")

    assert is_public is True


def testIsPublicRepository_whenLsRemoteFails_returnsFalse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A repository that needs authentication reports as not public."""
    monkeypatch.setattr(
        git.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, 128, b"", b"denied"),
    )

    is_public = git.is_public_repository("https://github.com/owner/repo")

    assert is_public is False


def testCloneRepository_whenGitExitsNonZero_raisesCloneError(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failing git command surfaces as a CloneError."""
    monkeypatch.setattr(
        git.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, 128, b"", b"boom"),
    )

    with pytest.raises(errors.CloneError):
        git.clone_repository("https://github.com/owner/repo", "abc123", "/code")
