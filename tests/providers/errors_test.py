"""Unittests for the provider error hierarchy."""

from agent.providers import errors


def testErrorHierarchy_whenAnyProviderError_sharesSingleBase() -> None:
    """Ensures every provider failure can be caught through one base class."""
    error_types = [
        errors.CloneError,
        errors.MissingCredentialsError,
        errors.UnsupportedProviderError,
        errors.ArchiveDownloadError,
    ]

    are_subclasses = [issubclass(e, errors.Error) for e in error_types]

    assert all(are_subclasses) is True


def testErrorHierarchy_whenArchiveDownloadError_isNotACloneError() -> None:
    """Ensures archive failures stay distinct from clone failures."""
    archive_error = errors.ArchiveDownloadError("boom")

    is_clone_error = isinstance(archive_error, errors.CloneError)

    assert is_clone_error is False
