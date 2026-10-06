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


def test_download_verifies_and_is_read_only(hub, tmp_path):
    c = client(hub)
    data = hub.files["daily_aligned/2025-10-08.parquet"]
    dest = tmp_path / "cache" / "x.parquet"
    url = c.file_url(REPO, SHA, "daily_aligned/2025-10-08.parquet")
    got = c.download(url, dest, len(data), hashlib.sha256(data).hexdigest())
    assert got == hashlib.sha256(data).hexdigest()
    assert not (dest.stat().st_mode & stat.S_IWUSR)
    assert c.download(url, dest, len(data), got) == got  # existing, verified, kept
    bad = tmp_path / "cache" / "bad.parquet"
    with pytest.raises(HubError, match="verification failed"):
        c.download(url, bad, len(data), "0" * 64)
    assert not bad.exists() and not bad.with_name("bad.parquet.part").exists()
    with pytest.raises(HubError, match="does not match"):
        c.download(url, dest, len(data), "0" * 64)
    # a manifest size that disagrees with the bytes fails even when the hash matches
    other = tmp_path / "cache" / "size.parquet"
    with pytest.raises(HubError, match="verification failed"):
        c.download(url, other, len(data) + 1, hashlib.sha256(data).hexdigest())
    assert not other.exists()


def test_download_without_lfs_hash_uses_git_blob_sha1(hub, tmp_path):
    c = client(hub)
    data = hub.files["README.md"]
    url = c.file_url(REPO, SHA, "README.md")
    oid = hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()
    with pytest.raises(HubError, match="no upstream hash"):
        c.download(url, tmp_path / "r0.md", len(data), None, None)
    for size, git_oid in ((len(data) + 1, oid), (len(data), "0" * 40)):
        d = tmp_path / f"r{size}{git_oid[:2]}.md"
        with pytest.raises(HubError, match="verification failed"):
            c.download(url, d, size, None, git_oid)
        assert not d.exists() and not d.with_name(d.name + ".part").exists()
    got = c.download(url, tmp_path / "ok.md", len(data), None, oid)
    assert got == hashlib.sha256(data).hexdigest()


def test_retry_on_503(fake_hub_factory):
    h = fake_hub_factory(REPO, SHA, {"a": b"1"}, fail_first=1)
    assert client(h).resolve_revision(REPO, "main") == SHA


def test_next_link():
    assert (
        next_link('<https://h/x?cursor=2>; rel="next", <https://h/y>; rel="prev"')
        == "https://h/x?cursor=2"
    )
    assert next_link(None) is None and next_link('<https://h/y>; rel="prev"') is None
