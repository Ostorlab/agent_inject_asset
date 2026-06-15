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
        if ref.token:
            parsed = urllib.parse.urlparse(url)
            netloc = f"x-access-token:{ref.token}@{parsed.hostname}"
            if parsed.port:
                netloc += f":{parsed.port}"
            url = urllib.parse.urlunparse(parsed._replace(netloc=netloc))
            
        redacted = git.redact_url(url)
        logger.info("cloning GitHub repository %s", redacted)
        git.clone_repository(url, ref.commit_hash, destination)
