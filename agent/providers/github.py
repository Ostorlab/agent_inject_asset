"""GitHub repository provider."""

import logging
import urllib.parse

from agent.providers import base
from agent.providers import git

logger = logging.getLogger(__name__)


class GitHubCloner(base.RepositoryCloner):
    """Checks out GitHub-hosted repositories onto the shared scan volume."""

    PROVIDER_NAME = "GITHUB"

    def clone(self, ref: base.RepositoryCheckoutRequest, destination: str) -> None:
        url = ref.repository_url
        if ref.token is not None:
            url = git.inject_token_into_url(url, ref.token, "x-access-token")

        redacted = git.redact_url(url)
        logger.info("cloning GitHub repository %s", redacted)
        git.clone_repository(url, ref.commit_hash, destination)
