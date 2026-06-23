"""Tests for the GitLab provider clone method."""

from unittest.mock import patch

from agent.providers.gitlab import GitLabCloner
from agent.providers.base import RepositoryCheckoutRequest


def testCloneWithoutToken_returnsOriginalUrl() -> None:
    """Clone without a token should use the original URL unchanged."""
    provider = GitLabCloner()
    repo_url = "https://gitlab.com/org/repo"
    ref = RepositoryCheckoutRequest(
        repository_url=repo_url, commit_hash="123", token=None
    )

    with patch("agent.providers.git.clone_repository") as mock_clone:
        mock_clone.return_value = None
        provider.clone(ref, "/tmp/dest")
        mock_clone.assert_called_once_with(repo_url, "123", "/tmp/dest")


def testCloneWithToken_injectsTokenPrefix() -> None:
    """Clone with a token should inject 'oauth2:' prefix into the GitLab URL."""
    provider = GitLabCloner()
    repo_url = "https://gitlab.com/org/repo"
    token = "secret-token-value"
    ref = RepositoryCheckoutRequest(
        repository_url=repo_url, commit_hash="123", token=token
    )
    expected_url = f"https://oauth2:{token}@gitlab.com/org/repo"

    with patch("agent.providers.git.clone_repository") as mock_clone:
        mock_clone.return_value = None
        provider.clone(ref, "/tmp/dest")
        mock_clone.assert_called_once_with(expected_url, "123", "/tmp/dest")
