"""Unittests for the repository archive downloader."""

import collections.abc
import io
import pathlib
import tarfile
import zipfile
from collections.abc import Callable

import py7zr
import pytest
import requests
from typing_extensions import Self

from agent import repository_archive
from agent.providers import errors


class _FakeResponse:
    def __init__(self, content: bytes, status_code: int = 200) -> None:
        self._content = content
        self.status_code = status_code
        self.closed = False

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        self.closed = True

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")

    def iter_content(self, chunk_size: int) -> collections.abc.Iterator[bytes]:
        for i in range(0, len(self._content), chunk_size):
            yield self._content[i : i + chunk_size]


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
            data = content.encode()
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar_file.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


@pytest.fixture
def mock_archive_response(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[bytes, int], None]:
    """Return a setter that makes `repository_archive.requests.get` return a fake response with `content`."""

    def _set(content: bytes, status_code: int = 200) -> None:
        monkeypatch.setattr(
            repository_archive.requests,
            "get",
            lambda *args, **kwargs: _FakeResponse(content, status_code),
        )

    return _set


def testDownloadArchive_whenZipArchive_extractsFilesUnderDestination(
    tmp_path: pathlib.Path, mock_archive_response: Callable[[bytes, int], None]
) -> None:
    """A zip archive is downloaded and its contents extracted into the destination."""
    zip_bytes = _build_zip({"src/main.py": "print('hi')", "README.md": "hello"})
    mock_archive_response(zip_bytes, 200)

    repository_archive.download_archive(
        "https://storage.example.com/repo.zip", str(tmp_path)
    )

    assert (tmp_path / "src" / "main.py").read_text() == "print('hi')"
    assert (tmp_path / "README.md").read_text() == "hello"


def testDownloadArchive_whenTarGzArchive_extractsFilesUnderDestination(
    tmp_path: pathlib.Path, mock_archive_response: Callable[[bytes, int], None]
) -> None:
    """A tar.gz archive is downloaded and its contents extracted into the destination."""
    tar_bytes = _build_tar_gz({"src/main.py": "print('hi')"})
    mock_archive_response(tar_bytes, 200)

    repository_archive.download_archive(
        "https://storage.example.com/repo.tar.gz", str(tmp_path)
    )

    assert (tmp_path / "src" / "main.py").read_text() == "print('hi')"


def testDownloadArchive_whenDestinationDoesNotExist_createsIt(
    tmp_path: pathlib.Path, mock_archive_response: Callable[[bytes, int], None]
) -> None:
    """The destination directory is created if the shared volume isn't mounted yet."""
    zip_bytes = _build_zip({"main.py": "print('hi')"})
    mock_archive_response(zip_bytes, 200)
    destination = tmp_path / "code"

    repository_archive.download_archive(
        "https://storage.example.com/repo.zip", str(destination)
    )

    assert (destination / "main.py").read_text() == "print('hi')"


def testDownloadArchive_whenZipHasPathTraversalMember_raisesArchiveDownloadError(
    tmp_path: pathlib.Path, mock_archive_response: Callable[[bytes, int], None]
) -> None:
    """A member name (../..) that would escape the destination is rejected outright."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zip_file:
        zip_file.writestr("../../evil.txt", "pwned")
    mock_archive_response(buffer.getvalue(), 200)
    destination = tmp_path / "code"

    with pytest.raises(errors.ArchiveDownloadError):
        repository_archive.download_archive(
            "https://storage.example.com/repo.zip", str(destination)
        )

    assert not (destination / "evil.txt").exists()
    assert not (tmp_path / "evil.txt").exists()


def testDownloadArchive_whenZipHasAbsolutePathMember_raisesArchiveDownloadError(
    tmp_path: pathlib.Path, mock_archive_response: Callable[[bytes, int], None]
) -> None:
    """A member with an absolute path is rejected outright."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zip_file:
        zip_file.writestr("/etc/evil.txt", "pwned")
    mock_archive_response(buffer.getvalue(), 200)
    destination = tmp_path / "code"

    with pytest.raises(errors.ArchiveDownloadError):
        repository_archive.download_archive(
            "https://storage.example.com/repo.zip", str(destination)
        )


def testDownloadArchive_whenTarHasPathTraversalMember_raisesArchiveDownloadError(
    tmp_path: pathlib.Path, mock_archive_response: Callable[[bytes, int], None]
) -> None:
    """A tar member name (../..) that would escape the destination is rejected outright."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar_file:
        data = b"pwned"
        info = tarfile.TarInfo(name="../../evil.txt")
        info.size = len(data)
        tar_file.addfile(info, io.BytesIO(data))
    mock_archive_response(buffer.getvalue(), 200)
    destination = tmp_path / "code"

    with pytest.raises(errors.ArchiveDownloadError):
        repository_archive.download_archive(
            "https://storage.example.com/repo.tar.gz", str(destination)
        )

    assert not (tmp_path / "evil.txt").exists()


def testExtractContent_whenZipHasPathTraversalMember_raisesArchiveDownloadError(
    tmp_path: pathlib.Path,
) -> None:
    """A member name (../..) in embedded content that would escape is rejected outright."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zip_file:
        zip_file.writestr("../../evil.txt", "pwned")
    destination = tmp_path / "code"

    with pytest.raises(errors.ArchiveDownloadError):
        repository_archive.extract_content(buffer.getvalue(), str(destination))

    assert not (tmp_path / "evil.txt").exists()


def testDownloadArchive_whenServerReturnsErrorStatus_raisesArchiveDownloadError(
    mock_archive_response: Callable[[bytes, int], None],
) -> None:
    """A non-2xx response surfaces as an ArchiveDownloadError."""
    mock_archive_response(b"", 403)

    with pytest.raises(errors.ArchiveDownloadError):
        repository_archive.download_archive(
            "https://storage.example.com/repo.zip", "/code"
        )


def testDownloadArchive_whenConnectionFails_raisesArchiveDownloadError(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A network-level failure surfaces as an ArchiveDownloadError."""

    def raise_connection_error(*args, **kwargs):
        raise requests.ConnectionError("boom")

    monkeypatch.setattr(repository_archive.requests, "get", raise_connection_error)

    with pytest.raises(errors.ArchiveDownloadError):
        repository_archive.download_archive(
            "https://storage.example.com/repo.zip", "/code"
        )


def testDownloadArchive_whenArchiveExceedsMaxSize_raisesArchiveDownloadError(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    mock_archive_response: Callable[[bytes, int], None],
) -> None:
    """A download exceeding the configured size limit is aborted, not silently truncated."""
    monkeypatch.setattr(repository_archive, "_MAX_ARCHIVE_BYTES", 10)
    monkeypatch.setattr(repository_archive, "_CHUNK_SIZE", 4)
    mock_archive_response(b"x" * 100, 200)

    with pytest.raises(errors.ArchiveDownloadError):
        repository_archive.download_archive(
            "https://storage.example.com/repo.zip", str(tmp_path)
        )


def testDownloadArchive_whenZipUncompressedSizeExceedsLimit_raisesArchiveDownloadError(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    mock_archive_response: Callable[[bytes, int], None],
) -> None:
    """A small zip that declares a huge uncompressed size is rejected before extraction."""
    monkeypatch.setattr(repository_archive, "_MAX_EXTRACTED_BYTES", 10)
    zip_bytes = _build_zip({"main.py": "print('hi')" * 10})
    mock_archive_response(zip_bytes, 200)

    with pytest.raises(errors.ArchiveDownloadError):
        repository_archive.download_archive(
            "https://storage.example.com/repo.zip", str(tmp_path)
        )

    assert not (tmp_path / "main.py").exists()


def testDownloadArchive_whenTarUncompressedSizeExceedsLimit_raisesArchiveDownloadError(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    mock_archive_response: Callable[[bytes, int], None],
) -> None:
    """A small tar.gz that declares a huge uncompressed size is rejected before extraction."""
    monkeypatch.setattr(repository_archive, "_MAX_EXTRACTED_BYTES", 10)
    tar_bytes = _build_tar_gz({"main.py": "print('hi')" * 10})
    mock_archive_response(tar_bytes, 200)

    with pytest.raises(errors.ArchiveDownloadError):
        repository_archive.download_archive(
            "https://storage.example.com/repo.tar.gz", str(tmp_path)
        )

    assert not (tmp_path / "main.py").exists()


def testDownloadArchive_whenTarMemberCountExceedsLimit_raisesArchiveDownloadError(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    mock_archive_response: Callable[[bytes, int], None],
) -> None:
    """A tar with one member more than the limit is rejected before extraction."""
    monkeypatch.setattr(repository_archive, "_MAX_MEMBERS", 3)
    tar_bytes = _build_tar_gz({f"file{i}.py": "x" for i in range(4)})
    mock_archive_response(tar_bytes, 200)

    with pytest.raises(errors.ArchiveDownloadError):
        repository_archive.download_archive(
            "https://storage.example.com/repo.tar.gz", str(tmp_path)
        )

    assert not any((tmp_path / f"file{i}.py").exists() for i in range(4))


def testDownloadArchive_whenTarMemberCountAtLimit_extractsFiles(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    mock_archive_response: Callable[[bytes, int], None],
) -> None:
    """A tar with exactly as many members as the limit is accepted."""
    monkeypatch.setattr(repository_archive, "_MAX_MEMBERS", 3)
    tar_bytes = _build_tar_gz({f"file{i}.py": str(i) for i in range(3)})
    mock_archive_response(tar_bytes, 200)

    repository_archive.download_archive(
        "https://storage.example.com/repo.tar.gz", str(tmp_path)
    )

    for i in range(3):
        assert (tmp_path / f"file{i}.py").read_text() == str(i)


def testDownloadArchive_whenZipMemberCountExceedsLimit_raisesArchiveDownloadError(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    mock_archive_response: Callable[[bytes, int], None],
) -> None:
    """A zip with one member more than the limit is rejected before extraction."""
    monkeypatch.setattr(repository_archive, "_MAX_MEMBERS", 3)
    zip_bytes = _build_zip({f"file{i}.py": "x" for i in range(4)})
    mock_archive_response(zip_bytes, 200)

    with pytest.raises(errors.ArchiveDownloadError):
        repository_archive.download_archive(
            "https://storage.example.com/repo.zip", str(tmp_path)
        )

    assert not any((tmp_path / f"file{i}.py").exists() for i in range(4))


def testDownloadArchive_whenZipMemberCountAtLimit_extractsFiles(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    mock_archive_response: Callable[[bytes, int], None],
) -> None:
    """A zip with exactly as many members as the limit is accepted."""
    monkeypatch.setattr(repository_archive, "_MAX_MEMBERS", 3)
    zip_bytes = _build_zip({f"file{i}.py": str(i) for i in range(3)})
    mock_archive_response(zip_bytes, 200)

    repository_archive.download_archive(
        "https://storage.example.com/repo.zip", str(tmp_path)
    )

    for i in range(3):
        assert (tmp_path / f"file{i}.py").read_text() == str(i)


def testDownloadArchive_whenDownloading_stagesTempFileOnDestinationVolume(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    mock_archive_response: Callable[[bytes, int], None],
) -> None:
    """The temp archive file is created on the destination volume, not the system temp dir."""
    dir_kwargs: list[str | None] = []
    original_named_temporary_file = repository_archive.tempfile.NamedTemporaryFile

    def spy_named_temporary_file(*args, **kwargs):
        dir_kwargs.append(kwargs.get("dir"))
        return original_named_temporary_file(*args, **kwargs)

    monkeypatch.setattr(
        repository_archive.tempfile, "NamedTemporaryFile", spy_named_temporary_file
    )
    zip_bytes = _build_zip({"main.py": "print('hi')"})
    mock_archive_response(zip_bytes, 200)

    repository_archive.download_archive(
        "https://storage.example.com/repo.zip", str(tmp_path)
    )

    assert dir_kwargs == [str(tmp_path)]


def testDownloadArchive_whenStreamingFailsMidDownload_raisesArchiveDownloadError(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A connection drop while streaming the body surfaces as an ArchiveDownloadError."""

    class _BrokenStreamResponse(_FakeResponse):
        def iter_content(self, chunk_size: int) -> collections.abc.Iterator[bytes]:
            yield b"partial"
            raise requests.exceptions.ChunkedEncodingError("connection broken")

    monkeypatch.setattr(
        repository_archive.requests,
        "get",
        lambda *args, **kwargs: _BrokenStreamResponse(b""),
    )

    with pytest.raises(errors.ArchiveDownloadError):
        repository_archive.download_archive(
            "https://storage.example.com/repo.zip", str(tmp_path)
        )


def testDownloadArchive_whenContentIsNotAnArchive_raisesArchiveDownloadError(
    tmp_path: pathlib.Path, mock_archive_response: Callable[[bytes, int], None]
) -> None:
    """Content that is neither a zip nor a tar archive is rejected."""
    mock_archive_response(b"not an archive", 200)

    with pytest.raises(errors.ArchiveDownloadError):
        repository_archive.download_archive(
            "https://storage.example.com/repo.zip", str(tmp_path)
        )


def testDownloadArchive_whenExtractionFailsPartway_leavesNoFilesInDestination(
    tmp_path: pathlib.Path, mock_archive_response: Callable[[bytes, int], None]
) -> None:
    """A member that fails mid-extraction leaves no earlier-extracted files behind."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as zip_file:
        zip_file.writestr("first.txt", "first content")
        zip_file.writestr("second.txt", "second content")
    zip_bytes = bytearray(buffer.getvalue())
    corrupt_at = zip_bytes.find(b"second content")
    zip_bytes[corrupt_at] ^= 0xFF
    mock_archive_response(bytes(zip_bytes), 200)

    with pytest.raises(errors.ArchiveDownloadError):
        repository_archive.download_archive(
            "https://storage.example.com/repo.zip", str(tmp_path)
        )

    assert not (tmp_path / "first.txt").exists()
    assert not (tmp_path / "second.txt").exists()
    assert list(tmp_path.iterdir()) == []


def testDownloadArchive_whenExtractionFailsAfterDownload_closesConnection(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The HTTP connection is released even when extraction fails after a successful download."""
    responses: list[_FakeResponse] = []

    def fake_get(*args, **kwargs) -> _FakeResponse:
        response = _FakeResponse(b"not an archive")
        responses.append(response)
        return response

    monkeypatch.setattr(repository_archive.requests, "get", fake_get)

    with pytest.raises(errors.ArchiveDownloadError):
        repository_archive.download_archive(
            "https://storage.example.com/repo.zip", str(tmp_path)
        )

    assert len(responses) == 1
    assert responses[0].closed is True


def testExtractContent_whenZipBytes_extractsFilesUnderDestination(
    tmp_path: pathlib.Path,
) -> None:
    """Embedded zip bytes are extracted into the destination, no network call involved."""
    zip_bytes = _build_zip({"src/main.py": "print('hi')"})

    repository_archive.extract_content(zip_bytes, str(tmp_path))

    assert (tmp_path / "src" / "main.py").read_text() == "print('hi')"


def testExtractContent_whenDestinationDoesNotExist_createsIt(
    tmp_path: pathlib.Path,
) -> None:
    """The destination directory is created if the shared volume isn't mounted yet."""
    zip_bytes = _build_zip({"main.py": "print('hi')"})
    destination = tmp_path / "code"

    repository_archive.extract_content(zip_bytes, str(destination))

    assert (destination / "main.py").read_text() == "print('hi')"


def testExtractContent_whenUncompressedSizeExceedsLimit_raisesArchiveDownloadError(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Embedded zip bytes declaring a huge uncompressed size are rejected before extraction."""
    monkeypatch.setattr(repository_archive, "_MAX_EXTRACTED_BYTES", 10)
    zip_bytes = _build_zip({"main.py": "print('hi')" * 10})

    with pytest.raises(errors.ArchiveDownloadError):
        repository_archive.extract_content(zip_bytes, str(tmp_path))

    assert not (tmp_path / "main.py").exists()


def testExtractContent_whenExtracting_stagesTempFileOnDestinationVolume(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The temp archive file is created on the destination volume, not the system temp dir."""
    dir_kwargs: list[str | None] = []
    original_named_temporary_file = repository_archive.tempfile.NamedTemporaryFile

    def spy_named_temporary_file(*args, **kwargs):
        dir_kwargs.append(kwargs.get("dir"))
        return original_named_temporary_file(*args, **kwargs)

    monkeypatch.setattr(
        repository_archive.tempfile, "NamedTemporaryFile", spy_named_temporary_file
    )
    zip_bytes = _build_zip({"main.py": "print('hi')"})

    repository_archive.extract_content(zip_bytes, str(tmp_path))

    assert dir_kwargs == [str(tmp_path)]


def testExtractContent_whenDestinationCannotBeCreated_raisesArchiveDownloadError(
    tmp_path: pathlib.Path,
) -> None:
    """An OSError creating the destination directory is wrapped, not raised raw."""
    blocked_path = tmp_path / "blocked"
    blocked_path.write_text("not a directory")
    zip_bytes = _build_zip({"main.py": "print('hi')"})

    with pytest.raises(errors.ArchiveDownloadError):
        repository_archive.extract_content(zip_bytes, str(blocked_path))


def testDownloadArchive_whenDestinationCannotBeCreated_raisesArchiveDownloadError(
    tmp_path: pathlib.Path, mock_archive_response: Callable[[bytes, int], None]
) -> None:
    """An OSError creating the destination directory is wrapped, not raised raw."""
    blocked_path = tmp_path / "blocked"
    blocked_path.write_text("not a directory")
    zip_bytes = _build_zip({"main.py": "print('hi')"})
    mock_archive_response(zip_bytes, 200)

    with pytest.raises(errors.ArchiveDownloadError):
        repository_archive.download_archive(
            "https://storage.example.com/repo.zip", str(blocked_path)
        )


def testExtractContent_whenContentIsNotAnArchive_raisesArchiveDownloadError(
    tmp_path: pathlib.Path,
) -> None:
    """Embedded content that is neither a zip nor a tar archive is rejected."""
    with pytest.raises(errors.ArchiveDownloadError):
        repository_archive.extract_content(b"not an archive", str(tmp_path))


def testExtractContent_whenContentExceedsMaxSize_raisesArchiveDownloadError(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Embedded content larger than the configured size limit is rejected."""
    monkeypatch.setattr(repository_archive, "_MAX_ARCHIVE_BYTES", 10)

    with pytest.raises(errors.ArchiveDownloadError):
        repository_archive.extract_content(b"x" * 100, str(tmp_path))


def _build_tar_bz2(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:bz2") as tar_file:
        for name, content in files.items():
            data = content.encode()
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar_file.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def _build_tar_xz(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:xz") as tar_file:
        for name, content in files.items():
            data = content.encode()
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar_file.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def _build_7z(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with py7zr.SevenZipFile(buffer, "w") as sz_file:
        for name, content in files.items():
            sz_file.writestr(content, name)
    return buffer.getvalue()


def testDownloadArchive_whenTarBz2Archive_extractsFilesUnderDestination(
    tmp_path: pathlib.Path, mock_archive_response: Callable[[bytes, int], None]
) -> None:
    """A tar.bz2 archive is downloaded and its contents extracted into the destination."""
    tar_bytes = _build_tar_bz2({"src/main.py": "print('hi bzip2')"})
    mock_archive_response(tar_bytes, 200)

    repository_archive.download_archive(
        "https://storage.example.com/repo.tar.bz2", str(tmp_path)
    )

    assert (tmp_path / "src" / "main.py").read_text() == "print('hi bzip2')"


def testDownloadArchive_whenTarXzArchive_extractsFilesUnderDestination(
    tmp_path: pathlib.Path, mock_archive_response: Callable[[bytes, int], None]
) -> None:
    """A tar.xz archive is downloaded and its contents extracted into the destination."""
    tar_bytes = _build_tar_xz({"src/main.py": "print('hi xz')"})
    mock_archive_response(tar_bytes, 200)

    repository_archive.download_archive(
        "https://storage.example.com/repo.tar.xz", str(tmp_path)
    )

    assert (tmp_path / "src" / "main.py").read_text() == "print('hi xz')"


def testDownloadArchive_when7zArchive_extractsFilesUnderDestination(
    tmp_path: pathlib.Path, mock_archive_response: Callable[[bytes, int], None]
) -> None:
    """A 7z archive is downloaded and its contents extracted into the destination."""
    sz_bytes = _build_7z({"src/main.py": "print('hi 7z')"})
    mock_archive_response(sz_bytes, 200)

    repository_archive.download_archive(
        "https://storage.example.com/repo.7z", str(tmp_path)
    )

    assert (tmp_path / "src" / "main.py").read_text() == "print('hi 7z')"


def testDownloadArchive_when7zCorrupted_raisesArchiveDownloadError(
    tmp_path: pathlib.Path, mock_archive_response: Callable[[bytes, int], None]
) -> None:
    """A corrupted 7z archive raises ArchiveDownloadError."""
    corrupt_7z_bytes = b"7z\xbc\xaf\x27\x1c" + b"random_corrupt_data"
    mock_archive_response(corrupt_7z_bytes, 200)

    with pytest.raises(errors.ArchiveDownloadError):
        repository_archive.download_archive(
            "https://storage.example.com/repo.7z", str(tmp_path)
        )
