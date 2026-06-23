"""Bitbucket repository provider."""

import logging

from agent.providers import base
from agent.providers import git

logger = logging.getLogger(__name__)


class BitbucketCloner(base.RepositoryCloner):
    """Checks out Bitbucket-hosted repositories onto the shared scan volume."""

    PROVIDER_NAME = "BITBUCKET"

    def clone(self, ref: base.RepositoryCheckoutRequest, destination: str) -> None:
        url = ref.repository_url
        if ref.token is not None:
            url = git.inject_token_into_url(url, ref.token, "x-token-auth")

        redacted = git.redact_url(url)
        logger.info("cloning Bitbucket repository %s", redacted)
        git.clone_repository(url, ref.commit_hash, destination)
