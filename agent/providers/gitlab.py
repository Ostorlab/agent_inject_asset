"""GitLab repository provider."""

import logging
import urllib.parse

from agent.providers import base
from agent.providers import git

logger = logging.getLogger(__name__)


class GitLabCloner(base.RepositoryCloner):
    """Checks out GitLab-hosted repositories onto the shared scan volume."""

    PROVIDER_NAME = "GITLAB"

    def clone(self, ref: base.RepositoryCheckoutRequest, destination: str) -> None:
        url = ref.repository_url
        if ref.token is not None:
            parsed = urllib.parse.urlparse(url)
            netloc = f"oauth2:{ref.token}@{parsed.hostname}"
            if parsed.port is not None:
                netloc += f":{parsed.port}"
            url = urllib.parse.urlunparse(parsed._replace(netloc=netloc))

        redacted = git.redact_url(url)
        logger.info("cloning GitLab repository %s", redacted)
        git.clone_repository(url, ref.commit_hash, destination)
