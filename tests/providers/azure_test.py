"""Tests for the Azure provider clone method."""

from unittest.mock import patch

from agent.providers.azure import AzureCloner
from agent.providers.base import RepositoryCheckoutRequest


def testCloneWithoutToken_returnsOriginalUrl() -> None:
    """Clone without a token should use the original URL unchanged."""
    provider = AzureCloner()
    repo_url = "https://dev.azure.com/org/project/_git/repo"
    ref = RepositoryCheckoutRequest(
        repository_url=repo_url, commit_hash="123", token=None
    )

    with patch("agent.providers.git.clone_repository") as mock_clone:
        mock_clone.return_value = None
        provider.clone(ref, "/tmp/dest")
        mock_clone.assert_called_once_with(repo_url, "123", "/tmp/dest")


def testCloneWithToken_injectsTokenPrefix() -> None:
    """Clone with a token should inject 'token:' prefix into the Azure URL."""
    provider = AzureCloner()
    repo_url = "https://dev.azure.com/org/project/_git/repo"
    token = "secret-token-value"
    ref = RepositoryCheckoutRequest(
        repository_url=repo_url, commit_hash="123", token=token
    )
    expected_url = f"https://token:{token}@dev.azure.com/org/project/_git/repo"

    with patch("agent.providers.git.clone_repository") as mock_clone:
        mock_clone.return_value = None
        provider.clone(ref, "/tmp/dest")
        mock_clone.assert_called_once_with(expected_url, "123", "/tmp/dest")


def testCloneWithEmptyToken_preservesUrlPath() -> None:
    """Token injection should preserve the full URL path structure."""
    provider = AzureCloner()
    repo_url = "https://dev.azure.com/org/project/_git/repo"
    token = "my-token"
    ref = RepositoryCheckoutRequest(
        repository_url=repo_url, commit_hash="123", token=token
    )

    with patch("agent.providers.git.clone_repository") as mock_clone:
        mock_clone.return_value = None
        provider.clone(ref, "/tmp/dest")
        mock_clone.assert_called_once()
        call_args = mock_clone.call_args[0]
        assert "org/project/_git/repo" in call_args[0]
