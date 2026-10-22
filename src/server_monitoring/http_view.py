from __future__ import annotations

from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
from typing import Any


def _build_html(report_text: str, json_available: bool, report_path: str, route: str) -> str:
    json_link = ""
    if json_available:
        json_link = f'<p><a href="{escape(route)}/json">View JSON report</a></p>'

    return (
        "<!doctype html>"
        "<html><head>"
        "<meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<meta http-equiv='refresh' content='30'>"
        "<title>Server Report</title>"
        "<style>"
        "body{font-family:Segoe UI,Arial,sans-serif;margin:20px;line-height:1.35;}"
        "h1{margin-bottom:6px;}"
        "p{margin:6px 0 10px 0;color:#444;}"
        "pre{background:#111;color:#eee;padding:14px;border-radius:8px;overflow:auto;}"
        "a{color:#0b63ce;text-decoration:none;}a:hover{text-decoration:underline;}"
        "</style></head><body>"
        "<h1>Server Monitoring Report</h1>"
        f"<p>Source file: {escape(report_path)} | Auto-refresh: 30s</p>"
        f"{json_link}"
        f"<pre>{escape(report_text)}</pre>"
        "</body></html>"
    )


def start_http_report_server(http_config: dict[str, Any], report_path: str) -> None:
    host = str(http_config["host"])
    port = int(http_config["port"])
    route = str(http_config["path"]).rstrip("/") or "/serverReport"

    text_path = Path(report_path)
    json_path = text_path.with_suffix(".json")

    class ReportHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            request_path = self.path.split("?", 1)[0]
            if request_path == route or request_path == route + "/":
                if not text_path.exists():
                    self.send_response(404)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(b"Report not generated yet.")
                    return

                report_text = text_path.read_text(encoding="utf-8", errors="replace")
                html_doc = _build_html(
                    report_text=report_text,
                    json_available=json_path.exists(),
                    report_path=str(text_path),
                    route=route,
                )
                data = html_doc.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return

            if request_path == route + "/json":
                if not json_path.exists():
                    self.send_response(404)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(b"JSON report not generated yet.")
                    return

                payload = json_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return

            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Not Found")

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer((host, port), ReportHandler)

    thread = threading.Thread(target=server.serve_forever, name="server-monitor-http", daemon=True)
    thread.start()
