#!/usr/bin/env python3
"""Simple local server for the CT Book Access viz. Run from the viz/ directory."""
import http.server, socketserver, os, webbrowser

PORT = 8080
os.chdir(os.path.dirname(os.path.abspath(__file__)))

Handler = http.server.SimpleHTTPRequestHandler
Handler.extensions_map = {**Handler.extensions_map, '.geojson': 'application/json'}

print(f"Serving at http://localhost:{PORT}/app.html")
print("Press Ctrl+C to stop.\n")

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    webbrowser.open(f"http://localhost:{PORT}/app.html")
    httpd.serve_forever()
