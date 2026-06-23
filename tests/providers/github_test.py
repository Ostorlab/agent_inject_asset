"""Tests for the GitHub provider clone method."""

from unittest.mock import patch

from agent.providers import github as github_provider
from agent.providers import base


def testGitHubCloner_whenCloneWithoutToken_shouldReturnOriginalUrl() -> None:
    """Clone without a token should use the original URL unchanged."""
    provider = github_provider.GitHubCloner()
    repo_url = "https://github.com/org/repo"
    ref = base.RepositoryCheckoutRequest(
        repository_url=repo_url, commit_hash="123", token=None
    )

    with patch("agent.providers.git.clone_repository") as mock_clone:
        mock_clone.return_value = None
        provider.clone(ref, "/tmp/dest")
        mock_clone.assert_called_once_with(repo_url, "123", "/tmp/dest")


def testGitHubCloner_whenCloneWithToken_shouldInjectTokenPrefix() -> None:
    """Clone with a token should inject 'x-access-token:' prefix into the GitHub URL."""
    provider = github_provider.GitHubCloner()
    repo_url = "https://github.com/org/repo"
    token = "secret-token-value"
    ref = base.RepositoryCheckoutRequest(
        repository_url=repo_url, commit_hash="123", token=token
    )
    expected_url = f"https://x-access-token:{token}@github.com/org/repo"

    with patch("agent.providers.git.clone_repository") as mock_clone:
        mock_clone.return_value = None
        provider.clone(ref, "/tmp/dest")
        mock_clone.assert_called_once_with(expected_url, "123", "/tmp/dest")
