from __future__ import annotations

import hashlib
import io
import stat

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from conftest import B

from r0.hub import HubClient, HubError, RemoteFile, next_link
from r0.rawread import Scope, read_footer, read_rows

REPO, SHA = "Owner/Data-v1", "f" * 40


def parquet_bytes(n: int = 20_000) -> bytes:
    t = pa.table(
        {
            "block_timestamp": pa.array([B - n + i for i in range(n)], pa.int64()),
            "question": [f"q{i % 7}" for i in range(n)],
            "blob": [f"{i:08d}" * 40 for i in range(n)],
        }
    )
    buf = io.BytesIO()
    pq.write_table(t, buf, row_group_size=5000, compression="none")
    return buf.getvalue()


@pytest.fixture
def hub(fake_hub_factory):
    files = {
        "README.md": b"# card\n",
        "daily_aligned/2025-01-01.parquet": parquet_bytes(),
        "daily_aligned/2025-10-08.parquet": b"x" * 50,
        "CTF/resolutions/a b.parquet": b"y",
    }
    return fake_hub_factory(REPO, SHA, files, page_size=2)


def client(h, token=None) -> HubClient:
    return HubClient(h.endpoint, token=token, retries=1, backoff=0.0)


def test_revision_and_paginated_tree(hub):
    c = client(hub)
    assert c.resolve_revision(REPO, "main") == SHA
    files = c.list_tree(REPO, SHA)
    assert sorted(f.path for f in files) == sorted(hub.files)
    f = next(f for f in files if f.path == "README.md")
    assert f.sha256 == hashlib.sha256(b"# card\n").hexdigest() and f.size == 7
    assert sum(1 for p, _ in hub.log if "cursor=" in p) >= 2  # followed Link pages


def test_tree_requires_pinned_sha(hub):
    with pytest.raises(HubError):
        client(hub).list_tree(REPO, "main")


def test_token_is_not_forwarded_to_cdn(hub):
    c = client(hub, token="hf_secret")
    # The fake Hub is plain HTTP; treat it as the token origin for this test only.
    c._token_schemes = ("http",)
    path = "daily_aligned/2025-01-01.parquet"
    rf = RemoteFile(c, c.file_url(REPO, SHA, path), len(hub.files[path]))
    info = read_footer(rf)
    assert info.num_rows == 20_000
    auth = {p.split("?")[0].split("/")[1]: a for p, a in hub.log}
    assert auth["datasets"] == "Bearer hf_secret"
    assert auth["cdn"] is None
    assert rf.bytes_fetched < len(hub.files[path]) / 2  # footer only, not the file


def test_token_only_to_https_endpoint_host(monkeypatch):
    import urllib.request

    sent: list[tuple[str, str | None]] = []

    class Resp:
        status, headers = 200, {}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, *a):
            return b"{}"

    def fake_urlopen(req, timeout=None):
        sent.append((req.full_url, req.unredirected_hdrs.get("Authorization")))
        return Resp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    c = HubClient("https://huggingface.co", token="hf_secret", retries=0)
    for url in (
        "https://huggingface.co/api/x",
        "https://evil.example/api/x",
        "http://huggingface.co/api/x",
    ):
        c._open(url)
    assert sent == [
        ("https://huggingface.co/api/x", "Bearer hf_secret"),
        ("https://evil.example/api/x", None),
        ("http://huggingface.co/api/x", None),
    ]
    assert HubClient("http://127.0.0.1:1", token="t")._origin == ("http", "127.0.0.1:1")


def test_cross_origin_pagination_link_is_refused(fake_hub_factory):
    h = fake_hub_factory(REPO, SHA, {"a": b"1", "b": b"2", "c": b"3"}, page_size=1)
    c = client(h)
    c._origin = ("http", "other.example:80")
    with pytest.raises(HubError):
        c.list_tree(REPO, SHA)


@pytest.mark.parametrize("bad", ["../x.parquet", "/abs/x.parquet", "a/../../x", "a//b", "a\\b"])
def test_unsafe_upstream_paths_are_rejected(fake_hub_factory, bad):
    h = fake_hub_factory(REPO, SHA, {bad: b"1"})
    with pytest.raises(HubError, match="unsafe repository path"):
        client(h).list_tree(REPO, SHA)


def test_remote_projected_pre_holdout_read(hub):
    c = client(hub)
    path = "daily_aligned/2025-01-01.parquet"
    rf = RemoteFile(c, c.file_url(REPO, SHA, path), len(hub.files[path]))
    df, _ = read_rows(rf, ["question"], ts_column="block_timestamp", scope=Scope.PRE_HOLDOUT)
    assert df.height == 20_000 and df.columns == ["question", "block_timestamp"]
    assert rf.bytes_fetched < len(hub.files[path]) / 2  # the wide "blob" column was not read


def test_quoted_paths(hub):
    c = client(hub)
    url = c.file_url(REPO, SHA, "CTF/resolutions/a b.parquet")
    assert url.endswith("/resolve/" + SHA + "/CTF/resolutions/a%20b.parquet")
    assert RemoteFile(c, url, 1).read(1) == b"y"


def test_server_ignoring_range_is_refused(fake_hub_factory):
    h = fake_hub_factory(REPO, SHA, {"f.parquet": b"z" * 10}, ignore_range=True)
    c = client(h)
    with pytest.raises(HubError, match="ignored the byte range"):
        RemoteFile(c, c.file_url(REPO, SHA, "f.parquet"), 10).read(4)


def _no_temp_files(d):
    return not any(p.name.endswith(".part") for p in d.rglob("*"))


def test_download_verifies_and_is_read_only(hub, tmp_path):
    c = client(hub)
    cache = tmp_path / "cache"
    data = hub.files["daily_aligned/2025-10-08.parquet"]
    dest = cache / "x.parquet"
    url = c.file_url(REPO, SHA, "daily_aligned/2025-10-08.parquet")
    got = c.download(url, dest, len(data), hashlib.sha256(data).hexdigest(), root=cache)
    assert got == hashlib.sha256(data).hexdigest()
    assert not (dest.stat().st_mode & stat.S_IWUSR)
    assert c.download(url, dest, len(data), got, root=cache) == got  # existing, verified, kept
    bad = cache / "bad.parquet"
    with pytest.raises(HubError, match="verification failed"):
        c.download(url, bad, len(data), "0" * 64, root=cache)
    assert not bad.exists() and _no_temp_files(cache)
    with pytest.raises(HubError, match="does not match"):
        c.download(url, dest, len(data), "0" * 64, root=cache)
    # a manifest size that disagrees with the bytes fails even when the hash matches
    other = cache / "size.parquet"
    with pytest.raises(HubError, match="verification failed"):
        c.download(url, other, len(data) + 1, hashlib.sha256(data).hexdigest(), root=cache)
    assert not other.exists() and _no_temp_files(cache)


def test_download_without_lfs_hash_uses_git_blob_sha1(hub, tmp_path):
    c = client(hub)
    data = hub.files["README.md"]
    url = c.file_url(REPO, SHA, "README.md")
    oid = hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()
    with pytest.raises(HubError, match="no usable integrity metadata"):
        c.download(url, tmp_path / "r0.md", len(data), None, None, root=tmp_path)
    for size, git_oid in ((len(data) + 1, oid), (len(data), "0" * 40)):
        d = tmp_path / f"r{size}{git_oid[:2]}.md"
        with pytest.raises(HubError, match="verification failed"):
            c.download(url, d, size, None, git_oid, root=tmp_path)
        assert not d.exists() and _no_temp_files(tmp_path)
    got = c.download(url, tmp_path / "ok.md", len(data), None, oid, root=tmp_path)
    assert got == hashlib.sha256(data).hexdigest()


# --- Codex finding 2: secure temporary files and containment -----------------


def _outside_target(tmp_path):
    out = tmp_path / "outside" / "victim.bin"
    out.parent.mkdir()
    out.write_bytes(b"precious")
    out.chmod(0o640)
    return out


def _unchanged(out):
    return out.read_bytes() == b"precious" and stat.S_IMODE(out.stat().st_mode) == 0o640


def test_preexisting_part_symlink_cannot_redirect_the_write(hub, tmp_path):
    import os

    c = client(hub)
    cache = tmp_path / "cache"
    cache.mkdir()
    out = _outside_target(tmp_path)
    data = hub.files["README.md"]
    dest = cache / "README.md"
    os.symlink(out, cache / "README.md.part")  # the old predictable temp name
    got = c.download(
        c.file_url(REPO, SHA, "README.md"),
        dest,
        len(data),
        hashlib.sha256(data).hexdigest(),
        root=cache,
    )
    assert got == hashlib.sha256(data).hexdigest() and dest.read_bytes() == data
    assert not dest.is_symlink() and _unchanged(out)
    assert (cache / "README.md.part").is_symlink()  # left untouched, never written through


def test_destination_symlink_is_refused(hub, tmp_path):
    import os

    c = client(hub)
    cache = tmp_path / "cache"
    cache.mkdir()
    out = _outside_target(tmp_path)
    os.symlink(out, cache / "README.md")
    data = hub.files["README.md"]
    with pytest.raises(HubError, match="symlink"):
        c.download(
            c.file_url(REPO, SHA, "README.md"),
            cache / "README.md",
            len(data),
            hashlib.sha256(data).hexdigest(),
            root=cache,
        )
    assert _unchanged(out) and _no_temp_files(cache)


def test_symlinked_directory_inside_cache_is_refused(hub, tmp_path):
    import os

    c = client(hub)
    cache = tmp_path / "cache"
    cache.mkdir()
    out = _outside_target(tmp_path)
    os.symlink(out.parent, cache / "daily_aligned")  # escape through a directory link
    data = hub.files["daily_aligned/2025-10-08.parquet"]
    with pytest.raises(HubError, match="symlink"):
        c.download(
            c.file_url(REPO, SHA, "daily_aligned/2025-10-08.parquet"),
            cache / "daily_aligned" / "2025-10-08.parquet",
            len(data),
            hashlib.sha256(data).hexdigest(),
            root=cache,
        )
    assert sorted(p.name for p in out.parent.iterdir()) == ["victim.bin"] and _unchanged(out)


def test_destination_outside_root_is_refused(hub, tmp_path):
    c = client(hub)
    data = hub.files["README.md"]
    with pytest.raises(HubError, match="outside the cache"):
        c.download(
            c.file_url(REPO, SHA, "README.md"),
            tmp_path / "elsewhere" / "README.md",
            len(data),
            hashlib.sha256(data).hexdigest(),
            root=tmp_path / "cache",
        )


def test_retry_on_503(fake_hub_factory):
    h = fake_hub_factory(REPO, SHA, {"a": b"1"}, fail_first=1)
    assert client(h).resolve_revision(REPO, "main") == SHA


def test_next_link():
    assert (
        next_link('<https://h/x?cursor=2>; rel="next", <https://h/y>; rel="prev"')
        == "https://h/x?cursor=2"
    )
    assert next_link(None) is None and next_link('<https://h/y>; rel="prev"') is None
