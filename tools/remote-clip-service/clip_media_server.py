#!/usr/bin/env python3
"""Read-only HTTP server for Kling reference clips.

Upload and deletion are deliberately kept on SSH.  This process only exposes
opaque MP4 paths and never accepts write requests.
"""

from __future__ import annotations

import argparse
import mimetypes
import os
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit


SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,159}$")


def safe_root(value: str) -> Path:
    return Path(value).expanduser().resolve()


class ClipHandler(BaseHTTPRequestHandler):
    server_version = "SHIYIN-Clip/1.0"

    def _send_error(self, status: int, message: str = "Not Found") -> None:
        body = (message + "\n").encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _resolve_file(self) -> Path | None:
        parsed = urlsplit(self.path)
        parts = [unquote(item) for item in parsed.path.split("/") if item]
        if len(parts) != 4 or parts[0] != "clip" or not parts[3].lower().endswith(".mp4"):
            return None
        account, canvas, clip_file = parts[1:]
        clip = clip_file[:-4]
        if not all(SAFE.fullmatch(value) for value in (account, canvas, clip)):
            return None
        root = safe_root(self.server.clip_root)  # type: ignore[attr-defined]
        target = (root / account / canvas / f"{clip}.mp4").resolve()
        try:
            target.relative_to(root)
        except ValueError:
            return None
        return target if target.is_file() else None

    def _serve(self) -> None:
        target = self._resolve_file()
        if target is None:
            self._send_error(HTTPStatus.NOT_FOUND)
            return
        size = target.stat().st_size
        start = 0
        end = size - 1
        range_header = self.headers.get("Range", "").strip()
        if range_header:
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header)
            if not match:
                self._send_error(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE, "Invalid Range")
                return
            raw_start, raw_end = match.groups()
            if raw_start:
                start = int(raw_start)
                end = int(raw_end) if raw_end else end
            else:
                suffix = int(raw_end or 0)
                start = max(0, size - suffix)
            if start >= size or start > end:
                self._send_error(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE, "Invalid Range")
                return
            end = min(end, size - 1)
        length = end - start + 1
        status = HTTPStatus.PARTIAL_CONTENT if range_header else HTTPStatus.OK
        self.send_response(status)
        self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "video/mp4")
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "public, max-age=3600")
        if range_header:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        if self.command == "HEAD":
            return
        with target.open("rb") as stream:
            stream.seek(start)
            remaining = length
            while remaining:
                chunk = stream.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def do_GET(self) -> None:  # noqa: N802
        self._serve()

    def do_HEAD(self) -> None:  # noqa: N802
        self._serve()

    def do_POST(self) -> None:  # noqa: N802
        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Read-only media service")

    def do_DELETE(self) -> None:  # noqa: N802
        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Read-only media service")

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=os.getenv("CLIPDATA_ROOT", "/opt/clipdata"))
    parser.add_argument("--host", default=os.getenv("CLIPDATA_BIND", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("CLIPDATA_PORT", "18080")))
    args = parser.parse_args()
    root = safe_root(args.root)
    root.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((args.host, args.port), ClipHandler)
    server.clip_root = root  # type: ignore[attr-defined]
    print(f"clip media server listening on {args.host}:{args.port}, root={root}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
