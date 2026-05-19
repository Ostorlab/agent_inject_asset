"""GitHub repository provider."""

import logging

from agent.providers import base
from agent.providers import errors
from agent.providers import git

logger = logging.getLogger(__name__)


class GitHubCloner(base.RepositoryCloner):
    """Checks out GitHub-hosted repositories onto the shared scan volume.

    A public repository is cloned anonymously. Authenticated cloning of private
    repositories is finalised when this provider is built out — see
    REPOSITORY_PROVIDER_DESIGN.md.
    """

    def ensure_credentials(self) -> None:
        # TODO(amat-osto): validate GitHub credentials once the agent args are defined.
        return None

    def clone(self, ref: base.RepositoryCheckoutRequest, destination: str) -> None:
        if git.is_public_repository(ref.repository_url) is True:
            logger.info("cloning public repository %s", ref.repository_url)
            git.clone_repository(ref.repository_url, ref.commit_hash, destination)
            return

        self.ensure_credentials()
        raise errors.CloneError("GitHub authenticated cloning is not yet implemented")
