"""Downloads and extracts repository archive assets onto the shared scan volume."""

import collections.abc
import datetime
import logging
import pathlib
import struct
import tarfile
import tempfile
import zipfile

import py7zr
import requests

from agent.providers import errors

logger = logging.getLogger(__name__)

_DOWNLOAD_TIMEOUT = datetime.timedelta(minutes=10)
_CHUNK_SIZE = 1024 * 1024
_MAX_ARCHIVE_BYTES = 5 * 1024 * 1024 * 1024
_MAX_EXTRACTED_BYTES = 10 * 1024 * 1024 * 1024
_MAX_MEMBERS = 1_000_000
_MAX_7Z_HEADER_BYTES = 256 * 1024 * 1024

_TAR_MAGIC_OFFSET_START = 257
_TAR_MAGIC_OFFSET_END = 262
_MIN_TAR_HEADER_BYTES = 263

_TAR_USTAR_MAGIC = b"ustar"

_FORMAT_SIGNATURES: dict[bytes, str] = {
    b"PK\x03\x04": "zip",
    b"PK\x05\x06": "zip",
    b"\x1f\x8b": "gzip",
    b"BZh": "bzip2",
    b"\xfd7zXZ\x00": "xz",
    b"\x5d\x00": "lzma",
    b"7z\xbc\xaf\x27\x1c": "7z",
}


def _check_member_paths(
    members: collections.abc.Sequence[str], destination: pathlib.Path
) -> None:
    """Reject any member whose resolved path would land outside `destination`.

    Zip-only: `ZipFile.extractall` already neutralizes "../" and absolute paths on its
    own by silently stripping them, so this check isn't what keeps extraction safe — it
    makes an escaping member fail closed instead. Tar gets the equivalent guarantee from
    `filter="data"` in `_extract` below, which raises instead of sanitizing.
    """
    destination_resolved = destination.resolve()
    for member in members:
        member_resolved = (destination_resolved / member).resolve()
        if member_resolved.is_relative_to(destination_resolved) is False:
            raise errors.ArchiveDownloadError(
                f"Archive member {member!r} would escape destination {destination}"
            )


def _check_extracted_size(sizes: collections.abc.Iterable[int]) -> None:
    """Reject an archive whose total uncompressed size exceeds the limit."""
    total_uncompressed = sum(sizes)
    if total_uncompressed > _MAX_EXTRACTED_BYTES:
        raise errors.ArchiveDownloadError(
            f"Archive uncompressed size {total_uncompressed} exceeds "
            f"{_MAX_EXTRACTED_BYTES} bytes limit"
        )


def _check_member_count(members: collections.abc.Sized) -> None:
    """Reject an archive whose member count exceeds the limit.

    A tar of millions of zero-byte files slips past the uncompressed-size cap
    while still exhausting inodes and memory during enumeration and extraction.
    """
    count = len(members)
    if count > _MAX_MEMBERS:
        raise errors.ArchiveDownloadError(
            f"Archive member count {count} exceeds {_MAX_MEMBERS} limit"
        )


def _check_zip_member_count(archive_path: pathlib.Path) -> None:
    """Reject an oversized ZIP member count before ZipFile parses the directory."""
    with archive_path.open("rb") as archive_file:
        archive_file.seek(0, 2)
        archive_size = archive_file.tell()
        trailer_size = min(archive_size, 22 + 65535)
        archive_file.seek(archive_size - trailer_size)
        trailer = archive_file.read(trailer_size)

        eocd_offset = trailer.rfind(b"PK\x05\x06")
        if eocd_offset < 0:
            return

        member_count = struct.unpack_from("<H", trailer, eocd_offset + 10)[0]
        if member_count == 0xFFFF:
            eocd_absolute_offset = archive_size - trailer_size + eocd_offset
            locator_absolute_offset = eocd_absolute_offset - 20
            if locator_absolute_offset >= 0:
                archive_file.seek(locator_absolute_offset)
                locator = archive_file.read(20)
                if locator.startswith(b"PK\x06\x07"):
                    zip64_offset = struct.unpack_from("<Q", locator, 8)[0]
                    archive_file.seek(zip64_offset)
                    zip64_eocd = archive_file.read(56)
                    if zip64_eocd.startswith(b"PK\x06\x06"):
                        member_count = struct.unpack_from("<Q", zip64_eocd, 32)[0]

        if member_count > _MAX_MEMBERS:
            raise errors.ArchiveDownloadError(
                f"Archive member count {member_count} exceeds {_MAX_MEMBERS} limit"
            )


def _check_7z_header_size(archive_path: pathlib.Path) -> None:
    """Reject an oversized 7z metadata header before py7zr parses it."""
    with archive_path.open("rb") as archive_file:
        signature_header = archive_file.read(32)

    if not signature_header.startswith(b"7z\xbc\xaf\x27\x1c"):
        return

    next_header_size = struct.unpack_from("<Q", signature_header, 20)[0]
    if next_header_size > _MAX_7Z_HEADER_BYTES:
        raise errors.ArchiveDownloadError(
            f"7z header size {next_header_size} exceeds "
            f"{_MAX_7Z_HEADER_BYTES} bytes limit"
        )


def _collect_tar_members(tar_file: tarfile.TarFile) -> list[tarfile.TarInfo]:
    """Collect tar members lazily, bailing out once the member cap is exceeded.

    `tarfile.TarFile` is iterable and yields one `TarInfo` at a time as it parses
    the entry stream, so we never materialise the full list up front. This matters
    for an inode bomb of millions of zero-byte files: `getmembers()` would build
    every `TarInfo` into memory *before* any size/count guard could run, exhausting
    it during enumeration itself. Iterating here caps the work at `_MAX_MEMBERS + 1`
    entries, and the error leaves no extracted files behind (the staging dir is
    still cleaned up by the caller).
    """
    members: list[tarfile.TarInfo] = []
    for member in tar_file:
        members.append(member)
        if len(members) > _MAX_MEMBERS:
            raise errors.ArchiveDownloadError(
                f"Archive member count exceeds {_MAX_MEMBERS} limit"
            )
    return members


def _check_extracted_symlinks(directory: pathlib.Path) -> None:
    """Reject any symlink under `directory` whose target escapes it.

    The lexical `_check_member_paths` check runs before extraction and therefore
    cannot see link semantics. Tar gets containment from `filter="data"` and zip
    from `extractall` sanitization, but the 7z branch materializes symlink members
    as real symlinks, so a `link -> ../..` entry followed by `link/evil` would
    write outside the destination. Current py7zr refuses such archives itself;
    auditing here keeps the guarantee ours rather than a transitive dependency's.
    """
    directory_resolved = directory.resolve()
    for entry in directory.rglob("*"):
        if entry.is_symlink() is False:
            continue
        target_resolved = (entry.parent / entry.readlink()).resolve()
        if target_resolved.is_relative_to(directory_resolved) is False:
            raise errors.ArchiveDownloadError(
                f"Archive symlink {entry.name!r} points outside the destination"
            )


def _get_archive_format(archive_path: pathlib.Path) -> str | None:
    """Determine the archive format from its header signature."""
    with archive_path.open("rb") as f:
        header = f.read(_MIN_TAR_HEADER_BYTES)

    for signature, archive_format in _FORMAT_SIGNATURES.items():
        if header.startswith(signature) is True:
            return archive_format

    is_ustar = header[_TAR_MAGIC_OFFSET_START:_TAR_MAGIC_OFFSET_END] == _TAR_USTAR_MAGIC
    if is_ustar is True:
        return "tar"

    return None


def _extract(archive_path: pathlib.Path, destination: pathlib.Path) -> None:
    """Extract a zip or tar (optionally compressed) archive into `destination`.

    Extracts into a temp subdirectory of `destination` first and only moves the result
    into place once extraction fully succeeds, so a failure partway through (e.g. disk
    full) never leaves partial files behind in `destination`.
    """

    archive_format = _get_archive_format(archive_path)
    if archive_format is None:
        raise errors.ArchiveDownloadError(
            f"Unsupported repository archive format at {archive_path}"
        )

    with tempfile.TemporaryDirectory(dir=str(destination)) as staging_dir_name:
        staging_dir = pathlib.Path(staging_dir_name)

        # Every archive library signals corruption with its own exception type, and the
        # list is neither documented nor stable: a truncated gzip surfaces as EOFError,
        # a corrupt deflate stream as zlib.error, xz as lzma.LZMAError, 7z as CrcError
        # or DecompressionError. Enumerating them invites the next one to escape and
        # crash start(), aborting the whole scan instead of skipping one asset. So this
        # is the single boundary where any library failure becomes ArchiveDownloadError;
        # the guards above raise it already and pass through untouched.
        try:
            if archive_format == "zip":
                _check_zip_member_count(archive_path)
                with zipfile.ZipFile(archive_path) as zip_file:
                    _check_member_count(zip_file.infolist())
                    _check_member_paths(zip_file.namelist(), staging_dir)
                    _check_extracted_size(
                        info.file_size for info in zip_file.infolist()
                    )
                    zip_file.extractall(staging_dir)

            elif archive_format in {"tar", "gzip", "bzip2", "xz", "lzma"}:
                with tarfile.open(archive_path) as tar_file:
                    members = _collect_tar_members(tar_file)
                    _check_member_paths([m.name for m in members], staging_dir)
                    _check_extracted_size([m.size for m in members])
                    tar_file.extractall(staging_dir, members, filter="data")

            elif archive_format == "7z":
                try:
                    _check_7z_header_size(archive_path)
                    with py7zr.SevenZipFile(archive_path, mode="r") as sz_file:
                        archive_members = sz_file.list()
                        _check_member_count(archive_members)
                        _check_extracted_size(
                            info.uncompressed
                            for info in archive_members
                            if info.is_directory is False
                        )
                        _check_member_paths(
                            [info.filename for info in archive_members], staging_dir
                        )
                        sz_file.extractall(str(staging_dir))
                except py7zr.PasswordRequired as exp:
                    raise errors.ArchiveDownloadError(
                        "7z archive is password protected."
                    ) from exp
                _check_extracted_symlinks(staging_dir)

            else:
                raise errors.ArchiveDownloadError(
                    f"Unsupported repository archive format at {archive_path}"
                )
        except errors.ArchiveDownloadError:
            raise
        except Exception as exc:
            raise errors.ArchiveDownloadError(
                f"Invalid or corrupted {archive_format} archive: {type(exc).__name__}"
            ) from exc

        for entry in staging_dir.iterdir():
            entry.rename(destination / entry.name)


def download_archive(content_url: str, destination: str) -> None:
    """Download `content_url` and extract it (zip or tar) into `destination`.

    Raises `ArchiveDownloadError` on any failure.
    """
    destination_dir = pathlib.Path(destination)

    try:
        with requests.get(
            content_url, stream=True, timeout=_DOWNLOAD_TIMEOUT.total_seconds()
        ) as response:
            response.raise_for_status()
            destination_dir.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=str(destination_dir)) as archive_file:
                downloaded_bytes = 0
                for chunk in response.iter_content(chunk_size=_CHUNK_SIZE):
                    downloaded_bytes += len(chunk)
                    if downloaded_bytes > _MAX_ARCHIVE_BYTES:
                        raise errors.ArchiveDownloadError(
                            f"Repository archive exceeds the "
                            f"{_MAX_ARCHIVE_BYTES} bytes size limit"
                        )
                    archive_file.write(chunk)
                archive_file.flush()
                _extract(pathlib.Path(archive_file.name), destination_dir)
    except errors.ArchiveDownloadError:
        raise
    except requests.RequestException as e:
        logger.error("Failed to download repository archive: %s", type(e).__name__)
        raise errors.ArchiveDownloadError(
            "Failed to download repository archive"
        ) from e
    except Exception as e:
        raise errors.ArchiveDownloadError(
            f"Failed to download or extract repository archive: {type(e).__name__}"
        ) from e


def extract_content(content: bytes, destination: str) -> None:
    """Extract embedded archive `content` (zip or tar) into `destination`.

    Raises `ArchiveDownloadError` on any failure.
    """
    if len(content) > _MAX_ARCHIVE_BYTES:
        raise errors.ArchiveDownloadError(
            f"Embedded repository archive exceeds the {_MAX_ARCHIVE_BYTES} bytes size limit"
        )

    destination_dir = pathlib.Path(destination)

    try:
        destination_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=str(destination_dir)) as archive_file:
            archive_file.write(content)
            archive_file.flush()
            _extract(pathlib.Path(archive_file.name), destination_dir)
    except errors.ArchiveDownloadError:
        raise
    except Exception as e:
        raise errors.ArchiveDownloadError(
            f"Failed to extract embedded repository archive: {type(e).__name__}"
        ) from e
