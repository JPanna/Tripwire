"""Read-only Hugging Face Hub client (standard library only).

Endpoints, checked against the official ``huggingface_hub`` 2.1.1 client
source on 2026-10-06 (``HfApi.list_repo_tree``, ``HfApi.dataset_info``,
``hf_hub_url``, ``utils._pagination``):

- revision:  GET {endpoint}/api/datasets/{repo}/revision/{revision} -> {"sha": ...}
- tree:      GET {endpoint}/api/datasets/{repo}/tree/{revision}[/{path}]
             ?recursive=true&expand=false, paginated by a ``Link: <...>; rel="next"``
             header. File entries carry ``path``, ``size``, ``oid`` (git blob id)
             and, for LFS files, ``lfs = {"oid": <sha256>, "size", "pointerSize"}``.
- file:      GET {endpoint}/datasets/{repo}/resolve/{revision}/{path}
             (usually redirects to a CDN; byte ranges are supported).

The token (``HF_TOKEN``, optional) is sent only to the configured endpoint
host over HTTPS, as an *unredirected* header, so it is never forwarded to the
CDN host after a redirect or to any other host. It is never logged.

Upstream paths are untrusted: ``safe_repo_path`` rejects absolute paths and
``.``/``..`` components before any path is used on the local filesystem.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, urlsplit

from r0.paths import safe_repo_path as _safe_repo_path

DEFAULT_ENDPOINT = "https://huggingface.co"
DATASET_REPO = "TimeSeventeen/Polymarket-v1"
USER_AGENT = "tripwire-r0-research/0 (read-only)"
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_RETRY_STATUS = {429, 500, 502, 503, 504}


class HubError(RuntimeError):
    pass


def safe_repo_path(path: str) -> str:
    try:
        return _safe_repo_path(path)
    except ValueError as e:
        raise HubError(str(e)) from None


def git_blob_sha1(data_chunks, size: int) -> str:
    h = hashlib.sha1(f"blob {size}\0".encode())
    for c in data_chunks:
        h.update(c)
    return h.hexdigest()


@dataclass(frozen=True)
class RepoFile:
    path: str
    size: int
    git_oid: str
    sha256: str | None  # LFS sha256 if the Hub reports one


class HubClient:
    def __init__(
        self,
        endpoint: str = DEFAULT_ENDPOINT,
        token: str | None = None,
        timeout: float = 60.0,
        retries: int = 3,
        backoff: float = 2.0,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        ep = urlsplit(self.endpoint)
        self._origin = (ep.scheme, ep.netloc)
        self._token_schemes: tuple[str, ...] = ("https",)  # never send a token over plain HTTP
        self._token = token if token is not None else os.environ.get("HF_TOKEN") or None
        self.timeout = timeout
        self.retries = retries
        self.backoff = backoff

    # -- low level -------------------------------------------------------
    def _open(self, url: str, headers: dict[str, str] | None = None):
        last: Exception | None = None
        for attempt in range(self.retries + 1):
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
            u = urlsplit(url)
            if (
                self._token
                and u.scheme in self._token_schemes
                and (u.scheme, u.netloc) == self._origin
            ):
                req.add_unredirected_header("Authorization", f"Bearer {self._token}")
            try:
                return urllib.request.urlopen(req, timeout=self.timeout)
            except urllib.error.HTTPError as e:
                if e.code not in _RETRY_STATUS:
                    raise HubError(f"HTTP {e.code} for {_redact(url)}") from None
                last = e
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                last = e
            if attempt < self.retries:
                time.sleep(self.backoff * (2**attempt))
        raise HubError(f"request failed after retries: {_redact(url)}: {last}")

    def _get_json(self, url: str) -> tuple[object, str | None]:
        with self._open(url, {"Accept": "application/json"}) as r:
            body = r.read()
            link = r.headers.get("Link")
        return json.loads(body), link

    # -- API -------------------------------------------------------------
    def resolve_revision(self, repo_id: str, revision: str) -> str:
        url = f"{self.endpoint}/api/datasets/{repo_id}/revision/{quote(revision, safe='')}"
        info, _ = self._get_json(url)
        sha = info.get("sha") if isinstance(info, dict) else None
        if not isinstance(sha, str) or not _SHA_RE.match(sha):
            raise HubError(f"could not resolve revision {revision!r} to a commit sha")
        return sha

    def list_tree(self, repo_id: str, revision_sha: str, path: str = "") -> list[RepoFile]:
        if not _SHA_RE.match(revision_sha):
            raise HubError("list_tree requires a pinned 40-hex commit sha")
        sub = "/" + quote(path, safe="") if path else ""
        url: str | None = (
            f"{self.endpoint}/api/datasets/{repo_id}/tree/{revision_sha}{sub}"
            "?recursive=true&expand=false"
        )
        files: list[RepoFile] = []
        seen: set[str] = set()
        while url:
            page, link = self._get_json(url)
            if not isinstance(page, list):
                raise HubError("unexpected tree response (not a list)")
            for e in page:
                if e.get("type") != "file":
                    continue
                safe_repo_path(e["path"])
                if e["path"] in seen:
                    raise HubError(f"duplicate path in tree listing: {e['path']}")
                seen.add(e["path"])
                lfs = e.get("lfs") or None
                sha256 = lfs.get("oid") if lfs else None
                if lfs and int(lfs.get("size", e["size"])) != int(e["size"]):
                    raise HubError(f"size mismatch between tree and LFS info: {e['path']}")
                files.append(RepoFile(e["path"], int(e["size"]), e["oid"], sha256))
            url = next_link(link)
            if url is not None and (urlsplit(url).scheme, urlsplit(url).netloc) != self._origin:
                raise HubError("pagination link points to another origin; refusing")
        return files

    def file_url(self, repo_id: str, revision_sha: str, path: str) -> str:
        if not _SHA_RE.match(revision_sha):
            raise HubError("file_url requires a pinned 40-hex commit sha")
        return f"{self.endpoint}/datasets/{repo_id}/resolve/{revision_sha}/{quote(path)}"

    def open_range(self, url: str, start: int, end_inclusive: int) -> bytes:
        with self._open(url, {"Range": f"bytes={start}-{end_inclusive}"}) as r:
            if r.status != 206:
                # A 200 would stream the whole file: refuse rather than download it.
                raise HubError(f"server ignored the byte range (HTTP {r.status}); refusing")
            data = r.read()
        if len(data) != end_inclusive - start + 1:
            raise HubError("short range read")
        return data

    def download(
        self,
        url: str,
        dest: Path,
        expected_size: int,
        expected_sha256: str | None,
        expected_git_oid: str | None = None,
    ) -> str:
        """Download to ``dest`` atomically; verify size and hash; make read-only.

        Verification uses the upstream LFS SHA-256 when the listing has one,
        otherwise the git blob SHA-1 (``expected_git_oid``); at least one is
        required. Returns the SHA-256 of the file. An existing ``dest`` is
        never overwritten: it is verified and kept, or an error is raised.
        """
        if not expected_sha256 and not expected_git_oid:
            raise HubError(f"no upstream hash to verify {dest.name} against; refusing")

        def ok(n: int, sha256: str, sha1: str) -> bool:
            if n != expected_size:
                return False
            if expected_sha256:
                return sha256 == expected_sha256
            return sha1 == expected_git_oid

        if dest.exists():
            got = sha256_file(dest)
            with open(dest, "rb") as f:
                sha1 = git_blob_sha1(iter(lambda: f.read(8 << 20), b""), dest.stat().st_size)
            if not ok(dest.stat().st_size, got, sha1):
                raise HubError(f"existing cached file does not match the manifest: {dest}")
            return got
        dest.parent.mkdir(parents=True, exist_ok=True)
        part = dest.with_name(dest.name + ".part")
        h = hashlib.sha256()
        h1 = hashlib.sha1(f"blob {expected_size}\0".encode())
        n = 0
        with self._open(url) as r, open(part, "wb") as f:
            while chunk := r.read(8 << 20):
                h.update(chunk)
                h1.update(chunk)
                f.write(chunk)
                n += len(chunk)
        got = h.hexdigest()
        if not ok(n, got, h1.hexdigest()):
            part.unlink(missing_ok=True)
            raise HubError(f"download verification failed for {dest.name}")
        os.replace(part, dest)
        dest.chmod(0o444)
        return got


def next_link(link_header: str | None) -> str | None:
    if not link_header:
        return None
    for part in link_header.split(","):
        m = re.match(r'\s*<([^>]+)>\s*;\s*rel="?next"?', part.strip())
        if m:
            return m.group(1)
    return None


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8 << 20):
            h.update(chunk)
    return h.hexdigest()


def _redact(url: str) -> str:
    return re.sub(r"([?&](?:token|signature|sig|key)[^=]*=)[^&]+", r"\1<redacted>", url, flags=re.I)


class RemoteFile(io.RawIOBase):
    """Seekable read-only view of a remote file through HTTP byte ranges.

    Used for Parquet footer (schema) reads and column-projected reads without
    downloading whole files. Bytes fetched are counted in ``bytes_fetched``.
    """

    def __init__(self, client: HubClient, url: str, size: int, block: int = 1 << 16) -> None:
        super().__init__()
        self._client, self._url, self._size, self._block = client, url, size, block
        self._pos = 0
        self._cache: dict[int, bytes] = {}
        self.bytes_fetched = 0

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self._pos

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        base = {io.SEEK_SET: 0, io.SEEK_CUR: self._pos, io.SEEK_END: self._size}[whence]
        self._pos = max(0, base + offset)
        return self._pos

    def _fetch(self, start: int, end_inclusive: int) -> bytes:
        data = self._client.open_range(self._url, start, end_inclusive)
        self.bytes_fetched += len(data)
        return data

    def _block_bytes(self, i: int) -> bytes:
        if i not in self._cache:
            if len(self._cache) >= 8:
                self._cache.pop(next(iter(self._cache)))
            start = i * self._block
            self._cache[i] = self._fetch(start, min(self._size, start + self._block) - 1)
        return self._cache[i]

    def readinto(self, b) -> int:  # type: ignore[override]
        want = min(len(b), self._size - self._pos)
        if want <= 0:
            return 0
        if want >= self._block:
            data = self._fetch(self._pos, self._pos + want - 1)
        else:
            parts, pos, left = [], self._pos, want
            while left > 0:
                i, off = divmod(pos, self._block)
                chunk = self._block_bytes(i)[off : off + left]
                parts.append(chunk)
                pos += len(chunk)
                left -= len(chunk)
            data = b"".join(parts)
        b[: len(data)] = data
        self._pos += len(data)
        return len(data)
