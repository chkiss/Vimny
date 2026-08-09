#!/usr/bin/env python3
# Vimny — a Vim-teaching dungeon crawler.
# Copyright (C) 2026 Chas Kissick
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Serve web/ with the two headers the browser build cannot live without.

`python3 -m http.server` will NOT do: without COOP and COEP the page is not
cross-origin isolated, SharedArrayBuffer does not exist, and the worker has no
way to block on input. That is the single most likely reason a deployment of
this looks broken, so it is worth naming twice.

    ./web/serve.py [port]
"""
import functools
import http.server
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        '.wasm': 'application/wasm',
        '.mjs':  'text/javascript',
        '.js':   'text/javascript',
        '.json': 'application/json',
        '.whl':  'application/octet-stream',
        '.woff2': 'font/woff2',
    }

    def end_headers(self):
        self.send_header('Cross-Origin-Opener-Policy', 'same-origin')
        self.send_header('Cross-Origin-Embedder-Policy', 'require-corp')
        self.send_header('Cache-Control', 'no-store')   # dev server: always fresh
        super().end_headers()

    def log_message(self, fmt, *args):
        if '404' in (fmt % args):
            super().log_message(fmt, *args)


def main() -> int:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    if not os.path.isdir(os.path.join(ROOT, 'vendor', 'pyodide')):
        print('web/vendor is empty — run ./web/build.sh first.', file=sys.stderr)
        return 1
    # THREADING, not the plain server: the page and the worker fetch at the same
    # time — index.html is still pulling xterm.js while the worker asks for 9 MB
    # of wasm — and a one-request-at-a-time server can sit on the second until
    # the first finishes, which shows up as a page that boots to a blank screen.
    http.server.ThreadingHTTPServer.allow_reuse_address = True
    handler = functools.partial(Handler, directory=ROOT)
    with http.server.ThreadingHTTPServer(('', port), handler) as httpd:
        print(f'Vimny on http://localhost:{port}  (Ctrl-C to stop)')
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
