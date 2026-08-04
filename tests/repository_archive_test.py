"""Unittests for the repository archive downloader."""

import collections.abc
import functools
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

_ARCHIVE_URL = "https://storage.example.com/repo.archive"


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


class _BrokenStreamResponse(_FakeResponse):
    """A response whose body stops mid-stream, as on a dropped connection."""

    def iter_content(self, chunk_size: int) -> collections.abc.Iterator[bytes]:
        yield b"partial"
        raise requests.exceptions.ChunkedEncodingError("connection broken")


class _FakeGet:
    """A `requests.get` stand-in serving fixed bytes, keeping every response it hands out."""

    def __init__(self, content: bytes, status_code: int = 200) -> None:
        self._content = content
        self._status_code = status_code
        self.responses: list[_FakeResponse] = []

    def __call__(self, *args: object, **kwargs: object) -> _FakeResponse:
        response = _FakeResponse(self._content, self._status_code)
        self.responses.append(response)
        return response


class _NamedTemporaryFileSpy:
    """A `tempfile.NamedTemporaryFile` stand-in recording the `dir` it is called with."""

    def __init__(self) -> None:
        self._original = repository_archive.tempfile.NamedTemporaryFile
        self.dir_kwargs: list[str | None] = []

    def __call__(self, *args: object, **kwargs: object) -> object:
        self.dir_kwargs.append(kwargs.get("dir"))
        return self._original(*args, **kwargs)


def _raise_connection_error(*args: object, **kwargs: object) -> None:
    raise requests.ConnectionError("boom")


def _build_zip(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zip_file:
        for name, content in files.items():
            zip_file.writestr(name, content)
    return buffer.getvalue()


def _build_tar(files: dict[str, str], mode: str = "w:gz") -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode=mode) as tar_file:
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


_ARCHIVE_BUILDERS: dict[str, Callable[[dict[str, str]], bytes]] = {
    "zip": _build_zip,
    "tar.gz": _build_tar,
    "tar.bz2": functools.partial(_build_tar, mode="w:bz2"),
    "tar.xz": functools.partial(_build_tar, mode="w:xz"),
    "7z": _build_7z,
}

# Formats whose member table is inspected before extraction, so the count and
# path guards can be exercised against them.
_INSPECTABLE_BUILDERS: dict[str, Callable[[dict[str, str]], bytes]] = {
    "zip": _build_zip,
    "tar.gz": _build_tar,
}


class _MockArchiveResponse:
    """Installs a `requests.get` stand-in serving the given archive bytes."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._monkeypatch = monkeypatch

    def __call__(self, content: bytes, status_code: int = 200) -> _FakeGet:
        fake_get = _FakeGet(content, status_code)
        self._monkeypatch.setattr(repository_archive.requests, "get", fake_get)
        return fake_get


class _DownloadArchive:
    """Feeds archive bytes through `download_archive`, served over a mocked `requests.get`."""

    def __init__(self, mock_archive_response: _MockArchiveResponse) -> None:
        self._mock_archive_response = mock_archive_response

    def __call__(self, content: bytes, destination: str) -> None:
        self._mock_archive_response(content)
        repository_archive.download_archive(_ARCHIVE_URL, destination)


class _ExtractContent:
    """Feeds archive bytes through `extract_content`."""

    def __call__(self, content: bytes, destination: str) -> None:
        repository_archive.extract_content(content, destination)


@pytest.fixture
def mock_archive_response(monkeypatch: pytest.MonkeyPatch) -> _MockArchiveResponse:
    """Return a setter installing a `requests.get` stand-in that serves the given archive bytes."""
    return _MockArchiveResponse(monkeypatch)


@pytest.fixture(params=["download_archive", "extract_content"])
def extract_archive(
    request: pytest.FixtureRequest, mock_archive_response: _MockArchiveResponse
) -> Callable[[bytes, str], None]:
    """Both public entry points, so shared extraction behaviour is asserted against each.

    `download_archive` and `extract_content` differ only in how the bytes reach
    disk; everything after that is the same `_extract` call.
    """
    if request.param == "download_archive":
        return _DownloadArchive(mock_archive_response)

    return _ExtractContent()


@pytest.mark.parametrize(
    "build_archive", _ARCHIVE_BUILDERS.values(), ids=_ARCHIVE_BUILDERS.keys()
)
def testExtractArchive_whenSupportedFormat_extractsFilesUnderDestination(
    tmp_path: pathlib.Path,
    extract_archive: Callable[[bytes, str], None],
    build_archive: Callable[[dict[str, str]], bytes],
) -> None:
    """Every supported format is detected by its magic bytes and extracted."""
    archive_bytes = build_archive({"src/main.py": "print('hi')", "README.md": "hello"})

    extract_archive(archive_bytes, str(tmp_path))

    assert (tmp_path / "src" / "main.py").read_text() == "print('hi')"
    assert (tmp_path / "README.md").read_text() == "hello"


def testExtractArchive_whenDestinationDoesNotExist_createsIt(
    tmp_path: pathlib.Path, extract_archive: Callable[[bytes, str], None]
) -> None:
    """The destination directory is created if the shared volume isn't mounted yet."""
    zip_bytes = _build_zip({"main.py": "print('hi')"})
    destination = tmp_path / "code"

    extract_archive(zip_bytes, str(destination))

    assert (destination / "main.py").read_text() == "print('hi')"


def testExtractArchive_whenDestinationCannotBeCreated_raisesArchiveDownloadError(
    tmp_path: pathlib.Path, extract_archive: Callable[[bytes, str], None]
) -> None:
    """An OSError creating the destination directory is wrapped, not raised raw."""
    blocked_path = tmp_path / "blocked"
    blocked_path.write_text("not a directory")
    zip_bytes = _build_zip({"main.py": "print('hi')"})

    with pytest.raises(errors.ArchiveDownloadError):
        extract_archive(zip_bytes, str(blocked_path))


def testExtractArchive_whenContentIsNotAnArchive_raisesArchiveDownloadError(
    tmp_path: pathlib.Path, extract_archive: Callable[[bytes, str], None]
) -> None:
    """Content matching no known archive signature is rejected."""
    with pytest.raises(errors.ArchiveDownloadError):
        extract_archive(b"not an archive", str(tmp_path))


def testExtractArchive_whenStaging_putsTempFileOnDestinationVolume(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    extract_archive: Callable[[bytes, str], None],
) -> None:
    """The temp archive file is created on the destination volume, not the system temp dir."""
    named_temporary_file_spy = _NamedTemporaryFileSpy()
    monkeypatch.setattr(
        repository_archive.tempfile, "NamedTemporaryFile", named_temporary_file_spy
    )
    zip_bytes = _build_zip({"main.py": "print('hi')"})

    extract_archive(zip_bytes, str(tmp_path))

    assert named_temporary_file_spy.dir_kwargs == [str(tmp_path)]


@pytest.mark.parametrize("member_name", ["../../evil.txt", "/etc/evil.txt"])
@pytest.mark.parametrize(
    "build_archive", _INSPECTABLE_BUILDERS.values(), ids=_INSPECTABLE_BUILDERS.keys()
)
def testExtractArchive_whenMemberEscapesDestination_raisesArchiveDownloadError(
    tmp_path: pathlib.Path,
    extract_archive: Callable[[bytes, str], None],
    build_archive: Callable[[dict[str, str]], bytes],
    member_name: str,
) -> None:
    """A member path that would land outside the destination is rejected outright."""
    archive_bytes = build_archive({member_name: "pwned"})
    destination = tmp_path / "code"

    with pytest.raises(errors.ArchiveDownloadError):
        extract_archive(archive_bytes, str(destination))

    assert not (destination / "evil.txt").exists()
    assert not (tmp_path / "evil.txt").exists()


@pytest.mark.parametrize(
    "build_archive", _INSPECTABLE_BUILDERS.values(), ids=_INSPECTABLE_BUILDERS.keys()
)
def testExtractArchive_whenUncompressedSizeExceedsLimit_raisesArchiveDownloadError(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    extract_archive: Callable[[bytes, str], None],
    build_archive: Callable[[dict[str, str]], bytes],
) -> None:
    """A small archive declaring a huge uncompressed size is rejected before extraction."""
    monkeypatch.setattr(repository_archive, "_MAX_EXTRACTED_BYTES", 10)
    archive_bytes = build_archive({"main.py": "print('hi')" * 10})

    with pytest.raises(errors.ArchiveDownloadError):
        extract_archive(archive_bytes, str(tmp_path))

    assert not (tmp_path / "main.py").exists()


def testExtractArchive_whenArchiveExceedsMaxSize_raisesArchiveDownloadError(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    extract_archive: Callable[[bytes, str], None],
) -> None:
    """An archive over the size limit is rejected, not silently truncated."""
    monkeypatch.setattr(repository_archive, "_MAX_ARCHIVE_BYTES", 10)
    monkeypatch.setattr(repository_archive, "_CHUNK_SIZE", 4)

    with pytest.raises(errors.ArchiveDownloadError):
        extract_archive(b"x" * 100, str(tmp_path))


@pytest.mark.parametrize(
    "build_archive", _INSPECTABLE_BUILDERS.values(), ids=_INSPECTABLE_BUILDERS.keys()
)
def testExtractArchive_whenMemberCountExceedsLimit_raisesArchiveDownloadError(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    extract_archive: Callable[[bytes, str], None],
    build_archive: Callable[[dict[str, str]], bytes],
) -> None:
    """An archive with one member more than the limit is rejected before extraction."""
    monkeypatch.setattr(repository_archive, "_MAX_MEMBERS", 3)
    archive_bytes = build_archive({f"file{i}.py": "x" for i in range(4)})

    with pytest.raises(errors.ArchiveDownloadError):
        extract_archive(archive_bytes, str(tmp_path))

    assert not any((tmp_path / f"file{i}.py").exists() for i in range(4))


@pytest.mark.parametrize(
    "build_archive", _INSPECTABLE_BUILDERS.values(), ids=_INSPECTABLE_BUILDERS.keys()
)
def testExtractArchive_whenMemberCountAtLimit_extractsFiles(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    extract_archive: Callable[[bytes, str], None],
    build_archive: Callable[[dict[str, str]], bytes],
) -> None:
    """An archive with exactly as many members as the limit is accepted."""
    monkeypatch.setattr(repository_archive, "_MAX_MEMBERS", 3)
    archive_bytes = build_archive({f"file{i}.py": str(i) for i in range(3)})

    extract_archive(archive_bytes, str(tmp_path))

    for i in range(3):
        assert (tmp_path / f"file{i}.py").read_text() == str(i)


def testExtractArchive_whenExtractionFailsPartway_leavesNoFilesInDestination(
    tmp_path: pathlib.Path, extract_archive: Callable[[bytes, str], None]
) -> None:
    """A member that fails mid-extraction leaves no earlier-extracted files behind."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as zip_file:
        zip_file.writestr("first.txt", "first content")
        zip_file.writestr("second.txt", "second content")
    zip_bytes = bytearray(buffer.getvalue())
    corrupt_at = zip_bytes.find(b"second content")
    zip_bytes[corrupt_at] ^= 0xFF

    with pytest.raises(errors.ArchiveDownloadError):
        extract_archive(bytes(zip_bytes), str(tmp_path))

    assert list(tmp_path.iterdir()) == []


def testExtractArchive_whenDestinationAlreadyPopulated_mergesEntries(
    tmp_path: pathlib.Path, extract_archive: Callable[[bytes, str], None]
) -> None:
    """Re-extracting into a non-empty destination merges entries instead of crashing."""
    destination = tmp_path / "code"
    destination.mkdir(parents=True)
    (destination / "existing.py").write_text("keep")
    zip_bytes = _build_zip({"new.py": "print('new')"})

    extract_archive(zip_bytes, str(destination))

    assert (destination / "existing.py").read_text() == "keep"
    assert (destination / "new.py").read_text() == "print('new')"


def testExtractArchive_when7zIsCorrupted_raisesArchiveDownloadError(
    tmp_path: pathlib.Path, extract_archive: Callable[[bytes, str], None]
) -> None:
    """A truncated 7z archive surfaces as an ArchiveDownloadError, not a py7zr error."""
    corrupt_7z_bytes = b"7z\xbc\xaf\x27\x1c" + b"random_corrupt_data"

    with pytest.raises(errors.ArchiveDownloadError):
        extract_archive(corrupt_7z_bytes, str(tmp_path))


def testExtractArchive_when7zHasEscapingSymlink_raisesArchiveDownloadError(
    tmp_path: pathlib.Path, extract_archive: Callable[[bytes, str], None]
) -> None:
    """A 7z archive containing a symlink pointing outside the destination is rejected.

    This asserts the end-to-end fail-closed behaviour only. Current `py7zr` refuses
    such an archive itself, so the extraction never reaches
    `_check_no_escaping_symlinks`; that guard is covered directly below.
    """
    staging = tmp_path / "staging"
    (staging / "src").mkdir(parents=True)
    (staging / "src" / "main.py").write_text("print('hi')")
    (staging / "src" / "evil").symlink_to("/etc")
    buffer = io.BytesIO()
    with py7zr.SevenZipFile(buffer, "w") as sz_file:
        sz_file.writeall(str(staging / "src"), "src")
    destination = tmp_path / "code"

    with pytest.raises(errors.ArchiveDownloadError):
        extract_archive(buffer.getvalue(), str(destination))

    assert not (destination / "src" / "evil").exists()


def testCheckNoEscapingSymlinks_whenSymlinkTargetsOutsideRoot_raisesArchiveDownloadError(
    tmp_path: pathlib.Path,
) -> None:
    """The post-extraction guard rejects a symlink resolving outside the staging root.

    Exercised directly rather than through a 7z archive: current `py7zr` refuses an
    escaping symlink before extraction finishes, so an end-to-end test would pass
    even with this guard removed.
    """
    root = tmp_path / "staging"
    root.mkdir()
    (root / "evil").symlink_to("/etc")

    with pytest.raises(errors.ArchiveDownloadError):
        repository_archive._check_no_escaping_symlinks(root)


def testCheckNoEscapingSymlinks_whenSymlinkStaysInsideRoot_doesNotRaise(
    tmp_path: pathlib.Path,
) -> None:
    """A symlink pointing within the staging root is left in place."""
    root = tmp_path / "staging"
    (root / "src").mkdir(parents=True)
    (root / "src" / "main.py").write_text("print('hi')")
    (root / "link.py").symlink_to(root / "src" / "main.py")

    repository_archive._check_no_escaping_symlinks(root)

    assert (root / "link.py").read_text() == "print('hi')"


def testDownloadArchive_whenServerReturnsErrorStatus_raisesArchiveDownloadError(
    tmp_path: pathlib.Path, mock_archive_response: _MockArchiveResponse
) -> None:
    """A non-2xx response surfaces as an ArchiveDownloadError."""
    mock_archive_response(b"", 403)

    with pytest.raises(errors.ArchiveDownloadError):
        repository_archive.download_archive(_ARCHIVE_URL, str(tmp_path))


def testDownloadArchive_whenConnectionFails_raisesArchiveDownloadError(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A network-level failure surfaces as an ArchiveDownloadError."""
    monkeypatch.setattr(repository_archive.requests, "get", _raise_connection_error)

    with pytest.raises(errors.ArchiveDownloadError):
        repository_archive.download_archive(_ARCHIVE_URL, str(tmp_path))


def testDownloadArchive_whenStreamingFailsMidDownload_raisesArchiveDownloadError(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A connection drop while streaming the body surfaces as an ArchiveDownloadError."""
    monkeypatch.setattr(
        repository_archive.requests,
        "get",
        lambda *args, **kwargs: _BrokenStreamResponse(b""),
    )

    with pytest.raises(errors.ArchiveDownloadError):
        repository_archive.download_archive(_ARCHIVE_URL, str(tmp_path))


def testDownloadArchive_whenExtractionFailsAfterDownload_closesConnection(
    tmp_path: pathlib.Path, mock_archive_response: _MockArchiveResponse
) -> None:
    """The HTTP connection is released even when extraction fails after a successful download."""
    fake_get = mock_archive_response(b"not an archive")

    with pytest.raises(errors.ArchiveDownloadError):
        repository_archive.download_archive(_ARCHIVE_URL, str(tmp_path))

    assert len(fake_get.responses) == 1
    assert fake_get.responses[0].closed is True
