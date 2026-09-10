"""Unittests for the repository archive module."""

import io
import pathlib
import tarfile
import zipfile

import py7zr
import pytest
import requests

from agent import repository_archive
from agent.providers import errors as provider_errors


def _build_zip(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zip_file:
        for name, content in files.items():
            zip_file.writestr(name, content)
    return buffer.getvalue()


def _build_tar_gz(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar_file:
        for name, content in files.items():
            payload = content.encode("utf-8")
            info = tarfile.TarInfo(name=name)
            info.size = len(payload)
            tar_file.addfile(info, io.BytesIO(payload))
    return buffer.getvalue()


def _build_7z(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with py7zr.SevenZipFile(buffer, mode="w") as sz_file:
        for name, content in files.items():
            sz_file.writestr(content, name)
    return buffer.getvalue()


class _FakeResponse:
    def __init__(self, content: bytes) -> None:
        self._content = content

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    def iter_content(self, chunk_size: int) -> "list[bytes]":
        return [
            self._content[i : i + chunk_size]
            for i in range(0, len(self._content), chunk_size)
        ]


def testExtractContent_whenZipArchive_extractsFilesIntoDestination(
    tmp_path: pathlib.Path,
) -> None:
    """Ensures a zip archive is extracted into the destination directory."""
    content = _build_zip({"src/main.py": "print('hello')", "README.md": "# repo"})

    repository_archive.extract_content(content, str(tmp_path))

    assert (tmp_path / "src" / "main.py").read_text() == "print('hello')"
    assert (tmp_path / "README.md").read_text() == "# repo"


def testExtractContent_whenTarGzArchive_extractsFilesIntoDestination(
    tmp_path: pathlib.Path,
) -> None:
    """Ensures a gzip-compressed tar archive is extracted into the destination."""
    content = _build_tar_gz({"src/main.py": "print('hello')"})

    repository_archive.extract_content(content, str(tmp_path))

    assert (tmp_path / "src" / "main.py").read_text() == "print('hello')"


def testExtractContent_when7zArchive_extractsFilesIntoDestination(
    tmp_path: pathlib.Path,
) -> None:
    """Ensures a 7z archive is extracted into the destination directory."""
    content = _build_7z({"src/main.py": "print('hello')"})

    repository_archive.extract_content(content, str(tmp_path))

    assert (tmp_path / "src" / "main.py").read_text() == "print('hello')"


def testExtractContent_whenFormatIsUnsupported_raisesArchiveDownloadError(
    tmp_path: pathlib.Path,
) -> None:
    """Ensures content that matches no known archive signature is rejected."""
    content = b"this is definitely not an archive" * 20

    with pytest.raises(provider_errors.ArchiveDownloadError):
        repository_archive.extract_content(content, str(tmp_path))


def testExtractContent_whenFormatIsUnsupported_leavesDestinationEmpty(
    tmp_path: pathlib.Path,
) -> None:
    """Ensures a failed extraction leaves no partial files behind."""
    content = b"this is definitely not an archive" * 20

    with pytest.raises(provider_errors.ArchiveDownloadError):
        repository_archive.extract_content(content, str(tmp_path))

    assert list(tmp_path.iterdir()) == []


def testExtractContent_whenContentExceedsSizeLimit_raisesArchiveDownloadError(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ensures oversized embedded content is rejected before extraction."""
    monkeypatch.setattr(repository_archive, "_MAX_ARCHIVE_BYTES", 10)
    content = _build_zip({"README.md": "# repo"})

    with pytest.raises(provider_errors.ArchiveDownloadError, match="size limit"):
        repository_archive.extract_content(content, str(tmp_path))


def testExtractContent_whenUncompressedSizeExceedsLimit_raisesArchiveDownloadError(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ensures a zip bomb is rejected based on its declared uncompressed size."""
    monkeypatch.setattr(repository_archive, "_MAX_EXTRACTED_BYTES", 5)
    content = _build_zip({"big.txt": "x" * 100})

    with pytest.raises(provider_errors.ArchiveDownloadError, match="uncompressed size"):
        repository_archive.extract_content(content, str(tmp_path))


def testExtractContent_whenMemberCountExceedsLimit_raisesArchiveDownloadError(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ensures an archive with too many members is rejected."""
    monkeypatch.setattr(repository_archive, "_MAX_MEMBERS", 2)
    content = _build_zip({f"file_{i}.txt": "x" for i in range(5)})

    with pytest.raises(provider_errors.ArchiveDownloadError, match="member count"):
        repository_archive.extract_content(content, str(tmp_path))


def testExtractContent_whenZipMemberEscapesDestination_raisesArchiveDownloadError(
    tmp_path: pathlib.Path,
) -> None:
    """Ensures a zip member resolving outside the destination is rejected."""
    content = _build_zip({"../../escaped.txt": "owned"})

    with pytest.raises(provider_errors.ArchiveDownloadError, match="escape"):
        repository_archive.extract_content(content, str(tmp_path))


def testExtractContent_whenTarMemberEscapesDestination_raisesArchiveDownloadError(
    tmp_path: pathlib.Path,
) -> None:
    """Ensures a tar member resolving outside the destination is rejected."""
    content = _build_tar_gz({"../../escaped.txt": "owned"})

    with pytest.raises(provider_errors.ArchiveDownloadError, match="escape"):
        repository_archive.extract_content(content, str(tmp_path))


def testDownloadArchive_whenArchiveIsValid_extractsFilesIntoDestination(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ensures a downloaded archive is extracted into the destination directory."""
    content = _build_zip({"src/main.py": "print('hello')"})
    monkeypatch.setattr(
        repository_archive.requests,
        "get",
        lambda *args, **kwargs: _FakeResponse(content),
    )

    repository_archive.download_archive("https://example.com/repo.zip", str(tmp_path))

    assert (tmp_path / "src" / "main.py").read_text() == "print('hello')"


def testDownloadArchive_whenDestinationDoesNotExist_createsIt(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ensures the destination directory is created when missing."""
    content = _build_zip({"README.md": "# repo"})
    monkeypatch.setattr(
        repository_archive.requests,
        "get",
        lambda *args, **kwargs: _FakeResponse(content),
    )
    destination = tmp_path / "missing" / "nested"

    repository_archive.download_archive(
        "https://example.com/repo.zip", str(destination)
    )

    assert (destination / "README.md").read_text() == "# repo"


def testDownloadArchive_whenRequestFails_raisesArchiveDownloadError(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ensures a network failure surfaces as an ArchiveDownloadError."""

    def _raise(*args: object, **kwargs: object) -> None:
        raise requests.ConnectionError("boom")

    monkeypatch.setattr(repository_archive.requests, "get", _raise)

    with pytest.raises(
        provider_errors.ArchiveDownloadError, match="Failed to download"
    ):
        repository_archive.download_archive(
            "https://example.com/repo.zip", str(tmp_path)
        )


def testDownloadArchive_whenDownloadExceedsSizeLimit_raisesArchiveDownloadError(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ensures the download is aborted once the size limit is exceeded."""
    monkeypatch.setattr(repository_archive, "_MAX_ARCHIVE_BYTES", 10)
    content = _build_zip({"README.md": "# repo" * 100})
    monkeypatch.setattr(
        repository_archive.requests,
        "get",
        lambda *args, **kwargs: _FakeResponse(content),
    )

    with pytest.raises(provider_errors.ArchiveDownloadError, match="size limit"):
        repository_archive.download_archive(
            "https://example.com/repo.zip", str(tmp_path)
        )


def _build_corrupt(content: bytes, start: int, length: int) -> bytes:
    corrupted = bytearray(content)
    corrupted[start : start + length] = b"\x00" * length
    return bytes(corrupted)


def testExtractContent_whenTarGzIsTruncated_raisesArchiveDownloadError(
    tmp_path: pathlib.Path,
) -> None:
    """Ensures a truncated gzip stream is reported as an archive failure."""
    content = _build_tar_gz({"big.txt": "x" * 200000})

    with pytest.raises(provider_errors.ArchiveDownloadError):
        repository_archive.extract_content(content[: len(content) // 2], str(tmp_path))


def testExtractContent_whenZipDeflateStreamIsCorrupt_raisesArchiveDownloadError(
    tmp_path: pathlib.Path,
) -> None:
    """Ensures a corrupt deflate stream is reported as an archive failure."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr("a.txt", "y" * 100000)
    content = _build_corrupt(buffer.getvalue(), 80, 120)

    with pytest.raises(provider_errors.ArchiveDownloadError):
        repository_archive.extract_content(content, str(tmp_path))


def testExtractContent_when7zPayloadIsCorrupt_raisesArchiveDownloadError(
    tmp_path: pathlib.Path,
) -> None:
    """Ensures a corrupt 7z payload is reported as an archive failure."""
    content = _build_7z({"a.txt": "z" * 50000})

    with pytest.raises(provider_errors.ArchiveDownloadError):
        repository_archive.extract_content(
            _build_corrupt(content, len(content) - 60, 60), str(tmp_path)
        )


def testExtractContent_when7zMemberCountExceedsLimit_raisesArchiveDownloadError(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ensures the member-count cap is wired for the 7z branch."""
    monkeypatch.setattr(repository_archive, "_MAX_MEMBERS", 2)
    content = _build_7z({f"file_{i}.txt": "x" for i in range(5)})

    with pytest.raises(provider_errors.ArchiveDownloadError, match="member count"):
        repository_archive.extract_content(content, str(tmp_path))


def testExtractContent_when7zUncompressedSizeExceedsLimit_raisesArchiveDownloadError(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ensures the uncompressed-size cap is wired for the 7z branch."""
    monkeypatch.setattr(repository_archive, "_MAX_EXTRACTED_BYTES", 5)
    content = _build_7z({"big.txt": "x" * 100})

    with pytest.raises(provider_errors.ArchiveDownloadError, match="uncompressed size"):
        repository_archive.extract_content(content, str(tmp_path))


def testCheckExtractedSymlinks_whenSymlinkEscapesDirectory_raisesArchiveDownloadError(
    tmp_path: pathlib.Path,
) -> None:
    """Ensures a symlink resolving outside the staging directory is rejected."""
    (tmp_path / "link").symlink_to("../../../../etc")

    with pytest.raises(provider_errors.ArchiveDownloadError, match="symlink"):
        repository_archive._check_extracted_symlinks(tmp_path)


def testCheckExtractedSymlinks_whenSymlinkStaysInsideDirectory_isAccepted(
    tmp_path: pathlib.Path,
) -> None:
    """Ensures an internal symlink is left alone."""
    (tmp_path / "real.txt").write_text("data")
    (tmp_path / "link").symlink_to("real.txt")

    repository_archive._check_extracted_symlinks(tmp_path)

    assert (tmp_path / "link").read_text() == "data"
