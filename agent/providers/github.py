"""GitHub repository provider."""

import logging
import urllib.parse

from agent.providers import base
from agent.providers import errors
from agent.providers import git

logger = logging.getLogger(__name__)


class GitHubCloner(base.RepositoryCloner):
    """Checks out GitHub-hosted repositories onto the shared scan volume.

    A public repository is cloned anonymously. A private repository is cloned
    using a Personal Access Token supplied via the `github_token` agent arg,
    embedded in the clone URL as `https://oauth2:<token>@github.com/...`.
    """

    def ensure_credentials(self) -> None:
        if not self._token:
            raise errors.MissingCredentialsError(
                "github_token agent arg is required to clone private GitHub repositories"
            )

    def clone(self, ref: base.RepositoryCheckoutRequest, destination: str) -> None:
        if git.is_public_repository(ref.repository_url) is True:
            logger.info("cloning public repository %s", ref.repository_url)
            git.clone_repository(ref.repository_url, ref.commit_hash, destination)
            return

        self.ensure_credentials()
        authenticated_url = self._authenticated_url(ref.repository_url)
        logger.info("cloning private repository %s", ref.repository_url)
        git.clone_repository(authenticated_url, ref.commit_hash, destination)

    def _authenticated_url(self, repository_url: str) -> str:
        parsed = urllib.parse.urlparse(repository_url)
        return parsed._replace(
            netloc=f"oauth2:{self._token}@{parsed.hostname}"
        ).geturl()
