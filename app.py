"""Serve Catalog Compass locally with Python 3.11+ and no pip dependencies."""
import argparse
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from catalog_check import model
from catalog_check.catalog import profile_csv, validate_catalog, issues_csv, normalized_csv
from catalog_check.samples import SAMPLES, get_sample

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
MAX_BYTES = 2 * 1024 * 1024


class Handler(BaseHTTPRequestHandler):
    server_version = "CatalogCompass/0.1"

    def send(self, code, body, content_type="application/json; charset=utf-8", filename=None):
        if not isinstance(body, bytes):
            body = (json.dumps(body, ensure_ascii=False) if content_type.startswith("application/json") else body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(body)

    def local_request(self):
        host = self.headers.get("Host", "")
        if host not in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}:
            return False
        origin = self.headers.get("Origin")
        return not origin or origin in {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}

    def do_GET(self):
        if not self.local_request():
            self.send(403, {"error": "Use this app from its localhost address."})
            return
        path = urlparse(self.path).path
        try:
            if path == "/api/status":
                self.send(200, {"model": model.status(), "samples": SAMPLES})
            elif path.startswith("/api/samples/"):
                self.send(200, get_sample(path.rsplit("/", 1)[-1]))
            elif path in {"/", "/index.html", "/styles.css", "/app.js"}:
                file = WEB / ("index.html" if path == "/" else path[1:])
                if not file.is_file():
                    self.send(503, {"error": "The interface is being prepared."})
                    return
                content_type = {".html": "text/html", ".js": "text/javascript", ".css": "text/css"}[file.suffix]
                self.send(200, file.read_bytes(), content_type + "; charset=utf-8")
            else:
                self.send(404, {"error": "Not found."})
        except ValueError as exc:
            self.send(400, {"error": str(exc)})

    def do_POST(self):
        if not self.local_request():
            self.send(403, {"error": "Cross-origin requests are not allowed."})
            return
        if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
            self.send(415, {"error": "Send application/json."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_BYTES:
                self.send(413, {"error": "Choose a CSV smaller than 2 MB."})
                return
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict) or not isinstance(data.get("csv"), str):
                raise ValueError("A CSV text string is required.")
            csv_text = data["csv"]
            profile = profile_csv(csv_text)
            if profile["row_count"] > 5000 or len(profile["headers"]) > 100:
                raise ValueError("This prototype supports up to 5,000 records and 100 columns.")
            path = urlparse(self.path).path
            if path == "/api/profile":
                self.send(200, profile)
            elif path == "/api/map":
                self.send(200, model.suggest_mapping(profile))
            elif path in {"/api/check", "/api/export"}:
                mapping = data.get("mapping", {})
                if not isinstance(mapping, dict) or any(key not in model.FIELDS for key in mapping):
                    raise ValueError("Invalid field mapping.")
                selected = [v for v in mapping.values() if v is not None and v != ""]
                if any(not isinstance(v, str) or v not in profile["headers"] for v in selected):
                    raise ValueError("Every selected column must exist in the uploaded CSV.")
                if len(selected) != len(set(selected)):
                    raise ValueError("Use each source column at most once.")
                if not mapping.get("sku") or not mapping.get("name") or not mapping.get("regular_price"):
                    raise ValueError("Confirm the SKU, product name and regular price columns before checking.")
                options = data.get("options") or {}
                if not isinstance(options, dict):
                    raise ValueError("Invalid options.")
                result = validate_catalog(csv_text, mapping, options)
                if path == "/api/check":
                    self.send(200, result)
                elif data.get("kind") == "issues":
                    self.send(200, issues_csv(result), "text/csv; charset=utf-8", "catalog-issues.csv")
                elif data.get("kind") == "normalized":
                    self.send(200, normalized_csv(result), "text/csv; charset=utf-8", "catalog-mapped-review.csv")
                else:
                    raise ValueError("Unknown export kind.")
            else:
                self.send(404, {"error": "Not found."})
        except (ValueError, UnicodeError) as exc:
            self.send(400, {"error": str(exc)})
        except RuntimeError as exc:
            self.send(503, {"error": str(exc)})
        except Exception:
            self.send(500, {"error": "An unexpected error occurred. The source file has not been modified."})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Catalog Compass: http://127.0.0.1:{args.port}", flush=True)
    print("Your catalog stays in memory. Press Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
