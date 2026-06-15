"""Maps a repository URL to the forge provider that owns it.

Host-to-provider matching lives only here; the providers themselves are
unaware of how they are selected.
"""

import urllib.parse
from typing import Optional

from agent.providers import base
from agent.providers import bitbucket
from agent.providers import errors
from agent.providers import git
from agent.providers import github
from agent.providers import gitlab
from agent.providers import azure

_PROVIDERS_BY_HOST: dict[str, type[base.RepositoryCloner]] = {
    "github.com": github.GitHubCloner,
    "gitlab.com": gitlab.GitLabCloner,
    "bitbucket.org": bitbucket.BitbucketCloner,
    "dev.azure.com": azure.AzureCloner,
}

_PROVIDERS_BY_NAME: dict[str, type[base.RepositoryCloner]] = {
    "GITHUB": github.GitHubCloner,
    "GITLAB": gitlab.GitLabCloner,
    "BITBUCKET": bitbucket.BitbucketCloner,
    "AZURE": azure.AzureCloner,
    "GIT": git.GitCloner,
}

def cloner_for_url(repository_url: str, provider: Optional[str] = None) -> base.RepositoryCloner:
    """Return a repository cloner for `repository_url`, matched by name or host.

    Raises `UnsupportedProviderError` when no provider matches.
    """
    if provider and provider in _PROVIDERS_BY_NAME:
        return _PROVIDERS_BY_NAME[provider]()

    host = urllib.parse.urlparse(repository_url).hostname
    provider_class = _PROVIDERS_BY_HOST.get((host or "").lower())
    if provider_class is None:
        raise errors.UnsupportedProviderError(
            f"no repository provider for URL: {git.redact_url(repository_url)}"
        )
    return provider_class()
