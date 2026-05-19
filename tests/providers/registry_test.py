"""Unittests for the repository provider registry."""

import pytest

from providers import bitbucket
from providers import errors
from providers import github
from providers import gitlab
from providers import registry


def testClonerForUrl_whenGitHubUrl_returnsGitHubCloner() -> None:
    """A github.com URL resolves to the GitHub provider."""
    cloner = registry.cloner_for_url("https://github.com/owner/repo")

    assert isinstance(cloner, github.GitHubCloner)


def testClonerForUrl_whenGitLabUrl_returnsGitLabCloner() -> None:
    """A gitlab.com URL resolves to the GitLab provider."""
    cloner = registry.cloner_for_url("https://gitlab.com/owner/repo")

    assert isinstance(cloner, gitlab.GitLabCloner)


def testClonerForUrl_whenBitbucketUrl_returnsBitbucketCloner() -> None:
    """A bitbucket.org URL resolves to the Bitbucket provider."""
    cloner = registry.cloner_for_url("https://bitbucket.org/owner/repo")

    assert isinstance(cloner, bitbucket.BitbucketCloner)


def testClonerForUrl_whenUnknownHost_raisesUnsupportedProviderError() -> None:
    """A URL whose host matches no provider raises an error."""
    with pytest.raises(errors.UnsupportedProviderError):
        registry.cloner_for_url("https://example.com/owner/repo")
