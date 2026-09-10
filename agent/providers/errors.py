"""Exceptions raised while persisting an asset onto the shared volume.

All failures derive from `Error`, so the agent core can catch a single type.
Two families sit under it: `CloneError` (and its subclasses) for repository
checkout failures, and `ArchiveDownloadError` for repository archive failures.
"""


class Error(Exception):
    """Base exception for all asset persistence errors."""


class CloneError(Error):
    """Raised when a repository cannot be checked out onto the shared volume."""


class MissingCredentialsError(CloneError):
    """Raised when a provider is missing the credentials it needs to clone."""


class UnsupportedProviderError(CloneError):
    """Raised when no provider matches a repository URL."""


class ArchiveDownloadError(Error):
    """Raised when a repository archive cannot be persisted onto the shared volume."""
