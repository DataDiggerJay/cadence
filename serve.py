#!/usr/bin/env python3
"""
serve.py - Run Cadence locally with its own feed proxy.

    python3 serve.py

Serves index.html at http://localhost:8000 and proxies RSS requests
through /proxy?url=... so the browser's cross-origin rules stop being a problem
and you don't have to trust a public proxy with your feed list.

Options:
    python3 serve.py --port 9000     use a different port
    python3 serve.py --no-open       don't launch a browser

Stdlib only. Nothing leaves your machine except the feed requests themselves.
"""

import argparse
import gzip
import io
import os
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = "index.html"
TIMEOUT = 25
MAX_BYTES = 25 * 1024 * 1024          # generous: some archive feeds are large
UA = "Mozilla/5.0 (compatible; CadenceLocal/1.0; +podcast cadence analysis)"


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=HERE, **kw)

    # --- quieter logs: one line per request, no noise for static assets
    def log_message(self, fmt, *args):
        if self.path.startswith("/proxy"):
            sys.stderr.write("  %s\n" % (fmt % args))

    def end_headers(self):
        # Always serve the latest page; never let the browser reuse a cached copy.
        if not self.path.startswith("/proxy"):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        if self.path == "/":
            self.path = "/" + PAGE
        if self.path.startswith("/proxy"):
            return self.do_proxy()
        return super().do_GET()

    def do_proxy(self):
        query = urllib.parse.urlparse(self.path).query
        target = urllib.parse.parse_qs(query).get("url", [""])[0]

        if not target:
            return self.fail(400, "No url parameter given.")
        parsed = urllib.parse.urlparse(target)
        if parsed.scheme not in ("http", "https"):
            return self.fail(400, f"Only http and https are proxied, not '{parsed.scheme}'.")

        req = urllib.request.Request(target, headers={
            "User-Agent": UA,
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
            "Accept-Encoding": "gzip",
        })
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                raw = r.read(MAX_BYTES)
                if r.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
                ctype = r.headers.get("Content-Type", "application/xml")
        except urllib.error.HTTPError as e:
            return self.fail(502, f"The feed host returned HTTP {e.code} {e.reason}.")
        except urllib.error.URLError as e:
            return self.fail(502, f"Could not reach the feed host: {e.reason}.")
        except Exception as e:
            return self.fail(502, f"Request failed: {e}")

        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def fail(self, code, message):
        body = message.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


def main():
    ap = argparse.ArgumentParser(description="Serve Cadence locally with a feed proxy.")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--no-open", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(os.path.join(HERE, PAGE)):
        sys.exit(f"{PAGE} is not next to serve.py. Put both files in the same folder.")

    try:
        httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    except OSError as e:
        sys.exit(f"Port {args.port} is not available ({e}). Try: python3 serve.py --port 8080")

    url = f"http://{args.host}:{args.port}/"
    print(f"Cadence is running at {url}")
    print("The page will use this server's built-in feed proxy automatically.")
    print("Press Ctrl+C to stop.\n")
    if not args.no_open:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()