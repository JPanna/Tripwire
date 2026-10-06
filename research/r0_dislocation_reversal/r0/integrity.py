"""The one file-integrity check used everywhere (download, --verify, Stage C).

A local raw file may be consumed only if it matches the manifest:

1. its byte size equals the expected size; and
2. its SHA-256 equals the manifest SHA-256 when one is recorded; otherwise
3. its Git blob SHA-1 equals the manifest ``git_oid``
   (``sha1(b"blob <size>\\0" + content)``, the Git object convention).

No usable integrity metadata (no well-formed SHA-256 and no well-formed
``git_oid``) means the file is refused. Every check fails closed.
"""

from __future__ import annotations

import hashlib
import os
import re
import stat
from pathlib import Path

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
_CHUNK = 8 << 20


class IntegrityError(RuntimeError):
    """A file does not match, or cannot be checked against, the manifest."""


class Hasher:
    """Streaming SHA-256 and Git blob SHA-1 over the same bytes."""

    def __init__(self, declared_size: int) -> None:
        # The Git blob header carries the size; for a streamed download it is
        # the expected size, and a size mismatch fails verification anyway.
        self.sha256 = hashlib.sha256()
        self.git_sha1 = hashlib.sha1(b"blob %d\0" % declared_size)
        self.size = 0

    def update(self, chunk: bytes) -> None:
        self.sha256.update(chunk)
        self.git_sha1.update(chunk)
        self.size += len(chunk)


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def require_usable_metadata(
    expected_sha256: str | None, expected_git_oid: str | None, what: str
) -> None:
    """Raise IntegrityError unless a well-formed SHA-256 or Git oid is available."""
    if expected_sha256 is not None and not _SHA256_RE.match(expected_sha256):
        raise IntegrityError(f"{what}: malformed manifest SHA-256; refusing")
    if expected_sha256 is None and (
        expected_git_oid is None or not _SHA1_RE.match(expected_git_oid)
    ):
        raise IntegrityError(f"{what}: no usable integrity metadata (SHA-256 or git oid)")


def check_digests(
    *,
    size: int,
    sha256: str,
    git_sha1: str,
    expected_size: int,
    expected_sha256: str | None,
    expected_git_oid: str | None,
    what: str,
) -> None:
    """Raise IntegrityError unless the digests match the expected metadata."""
    require_usable_metadata(expected_sha256, expected_git_oid, what)
    if size != expected_size:
        raise IntegrityError(f"{what}: size {size} != expected {expected_size}")
    if expected_sha256 is not None:
        if sha256 != expected_sha256:
            raise IntegrityError(f"{what}: SHA-256 mismatch")
    elif git_sha1 != expected_git_oid:
        raise IntegrityError(f"{what}: Git blob SHA-1 mismatch")


def verify_file(
    path: Path, expected_size: int, expected_sha256: str | None, expected_git_oid: str | None
) -> str:
    """Verify a local regular file (symlinks refused); return its SHA-256."""
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError as e:
        raise IntegrityError(f"{path.name}: cannot open for verification ({e.strerror})") from None
    with os.fdopen(fd, "rb") as f:
        st = os.fstat(f.fileno())
        if not stat.S_ISREG(st.st_mode):
            raise IntegrityError(f"{path.name}: not a regular file")
        h = Hasher(st.st_size)
        while chunk := f.read(_CHUNK):
            h.update(chunk)
    check_digests(
        size=h.size,
        sha256=h.sha256.hexdigest(),
        git_sha1=h.git_sha1.hexdigest(),
        expected_size=expected_size,
        expected_sha256=expected_sha256,
        expected_git_oid=expected_git_oid,
        what=path.name,
    )
    return h.sha256.hexdigest()
