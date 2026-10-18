# Copyright (c) 2026 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0

"""Golden files for the gateway to Django contract.

A golden file lists the steps of one device scenario and the HTTP requests
the gateway sent to Django for each step. ``contract/gateway/README.rst``
describes the format and the placeholders.
"""

from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ENDPOINT = "<endpoint>"
TIME = "<time>"
TIMESTAMP = "<timestamp>"

_ISO_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?Z$")


def normalize(value: object, endpoint: str) -> object:
    """Replace the volatile parts of a recorded request body with placeholders."""

    if isinstance(value, dict):
        if value.get("type") == "TIME" and "value" in value:
            value = {**value, "value": TIME}
        return {
            (TIMESTAMP if _ISO_TIMESTAMP.match(key) else key): normalize(item, endpoint)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [normalize(item, endpoint) for item in value]
    if value == endpoint:
        return ENDPOINT
    if isinstance(value, str) and _ISO_TIMESTAMP.match(value):
        return TIMESTAMP
    return value


@dataclass
class Recorded:
    method: str
    path: str
    body: object
    status: int

    def normalized(self, endpoint: str) -> dict:
        return {"method": self.method, "path": self.path, "body": normalize(self.body, endpoint)}


@dataclass
class RecordingSink:
    """HTTP server that stands in for Django and records each request.

    ``status`` is the response code for every request, so a test can also
    simulate a failing Django.
    """

    host: str = "0.0.0.0"
    port: int = 0
    status: int = 201
    requests: list[Recorded] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._changed = threading.Condition()
        sink = self

        class Handler(BaseHTTPRequestHandler):
            def _record(self) -> None:
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length).decode() if length else ""
                body = json.loads(raw) if raw else None
                status = sink.status
                with sink._changed:
                    sink.requests.append(Recorded(self.command, self.path, body, status))
                    sink._changed.notify_all()
                self.send_response(status)
                self.send_header("Content-Length", "0")
                self.end_headers()

            do_POST = do_PUT = _record

            def log_message(self, format, *args):
                return

        self._server = ThreadingHTTPServer((self.host, self.port), Handler)
        self.port = self._server.server_address[1]
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    def for_endpoint(self, endpoint: str) -> list[Recorded]:
        with self._changed:
            return [r for r in self.requests if _endpoint_of(r.body) == endpoint]

    def wait_settled(
        self,
        endpoint: str,
        *,
        known: int,
        timeout: float,
        quiet: float = 1.5,
        require: bool = True,
    ) -> list[Recorded]:
        """Wait for a request after the first ``known`` ones, then for ``quiet`` seconds
        without another request. Return all requests of ``endpoint``. With
        ``require=False``, only wait for the quiet period."""

        with self._changed:
            if require and not self._changed.wait_for(
                lambda: len(self.for_endpoint(endpoint)) > known, timeout=timeout
            ):
                raise TimeoutError(f"no gateway request for {endpoint} within {timeout}s")
            while self._changed.wait(quiet):
                pass
            return self.for_endpoint(endpoint)

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()


def _endpoint_of(body: object) -> str | None:
    return body.get("ep") if isinstance(body, dict) else None


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def dump(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2) + "\n")
