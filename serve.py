#!/usr/bin/env python3
"""Local dev server that behaves like Cloudflare Pages.

    py serve.py [port]        # default 8081

Plain `python -m http.server` does NOT match production, which matters here:

  * Pages serves /articles from newsletter.html. A plain server 404s it, so every
    internal link looks broken locally even though it works live.
  * Pages 308-redirects /articles.html to /articles. Links must use the
    extensionless form; this makes the old form behave locally as it does live.
  * Pages serves 404.html, with a 404 status, for anything unmatched. A plain server
    sends its own bare error page, so the real 404 page can never be checked.

Static files are still served straight off disk, so this is only a router.
"""

import os
import sys
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlsplit


class PagesHandler(SimpleHTTPRequestHandler):
    def send_head(self):
        path = urlsplit(self.path).path

        # /articles.html -> 308 /articles   ·   /index.html -> 308 /
        if path.endswith(".html") and os.path.basename(path) != "404.html":
            target = path[: -len("index.html")] if path.endswith("/index.html") else path[: -len(".html")]
            if path == "/index.html":
                target = "/"
            self.send_response(308)
            self.send_header("Location", target)
            self.end_headers()
            return None

        local = self.translate_path(self.path)

        # A directory serves its index.html; a bare path tries <path>.html.
        if os.path.isdir(local):
            if os.path.isfile(os.path.join(local, "index.html")):
                self.path = path.rstrip("/") + "/index.html"
        elif not os.path.isfile(local) and os.path.isfile(local + ".html"):
            self.path = path + ".html"

        if not os.path.isfile(self.translate_path(self.path)):
            return self.send_404()

        return super().send_head()

    def send_404(self):
        page = os.path.join(os.getcwd(), "404.html")
        if not os.path.isfile(page):
            self.send_error(404, "Not Found")
            return None
        body = open(page, "rb").read()
        self.send_response(404)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command == "HEAD":
            return None
        self.wfile.write(body)
        return None


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8081
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    handler = partial(PagesHandler, directory=os.getcwd())
    # Threaded with daemon threads: a browser keep-alive connection would otherwise
    # block the single-threaded server inside a socket read, and Ctrl-C would sit
    # unprocessed until that connection timed out.
    ThreadingHTTPServer.daemon_threads = True
    print(f"http://localhost:{port}  (Cloudflare Pages routing: extensionless URLs, real 404s)")
    try:
        ThreadingHTTPServer(("", port), handler).serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
