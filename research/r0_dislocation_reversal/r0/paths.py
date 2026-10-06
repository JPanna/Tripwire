"""Local data layout and the holdout guard.

Layout (all under the data root, which Git ignores):

    raw/<owner>__<name>@<revision-sha>/<repo path>   immutable raw-source cache
    exploration/                                     exploration-period outputs
                                                     (Stage C inspection); the
                                                     pre-holdout partition's location
                                                     is fixed at Stage E
    holdout/                                         holdout partition (built only
                                                     after the analysis freeze)

The raw cache holds whole upstream files, whatever period their rows belong
to. Row values in it are read only through ``r0.rawread``, which applies the
timestamp partition rule (``r0.periods.PARTITION_BOUNDARY``: PRE-HOLDOUT rows
are those before the holdout start) before any row leaves the reader. PRE-HOLDOUT
is an access-control notion only; research operations further restrict rows to
the EXPLORATION period (ADR-0022). ``data/holdout/`` can be read only with a
``HoldoutAuthorization``, which only ``authorize_holdout`` creates, from an
explicit command-line flag. No Stage A-C code path creates one.
"""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath

REPO_ROOT = Path(__file__).resolve().parents[3]
RESEARCH_DIR = Path(__file__).resolve().parents[1]


class HoldoutAccessError(PermissionError):
    """Raised when code tries to read holdout data without authorization."""


class RawCacheAccessError(PermissionError):
    """Raised when raw-cache rows are read outside ``r0.rawread``."""


_AUTH_SENTINEL = object()


class HoldoutAuthorization:
    """Proof that the caller was invoked with an explicit holdout flag."""

    __slots__ = ("purpose",)

    def __init__(self, purpose: str, _sentinel: object = None) -> None:
        if _sentinel is not _AUTH_SENTINEL:
            raise HoldoutAccessError("use authorize_holdout(); do not construct directly")
        self.purpose = purpose


def authorize_holdout(flag: bool, purpose: str) -> HoldoutAuthorization:
    """Return an authorization only if ``flag`` is literally ``True``."""
    if flag is not True:
        raise HoldoutAccessError(f"holdout access refused for {purpose!r}: no explicit flag")
    return HoldoutAuthorization(purpose, _AUTH_SENTINEL)


def data_root() -> Path:
    env = os.environ.get("R0_DATA_ROOT")
    return Path(env).expanduser().resolve() if env else (REPO_ROOT / "data").resolve()


def exploration_dir() -> Path:
    return data_root() / "exploration"


def holdout_dir(auth: HoldoutAuthorization) -> Path:
    _require_auth(auth)
    return data_root() / "holdout"


def raw_root() -> Path:
    return data_root() / "raw"


def raw_cache_dir(repo_id: str, revision_sha: str) -> Path:
    if not revision_sha or any(c not in "0123456789abcdef" for c in revision_sha):
        raise ValueError(f"revision must be a lowercase hex commit sha, got {revision_sha!r}")
    return raw_root() / f"{repo_id.replace('/', '__')}@{revision_sha}"


def safe_repo_path(path: str) -> str:
    """Return ``path`` if it is a plain relative POSIX path; raise ValueError otherwise.

    Upstream listings are untrusted input: absolute paths, backslashes, NUL
    and empty, ``.`` or ``..`` components are rejected.
    """
    if not isinstance(path, str) or not path or "\x00" in path or "\\" in path:
        raise ValueError(f"unsafe repository path: {path!r}")
    if PurePosixPath(path).is_absolute() or any(
        part in ("", ".", "..") for part in path.split("/")
    ):
        raise ValueError(f"unsafe repository path: {path!r}")
    return path


def raw_file(repo_id: str, revision_sha: str, repo_path: str) -> Path:
    """Location of an upstream file in the raw cache, guaranteed inside it."""
    base = raw_cache_dir(repo_id, revision_sha)
    p = base / safe_repo_path(repo_path)
    if not p.resolve().is_relative_to(base.resolve()):
        raise ValueError(f"repository path escapes the raw cache: {repo_path!r}")
    return p


def _require_auth(auth: object) -> None:
    if not isinstance(auth, HoldoutAuthorization):
        raise HoldoutAccessError("holdout access requires a HoldoutAuthorization")


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def check_readable(
    path: Path | str,
    auth: HoldoutAuthorization | None = None,
    *,
    raw_reader: bool = False,
) -> Path:
    """Resolve ``path`` (following symlinks) and refuse guarded locations.

    - ``data/holdout/**`` needs ``auth``.
    - ``data/raw/**`` is readable only by ``r0.rawread`` (``raw_reader=True``),
      which enforces the timestamp partition rule on rows.
    """
    given = Path(os.path.abspath(Path(path).expanduser()))
    resolved = given.resolve()
    root = data_root()
    # Compare both the literal and the symlink-resolved path with both the
    # literal and the resolved guarded roots, so a symlinked file *or* a
    # symlinked data/holdout or data/raw directory cannot bypass the guard.
    holdout = (root / "holdout", (root / "holdout").resolve())
    raw = (raw_root(), raw_root().resolve())
    if any(_within(p, h) for p in (given, resolved) for h in holdout):
        _require_auth(auth)
    if not raw_reader and any(_within(p, r) for p in (given, resolved) for r in raw):
        raise RawCacheAccessError(f"raw cache rows must be read through r0.rawread: {resolved}")
    return resolved
