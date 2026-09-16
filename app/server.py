import concurrent.futures
import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from app.config import load_config, save_config
from app.scraper import fetch_all_characters, fetch_dungeon, fetch_hero_details_html
from app.template import build_html

_cache_data = None
_cache_time = 0
CACHE_TTL = 300  # 5 minutes


class TrackerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

        parsed_url = urlparse(self.path)
        if parsed_url.path == "/api/config":
            config = load_config()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(config).encode("utf-8"))
            return

        global _cache_data, _cache_time
        parsed_url = urlparse(self.path)
        qs = parse_qs(parsed_url.query)
        selected_team = qs.get("team", [None])[0]
        force_refresh = qs.get("force_refresh", [None])[0] == "true"

        now = time.time()
        if force_refresh or _cache_data is None or (now - _cache_time > CACHE_TTL):
            print("[*] Fetching fresh character data from Fellows.gg...")
            _cache_data = fetch_all_characters()
            _cache_time = now
        else:
            print(
                f"[*] Using cached character data ({(CACHE_TTL - (now - _cache_time)):.0f}s left in cache)..."
            )

        html = build_html(_cache_data, selected_team)

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def do_POST(self):
        if self.path == "/api/team-dungeons":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            try:
                selections = json.loads(body)
            except Exception:
                selections = {}

            config = load_config()
            characters = config.get("characters", [])
            selected_chars = [c for c in characters if selections.get(c["slug"])]
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = [
                    executor.submit(fetch_dungeon, c, selections.get(c["slug"]))
                    for c in selected_chars
                ]
                results = [f.result() for f in futures]

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(results).encode("utf-8"))

        elif self.path == "/api/hero-details":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            try:
                data = json.loads(body)
            except Exception:
                data = {}

            slug = data.get("slug")
            hero = data.get("hero")

            config = load_config()
            chars = config.get("characters", [])
            char = next((c for c in chars if c["slug"] == slug), None)

            html_out = ""
            if char and hero:
                html_out = fetch_hero_details_html(char, hero)

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"html": html_out}).encode("utf-8"))

        elif self.path == "/api/config":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            try:
                new_cfg = json.loads(body)
                save_config(new_cfg)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"ok"}')
            except Exception as e:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(str(e).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")


def main():
    port = 8099
    server = HTTPServer(("localhost", port), TrackerHandler)
    print("=" * 51)
    print("   Fellowship Eternal Tracker")
    print("=" * 51)
    print(f"\n  Server running at:  http://localhost:{port}")
    print("  Config file:        config.json\n")
    print("  Press Ctrl+C to stop")
    print("=" * 51 + "\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    print("\nShutting down server...")
    server.server_close()


if __name__ == "__main__":
    main()
