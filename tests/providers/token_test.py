"""Tests for token provider."""

from unittest import mock

import requests

from agent.providers import token


def testFetchPlatformToken_whenApiSucceeds_returnsToken() -> None:
    """Test fetching a token successfully."""
    api_url = "https://api.ostorlab.co/apis/robot_graphql"
    api_key = "dummy_key"
    git_provider = "GITHUB"

    mock_response = mock.Mock()
    mock_response.json.return_value = {
        "data": {"generateGitPlatformToken": {"token": "ghp_12345"}}
    }
    mock_response.raise_for_status = mock.Mock()

    with mock.patch("requests.post", return_value=mock_response) as mock_post:
        fetched_token = token.fetch_platform_token(api_url, api_key, git_provider)

        assert fetched_token == "ghp_12345"
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert kwargs["headers"]["X-API-KEY"] == "dummy_key"
        assert kwargs["json"]["variables"]["gitProvider"] == "GITHUB"


def testFetchPlatformToken_whenApiFails_returnsNone() -> None:
    """Test fetching a token when the API returns an error."""
    api_url = "https://api.ostorlab.co/apis/robot_graphql"
    api_key = "dummy_key"
    git_provider = "GITHUB"

    mock_response = mock.Mock()
    mock_response.raise_for_status.side_effect = requests.RequestException("API Error")

    with mock.patch("requests.post", return_value=mock_response):
        fetched_token = token.fetch_platform_token(api_url, api_key, git_provider)

        assert fetched_token is None


def testFetchPlatformToken_whenGraphqlErrors_returnsNone() -> None:
    """Test fetching a token when GraphQL returns errors."""
    api_url = "https://api.ostorlab.co/apis/robot_graphql"
    api_key = "dummy_key"
    git_provider = "GITHUB"

    mock_response = mock.Mock()
    mock_response.json.return_value = {"errors": [{"message": "Invalid provider"}]}

    with mock.patch("requests.post", return_value=mock_response):
        fetched_token = token.fetch_platform_token(api_url, api_key, git_provider)

        assert fetched_token is None
