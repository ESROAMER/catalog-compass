"""Download a pinned, checksummed local Qwen runtime (Windows x64; no pip needed).

Run: python scripts/setup_model.py
The files stay in .runtime; no PATH changes, installers, API keys, or cloud calls.
Use --cpu for the smaller CPU-only runtime, or --verify-only to check installed files.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import platform
import time
from urllib.request import Request, urlopen
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime"
BUILD = "b11429"
MODEL_REPO = "Qwen/Qwen3-0.6B-GGUF"
MODEL_REVISION = "23749fefcc72300e3a2ad315e1317431b06b590a"
MODEL_FILE = "Qwen3-0.6B-Q8_0.gguf"
MODEL_SHA256 = "9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031"
MODEL_BYTES = 639446688
RUNTIME_DIGESTS = {
    "vulkan": "1bfe78ad9168b79fa02bf67f6af9f5e17a966d824d77238517f7bef12ac73b36",
    "cpu": "1283323272b04cd07905816a597a0da810918102de958f4ff6f7bbaa70ed2efe",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, path: Path, expected_sha256: str) -> None:
    if path.is_file() and sha256(path) == expected_sha256:
        print(f"Verified existing {path.name}", flush=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".part")
    # A failed download remains resumable, but is never treated as installed.
    offset = partial.stat().st_size if partial.exists() else 0
    headers = {"User-Agent": "CatalogCheck-local-model-setup"}
    if offset:
        headers["Range"] = f"bytes={offset}-"
    with urlopen(Request(url, headers=headers), timeout=180) as response:
        append = response.status == 206 and offset > 0
        downloaded = offset if append else 0
        last_progress = time.monotonic()
        with partial.open("ab" if append else "wb") as target:
            while chunk := response.read(1024 * 1024):
                target.write(chunk)
                downloaded += len(chunk)
                if time.monotonic() - last_progress > 10:
                    print(f"{path.name}: {downloaded / 1_000_000:.1f} MB", flush=True)
                    last_progress = time.monotonic()
    actual = sha256(partial)
    if actual != expected_sha256:
        # Remove only the corrupt partial file within the runtime directory.
        partial.unlink()
        raise RuntimeError(f"SHA-256 mismatch for {path.name}: {actual}")
    partial.replace(path)
    print(f"Downloaded and verified {path.name}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cpu", action="store_true", help="Use the CPU-only runtime")
    parser.add_argument("--verify-only", action="store_true", help="No downloads or extraction")
    args = parser.parse_args()
    if platform.system() != "Windows" or platform.machine().lower() not in {"amd64", "x86_64"}:
        raise SystemExit("This portable setup supports Windows x64. See the README for other platforms.")
    backend = "cpu" if args.cpu else "vulkan"
    archive_name = f"llama-{BUILD}-bin-win-{backend}-x64.zip"
    archive = RUNTIME / "downloads" / archive_name
    model = RUNTIME / "models" / MODEL_FILE
    unpacked = RUNTIME / f"llama-{BUILD}-{backend}"
    downloads = [
        (f"https://github.com/ggml-org/llama.cpp/releases/download/{BUILD}/{archive_name}?download=true", archive, RUNTIME_DIGESTS[backend]),
        (f"https://huggingface.co/{MODEL_REPO}/resolve/{MODEL_REVISION}/{MODEL_FILE}?download=true", model, MODEL_SHA256),
        (f"https://huggingface.co/{MODEL_REPO}/raw/{MODEL_REVISION}/LICENSE", RUNTIME / "licenses" / "Qwen-Apache-2.0.txt", "5de36594c10839788a8c589443a8ef9d8b8d17c65a1b5807206ae037fc36c6bd"),
        (f"https://raw.githubusercontent.com/ggml-org/llama.cpp/{BUILD}/LICENSE", RUNTIME / "licenses" / "llama-cpp-MIT.txt", "94f29bbed6a22c35b992c5c6ebf0e7c92f13b836b90f36f461c9cf2f0f1d010d"),
    ]
    if args.verify_only:
        for _, path, checksum in downloads:
            if not path.is_file() or sha256(path) != checksum:
                raise SystemExit(f"Missing or invalid: {path}")
        print("Runtime archive, model, and licenses match their pinned SHA-256 digests.")
        return
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda item: download(*item), downloads))
    unpacked.mkdir(parents=True, exist_ok=True)
    with ZipFile(archive) as bundle:
        # Keep every archive member inside this version's runtime directory.
        destination = unpacked.resolve()
        for member in bundle.infolist():
            member_path = (destination / member.filename).resolve()
            if not member_path.is_relative_to(destination):
                raise RuntimeError(f"Unsafe archive member: {member.filename}")
        bundle.extractall(unpacked)
    servers = list(unpacked.rglob("llama-server.exe"))
    if len(servers) != 1:
        raise RuntimeError("Expected one llama-server.exe in the official runtime archive")
    manifest = {
        "runtime": {
            "name": "llama.cpp", "build": BUILD, "backend": backend, "license": "MIT",
            "archive_sha256": RUNTIME_DIGESTS[backend], "archive_url": downloads[0][0],
            "digest_source": f"https://github.com/ggml-org/llama.cpp/releases/expanded_assets/{BUILD}",
            "server": str(servers[0].relative_to(ROOT)),
        },
        "model": {
            "repo": MODEL_REPO, "revision": MODEL_REVISION, "file": MODEL_FILE,
            "sha256": MODEL_SHA256, "bytes": MODEL_BYTES, "license": "Apache-2.0",
            "url": downloads[1][0], "path": str(model.relative_to(ROOT)),
            "metadata_source": f"https://huggingface.co/api/models/{MODEL_REPO}?blobs=true",
        },
        "server": {"host": "127.0.0.1", "port": 8766, "alias": "catalog-qwen", "context_size": 8192},
    }
    (RUNTIME / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("Ready. Start with: powershell -ExecutionPolicy Bypass -File scripts/start_model.ps1")


if __name__ == "__main__":
    main()
