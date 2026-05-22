"""Unittests for the GitHub repository provider."""

import pathlib
import subprocess

import pytest

from agent.providers import base, errors, git, github


@pytest.fixture()
def local_git_repo(tmp_path: pathlib.Path) -> tuple[pathlib.Path, str]:
    """Create a minimal local git repo and return (repo_path, commit_hash)."""
    repo = tmp_path / "source"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "test@test.com"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.name", "Test"],
        check=True,
        capture_output=True,
    )
    (repo / "README.md").write_text("hello")
    subprocess.run(
        ["git", "-C", str(repo), "add", "."], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "init"],
        check=True,
        capture_output=True,
    )
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return repo, result.stdout.strip()


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


def testClone_whenRepositoryIsPrivateAndNoToken_raisesCloneError(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A private repository with no token raises MissingCredentialsError."""
    monkeypatch.setattr(git, "is_public_repository", lambda repository_url: False)
    cloner = github.GitHubCloner()
    ref = base.RepositoryCheckoutRequest("https://github.com/owner/repo", "abc123")

    with pytest.raises(errors.MissingCredentialsError):
        cloner.clone(ref, "/code")


def testClone_whenRepositoryIsPrivateAndTokenIsProvided_clonesWithAuthenticatedUrl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A private repository is cloned via an authenticated URL when a token is set."""
    clone_calls: list[tuple[str, str, str]] = []
    monkeypatch.setattr(git, "is_public_repository", lambda repository_url: False)
    monkeypatch.setattr(
        git,
        "clone_repository",
        lambda repository_url, commit_hash, destination: clone_calls.append(
            (repository_url, commit_hash, destination)
        ),
    )
    cloner = github.GitHubCloner(token="ghp_test_token")
    ref = base.RepositoryCheckoutRequest("https://github.com/owner/repo", "abc123")

    cloner.clone(ref, "/code")

    assert clone_calls == [
        ("https://oauth2:ghp_test_token@github.com/owner/repo", "abc123", "/code")
    ]


def testClone_withRealLocalRepository_filesArePresentInDestination(
    tmp_path: pathlib.Path,
    local_git_repo: tuple[pathlib.Path, str],
) -> None:
    """End-to-end: clone actually lands files in the destination directory."""
    repo_path, commit_hash = local_git_repo
    destination = str(tmp_path / "cloned")
    cloner = github.GitHubCloner()
    ref = base.RepositoryCheckoutRequest(
        repository_url=str(repo_path),
        commit_hash=commit_hash,
    )

    cloner.clone(ref, destination)

    assert pathlib.Path(destination, "README.md").exists()
