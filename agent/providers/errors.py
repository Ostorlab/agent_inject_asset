"""Exceptions raised by the repository providers.

All provider failures surface as `CloneError` (or a subclass) so the agent core
catches a single type regardless of forge. Archive download failures surface as
`ArchiveDownloadError`. Every exception here inherits from the shared `Error`
base, so callers can catch all provider-related failures with a single
`except errors.Error` if needed.
"""


class Error(Exception):
    """Base error for this package."""


class CloneError(Error):
    """Raised when a repository cannot be checked out onto the shared volume."""


class MissingCredentialsError(CloneError):
    """Raised when a provider is missing the credentials it needs to clone."""


class UnsupportedProviderError(CloneError):
    """Raised when no provider matches a repository URL."""


class ArchiveDownloadError(Error):
    """Raised when a repository archive cannot be downloaded onto the shared volume."""
