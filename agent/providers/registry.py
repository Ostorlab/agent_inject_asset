"""Maps a repository URL to the forge provider that owns it.

Host-to-provider matching lives only here; the providers themselves are
unaware of how they are selected.
"""

import urllib.parse

from agent.providers import base
from agent.providers import bitbucket
from agent.providers import errors
from agent.providers import github
from agent.providers import gitlab

_PROVIDERS_BY_HOST: dict[str, type[base.RepositoryCloner]] = {
    "github.com": github.GitHubCloner,
    "gitlab.com": gitlab.GitLabCloner,
    "bitbucket.org": bitbucket.BitbucketCloner,
}


def cloner_for_url(repository_url: str) -> base.RepositoryCloner:
    """Return a repository cloner for `repository_url`, matched by host.

    Raises `UnsupportedProviderError` when no provider matches the host.
    """
    host = urllib.parse.urlparse(repository_url).hostname
    provider_class = _PROVIDERS_BY_HOST.get((host or "").lower())
    if provider_class is None:
        raise errors.UnsupportedProviderError(
            f"no repository provider for URL: {repository_url}"
        )
    return provider_class()
