"""Serve the offline training suite with HTTP byte-range support for video seeking."""
from __future__ import annotations

import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
import re
from typing import BinaryIO


RANGE_PATTERN = re.compile(r"^bytes=(\d*)-(\d*)$")


class RangeRequestHandler(SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def send_head(self) -> BinaryIO | None:
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            return super().send_head()

        content_type = self.guess_type(path)
        try:
            source = open(path, "rb")
        except OSError:
            self.send_error(404, "File not found")
            return None

        stat = os.fstat(source.fileno())
        size = stat.st_size
        byte_range = self.headers.get("Range")
        self._range: tuple[int, int] | None = None

        if byte_range:
            match = RANGE_PATTERN.fullmatch(byte_range.strip())
            if not match or "," in byte_range:
                source.close()
                self.send_error(400, "Invalid byte range")
                return None
            first, last = match.groups()
            if not first:
                length = int(last or 0)
                start = max(0, size - length)
                end = size - 1
            else:
                start = int(first)
                end = min(int(last), size - 1) if last else size - 1
            if start >= size or start > end:
                source.close()
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return None
            self._range = (start, end)
            source.seek(start)
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            content_length = end - start + 1
        else:
            self.send_response(200)
            content_length = size

        self.send_header("Content-Type", content_type)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(content_length))
        self.send_header("Last-Modified", self.date_time_string(stat.st_mtime))
        self.end_headers()
        return source

    def copyfile(self, source: BinaryIO, outputfile: BinaryIO) -> None:
        if not self._range:
            return super().copyfile(source, outputfile)
        remaining = self._range[1] - self._range[0] + 1
        while remaining:
            chunk = source.read(min(64 * 1024, remaining))
            if not chunk:
                break
            outputfile.write(chunk)
            remaining -= len(chunk)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", required=True)
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    handler = lambda *items, **kwargs: RangeRequestHandler(  # noqa: E731
        *items, directory=args.directory, **kwargs
    )
    server = ThreadingHTTPServer((args.bind, args.port), handler)
    print(f"Serving {args.directory} on {args.bind}:{args.port} with byte ranges", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
