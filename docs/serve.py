#!/usr/bin/env python3
"""
Loan portal dev server.

Serves static files AND proxies bucket uploads to Orchestrator server-side,
avoiding CORS restrictions on both the OData /GetWriteUri endpoint and
the Azure Blob Storage PUT (both are blocked from the browser on UiPath Cloud).

The /api/upload endpoint:
  1. Calls Orchestrator GetWriteUri server-to-server (no CORS issue)
  2. Parses the {Uri, Verb, Headers:{Keys, Values}} response
  3. PUTs the file to the Azure SAS URL with the correct headers (no auth — SAS handles it)
  4. Returns {"path": filename} for the portal to include in the trigger payload

Usage:
    cd docs && python3 serve.py
"""

import http.server
import json
import os
import urllib.error
import urllib.parse
import urllib.request

ORCHESTRATOR_BASE = "https://cloud.uipath.com/courswvdqnod/DefaultTenant/orchestrator_"
BUCKET_ID         = "168284"
FOLDER_ID         = "7201517"  # Orchestrator → Shared folder → URL fid=XXXXX
PORT              = 8080


class Handler(http.server.SimpleHTTPRequestHandler):

    # ── CORS preflight (for same-origin calls to /api/*) ──────────────────
    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        super().do_GET()

    def do_POST(self):
        if self.path == "/api/upload":
            self._handle_upload()
        else:
            self.send_error(404)

    # ── Upload handler ─────────────────────────────────────────────────────
    def _handle_upload(self):
        auth        = self.headers.get("Authorization", "")
        folder_path = self.headers.get("X-UIPATH-OrganizationUnitPath", "Shared")
        filename    = self.headers.get("X-Filename", "document.pdf")
        length      = int(self.headers.get("Content-Length", 0))
        file_bytes  = self.rfile.read(length)

        # Step 1 — GetWriteUri (server-side, no CORS)
        try:
            write_uri_data = self._get_write_uri(filename, auth, folder_path)
        except urllib.error.HTTPError as exc:
            body = exc.read()
            print(f"[serve] GetWriteUri {exc.code}: {body.decode(errors='replace')}")
            self._respond(exc.code, body)
            return
        except Exception as exc:
            print(f"[serve] GetWriteUri error: {exc}")
            self._json_error(502, f"GetWriteUri failed: {exc}")
            return

        # Step 2 — PUT to Azure Blob using the SAS URL
        try:
            self._blob_put(write_uri_data, file_bytes)
        except urllib.error.HTTPError as exc:
            self._json_error(
                exc.code,
                f"Blob upload failed: HTTP {exc.code} — {exc.read().decode(errors='replace')}",
            )
            return
        except Exception as exc:
            self._json_error(502, f"Blob upload failed: {exc}")
            return

        self._respond(200, json.dumps({"path": filename}).encode())

    # ── Helpers ────────────────────────────────────────────────────────────
    def _get_write_uri(self, filename, auth, folder_path):
        url = (
            f"{ORCHESTRATOR_BASE}/odata/Buckets({BUCKET_ID})"
            f"/UiPath.Server.Configuration.OData.GetWriteUri"
            f"?path={urllib.parse.quote(filename, safe='')}"
            f"&contentType=application%2Fpdf"
        )
        req = urllib.request.Request(url, headers={
            "Authorization": auth,
            "X-UIPATH-OrganizationUnitId": FOLDER_ID,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())

    def _blob_put(self, write_uri_data, file_bytes):
        uri  = write_uri_data["Uri"]
        verb = write_uri_data.get("Verb", "PUT")

        # Build headers from parallel Keys/Values arrays (UiPath API format)
        raw     = write_uri_data.get("Headers") or {}
        headers = dict(zip(raw.get("Keys", []), raw.get("Values", [])))
        headers["Content-Type"] = "application/pdf"
        # No Authorization header — auth is embedded in the SAS URL

        req = urllib.request.Request(uri, data=file_bytes, method=verb, headers=headers)
        with urllib.request.urlopen(req):
            pass

    def _respond(self, status, body_bytes):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self._cors()
        self.end_headers()
        self.wfile.write(body_bytes)

    def _json_error(self, status, message):
        self._respond(status, json.dumps({"error": message}).encode())

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Authorization, Content-Type, X-UIPATH-OrganizationUnitPath, X-Filename",
        )

    def log_message(self, fmt, *args):
        print(f"[serve] {self.address_string()} – {fmt % args}")


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    print(f"Loan portal running on http://localhost:{PORT}")
    http.server.HTTPServer(("", PORT), Handler).serve_forever()
