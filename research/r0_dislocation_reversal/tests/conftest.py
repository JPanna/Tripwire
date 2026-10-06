"""Shared fixtures. All data is synthetic; no test touches the network or real data."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from r0.periods import PARTITION_BOUNDARY

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
B = PARTITION_BOUNDARY


@pytest.fixture
def data_root(tmp_path, monkeypatch) -> Path:
    root = tmp_path / "data"
    root.mkdir()
    monkeypatch.setenv("R0_DATA_ROOT", str(root))
    return root


def write_parquet(path: Path, table: pa.Table, row_group_size: int | None = None, **kw) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path, row_group_size=row_group_size, **kw)
    return path


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name.replace(".py", "_mod"), SCRIPTS / name)
    mod = importlib.util.module_from_spec(spec)
    import sys

    sys.path.insert(0, str(SCRIPTS))
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


class FakeHub:
    """Minimal local stand-in for the Hugging Face endpoints used by r0.hub."""

    def __init__(
        self,
        repo: str,
        sha: str,
        files: dict[str, bytes],
        page_size: int = 2,
        lfs: bool = True,
        ignore_range: bool = False,
        fail_first: int = 0,
    ) -> None:
        self.repo, self.sha, self.files = repo, sha, files
        self.page_size, self.lfs, self.ignore_range = page_size, lfs, ignore_range
        self.fail_first = fail_first
        self.log: list[tuple[str, str | None]] = []  # (path, Authorization header)
        hub = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):  # silence
                pass

            def do_GET(self):  # noqa: N802
                hub.log.append((self.path, self.headers.get("Authorization")))
                if hub.fail_first > 0:
                    hub.fail_first -= 1
                    self.send_response(503)
                    self.end_headers()
                    return
                u = urlparse(self.path)
                p = u.path
                rev_prefix = f"/api/datasets/{hub.repo}/revision/"
                tree_prefix = f"/api/datasets/{hub.repo}/tree/{hub.sha}"
                res_prefix = f"/datasets/{hub.repo}/resolve/{hub.sha}/"
                if p.startswith(rev_prefix):
                    return self._json({"sha": hub.sha, "id": hub.repo})
                if p.startswith(tree_prefix):
                    q = parse_qs(u.query)
                    assert q.get("recursive") == ["true"]
                    start = int(q.get("cursor", ["0"])[0])
                    entries = [
                        {"type": "directory", "path": "daily_aligned", "oid": "d" * 40, "size": 0}
                    ]
                    for name, data in sorted(hub.files.items()):
                        oid = hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()
                        e = {"type": "file", "path": name, "size": len(data), "oid": oid}
                        if hub.lfs:
                            e["lfs"] = {
                                "oid": hashlib.sha256(data).hexdigest(),
                                "size": len(data),
                                "pointerSize": 134,
                            }
                        entries.append(e)
                    page = entries[start : start + hub.page_size]
                    nxt = start + hub.page_size
                    link = None
                    if nxt < len(entries):
                        link = (
                            f"<http://127.0.0.1:{hub.port}{tree_prefix}?recursive=true"
                            f'&expand=false&cursor={nxt}>; rel="next"'
                        )
                    return self._json(page, link)
                if p.startswith(res_prefix):
                    name = p[len(res_prefix) :]
                    self.send_response(302)
                    self.send_header("Location", f"http://127.0.0.1:{hub.port}/cdn/{name}")
                    self.end_headers()
                    return
                if p.startswith("/cdn/"):
                    from urllib.parse import unquote

                    data = hub.files[unquote(p[5:])]
                    rng = self.headers.get("Range")
                    if rng and not hub.ignore_range:
                        a, b = rng.split("=")[1].split("-")
                        a, b = int(a), min(int(b), len(data) - 1)
                        self.send_response(206)
                        self.send_header("Content-Range", f"bytes {a}-{b}/{len(data)}")
                        self.send_header("Content-Length", str(b - a + 1))
                        self.end_headers()
                        self.wfile.write(data[a : b + 1])
                        return
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return
                self.send_response(404)
                self.end_headers()

            def _json(self, obj, link=None):
                body = json.dumps(obj).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                if link:
                    self.send_header("Link", link)
                self.end_headers()
                self.wfile.write(body)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.port = self.server.server_address[1]
        self.endpoint = f"http://127.0.0.1:{self.port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def fake_hub_factory():
    hubs: list[FakeHub] = []

    def make(*a, **kw) -> FakeHub:
        h = FakeHub(*a, **kw)
        hubs.append(h)
        return h

    yield make
    for h in hubs:
        h.close()
