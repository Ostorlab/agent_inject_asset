"""Exceptions raised by the repository providers.

All provider failures surface as `CloneError` (or a subclass) so the agent core
catches a single type regardless of forge.
"""


class CloneError(Exception):
    """Raised when a repository cannot be checked out onto the shared volume."""


class MissingCredentialsError(CloneError):
    """Raised when a provider is missing the credentials it needs to clone."""


class UnsupportedProviderError(CloneError):
    """Raised when no provider matches a repository URL."""
