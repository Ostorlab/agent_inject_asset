"""Base contract every repository provider implementation must satisfy."""

import abc
import dataclasses


@dataclasses.dataclass
class RepositoryCheckoutRequest:
    """A repository checkout request parsed from a `v3.asset.repository` asset."""

    repository_url: str
    commit_hash: str


class RepositoryCloner(abc.ABC):
    """Contract for repository checkout providers."""

    def __init__(self, token: str | None = None) -> None:
        self._token = token

    @abc.abstractmethod
    def ensure_credentials(self) -> None:
        """Validate that this provider has the credentials it needs.

        Invoked by `clone()` only for a private repository. Raises
        `MissingCredentialsError` when authentication is required but no
        token is configured.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def clone(self, ref: RepositoryCheckoutRequest, destination: str) -> None:
        """Check out `ref` into `destination`, detecting public vs private.

        A public repository is cloned anonymously; a private one falls back to
        authenticated cloning. Raises `CloneError` on any failure.
        """
        raise NotImplementedError
