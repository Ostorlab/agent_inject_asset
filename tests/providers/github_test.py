"""Unittests for the GitHub repository provider."""

import pytest

from agent.providers import base
from agent.providers import errors
from agent.providers import git
from agent.providers import github


def testClone_whenRepositoryIsPublic_clonesAnonymously(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A public repository is cloned without credentials."""
    clone_calls: list[tuple[str, str, str]] = []
    monkeypatch.setattr(git, "is_public_repository", lambda repository_url: True)
    monkeypatch.setattr(
        git,
        "clone_repository",
        lambda repository_url, commit_hash, destination: clone_calls.append(
            (repository_url, commit_hash, destination)
        ),
    )
    cloner = github.GitHubCloner()
    ref = base.RepositoryCheckoutRequest("https://github.com/owner/repo", "abc123")

    cloner.clone(ref, "/code")

    assert clone_calls == [("https://github.com/owner/repo", "abc123", "/code")]


def testClone_whenRepositoryIsPrivate_raisesCloneError(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A private repository raises until authenticated cloning is implemented."""
    monkeypatch.setattr(git, "is_public_repository", lambda repository_url: False)
    cloner = github.GitHubCloner()
    ref = base.RepositoryCheckoutRequest("https://github.com/owner/repo", "abc123")

    with pytest.raises(errors.CloneError):
        cloner.clone(ref, "/code")
