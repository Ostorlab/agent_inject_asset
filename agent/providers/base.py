"""Base contract every repository provider implementation must satisfy."""

import abc
import dataclasses
from typing import Optional


@dataclasses.dataclass
class RepositoryCheckoutRequest:
    """A repository checkout request parsed from a `v3.asset.repository` asset."""

    repository_url: str
    commit_hash: str
    provider: str | None = None
    token: str | None = None


class RepositoryCloner(abc.ABC):
    """Contract for repository checkout providers."""

    PROVIDER_NAME: Optional[str] = None

    @abc.abstractmethod
    def clone(self, ref: RepositoryCheckoutRequest, destination: str) -> None:
        """Check out `ref` into `destination`.

        Raises `CloneError` on any failure.
        """
        raise NotImplementedError
