"""Tests for the GitLab provider clone method."""

from unittest.mock import patch

from agent.providers import gitlab as gitlab_provider
from agent.providers import base


def testGitLabCloner_whenCloneWithoutToken_shouldReturnOriginalUrl() -> None:
    """Clone without a token should use the original URL unchanged."""
    provider = gitlab_provider.GitLabCloner()
    repo_url = "https://gitlab.com/org/repo"
    ref = base.RepositoryCheckoutRequest(
        repository_url=repo_url, commit_hash="123", token=None
    )

    with patch("agent.providers.git.clone_repository") as mock_clone:
        mock_clone.return_value = None
        provider.clone(ref, "/tmp/dest")
        mock_clone.assert_called_once_with(repo_url, "123", "/tmp/dest")


def testGitLabCloner_whenCloneWithToken_shouldInjectTokenPrefix() -> None:
    """Clone with a token should inject 'oauth2:' prefix into the GitLab URL."""
    provider = gitlab_provider.GitLabCloner()
    repo_url = "https://gitlab.com/org/repo"
    token = "secret-token-value"
    ref = base.RepositoryCheckoutRequest(
        repository_url=repo_url, commit_hash="123", token=token
    )
    expected_url = f"https://oauth2:{token}@gitlab.com/org/repo"

    with patch("agent.providers.git.clone_repository") as mock_clone:
        mock_clone.return_value = None
        provider.clone(ref, "/tmp/dest")
        mock_clone.assert_called_once_with(expected_url, "123", "/tmp/dest")
