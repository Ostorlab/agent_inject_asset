"""Bitbucket repository provider."""

import logging
import urllib.parse

from agent.providers import base
from agent.providers import git

logger = logging.getLogger(__name__)


class BitbucketCloner(base.RepositoryCloner):
    """Checks out Bitbucket-hosted repositories onto the shared scan volume."""

    PROVIDER_NAME = "BITBUCKET"

    def clone(self, ref: base.RepositoryCheckoutRequest, destination: str) -> None:
        url = ref.repository_url
        if ref.token is not None:
            parsed = urllib.parse.urlparse(url)
            netloc = f"x-token-auth:{ref.token}@{parsed.hostname}"
            if parsed.port is not None:
                netloc += f":{parsed.port}"
            url = urllib.parse.urlunparse(parsed._replace(netloc=netloc))

        redacted = git.redact_url(url)
        logger.info("cloning Bitbucket repository %s", redacted)
        git.clone_repository(url, ref.commit_hash, destination)
