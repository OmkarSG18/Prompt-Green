"""
PromptGreen V2 — Independent Frontend Static Server
Lightweight HTTP server serving the Green Prompt Studio and Evolution & Evaluation portal
completely decoupled from the backend FastAPI engine.

Zero external dependencies: uses Python standard library http.server.
"""

import argparse
import os
import posixpath
import sys
import urllib.parse
from http import HTTPStatus
from http.server import HTTPServer, SimpleHTTPRequestHandler

WEBSITE_DIR = os.path.abspath(os.path.dirname(__file__))


class PromptGreenFrontendHandler(SimpleHTTPRequestHandler):
    """Custom request handler mapping SPA routes to static HTML documents with directory listing strictly disabled."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEBSITE_DIR, **kwargs)

    def translate_path(self, path: str) -> str:
        """
        Safely translate a /-separated URL path to an absolute filesystem path.
        Enforces strict resolution inside WEBSITE_DIR, preventing any path traversal,
        Windows drive letter escapes (e.g. /D: or /d:), or reliance on PowerShell working directory.
        """
        # Strip query parameters and fragment identifiers
        path = path.split("?", 1)[0].split("#", 1)[0]
        # Unquote URL encoding
        try:
            path = urllib.parse.unquote(path, errors="surrogatepass")
        except UnicodeDecodeError:
            path = urllib.parse.unquote(path)
        # Normalize POSIX-style path
        path = posixpath.normpath(path)

        # Discard leading slashes and split
        words = path.split("/")
        # Filter out empty, current dir (.), parent dir (..), and Windows drive letters (e.g., 'd:', 'D:')
        safe_words = []
        for word in words:
            if not word or word in (os.curdir, os.pardir):
                continue
            # Guard against Windows drive specifiers (e.g. 'D:', 'c:', 'D:\\')
            if len(word) == 2 and word[1] == ":":
                continue
            safe_word = os.path.basename(word)
            if safe_word and safe_word not in (os.curdir, os.pardir):
                safe_words.append(safe_word)

        # Resolve strictly relative to WEBSITE_DIR
        resolved_path = WEBSITE_DIR
        for word in safe_words:
            resolved_path = os.path.join(resolved_path, word)

        # Final containment assertion: path must strictly reside within WEBSITE_DIR
        resolved_abs = os.path.abspath(resolved_path)
        try:
            if os.path.commonpath([WEBSITE_DIR, resolved_abs]) != WEBSITE_DIR:
                return os.path.join(WEBSITE_DIR, "index.html")
        except ValueError:
            # On Windows, commonpath raises ValueError if paths are on different drives
            return os.path.join(WEBSITE_DIR, "index.html")

        return resolved_abs

    def list_directory(self, path):
        """
        Strictly disable directory listing.
        Never expose filesystem directories (such as Index of D:\\) to clients.
        Returns 404 NOT FOUND.
        """
        self.send_error(HTTPStatus.NOT_FOUND, "Directory listing is disabled.")
        return None

    def do_GET(self):
        # Normalize request path (strip query parameters and trailing slashes)
        clean_path = self.path.split("?")[0].split("#")[0].rstrip("/")
        if not clean_path:
            clean_path = "/"

        # Reject path traversal or drive letter spoofing immediately with 404
        if ".." in clean_path or ":" in clean_path:
            self.send_error(HTTPStatus.NOT_FOUND, "Resource not found.")
            return

        # Custom SPA routing
        if clean_path in {"/", "/app", "/website", "/studio", "/index", "/index.html", "/about", "/v1", "/v2"}:
            self.path = "/index.html"
        elif clean_path in {"/evaluation", "/evolution", "/compare", "/evaluation.html", "/dossier"}:
            self.path = "/evaluation.html"
        elif clean_path.startswith("/api/"):
            # If API is mistakenly requested from frontend port, provide helpful JSON notice
            self.send_response(HTTPStatus.NOT_FOUND)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            err_msg = (
                b'{"error": "Frontend server only. PromptGreen API backend runs independently '
                b'at http://127.0.0.1:8000"}'
            )
            self.wfile.write(err_msg)
            return

        return super().do_GET()

    def end_headers(self):
        # Add CORS and no-cache headers for smooth local development and inspection
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def log_message(self, format, *args):
        # Clean logging format to stdout/log file
        sys.stdout.write(f"[FRONTEND] {self.address_string()} - {format % args}\n")
        sys.stdout.flush()


def run_frontend(host: str = "127.0.0.1", port: int = 8080):
    server_address = (host, port)
    httpd = HTTPServer(server_address, PromptGreenFrontendHandler)
    print(f"[READY] PromptGreen Frontend Server is online at http://{host}:{port}")
    print(f"        Serving directory: {WEBSITE_DIR}")
    print(f"        Studio:            http://{host}:{port}/")
    print(f"        Evaluation:        http://{host}:{port}/evaluation")
    print(f"        Evolution:         http://{host}:{port}/evolution")
    sys.stdout.flush()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[STOP] Shutting down frontend server cleanly...")
    finally:
        httpd.server_close()
        print("[STOP] Frontend server stopped.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PromptGreen V2 Independent Frontend Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on (default: 8080)")
    args = parser.parse_args()

    run_frontend(host=args.host, port=args.port)
