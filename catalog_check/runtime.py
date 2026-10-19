"""Bounded, user-triggered setup/start of the bundled Windows local model."""
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import threading

from catalog_check import model

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime"
LOCK = threading.Lock()
JOB = {"busy": False, "phase": "idle", "message": ""}


def installed():
    try:
        manifest = json.loads((RUNTIME / "manifest.json").read_text(encoding="utf-8"))
        paths = [(ROOT / manifest["runtime"]["server"]).resolve(), (ROOT / manifest["model"]["path"]).resolve()]
        return all(path.is_relative_to(RUNTIME.resolve()) and path.is_file() for path in paths)
    except (OSError, ValueError, KeyError, TypeError):
        return False


def snapshot():
    with LOCK:
        result = dict(JOB)
    result.update({"installed": installed(), "supported": platform.system() == "Windows" and platform.machine().lower() in {"amd64", "x86_64"}})
    return result


def update(**values):
    with LOCK:
        JOB.update(values)


def launch(install=False, cpu=False):
    if not snapshot()["supported"]:
        raise ValueError("One-click local setup supports Windows x64. Use an API service or follow the README for other platforms.")
    if not installed() and not install:
        raise ValueError("Install the local model first, or use an API service.")
    # The bundled launcher owns only its fixed port and alias, never custom URLs.
    if model.endpoint() != "http://127.0.0.1:8766/v1" or os.getenv("CATALOG_MODEL_NAME", "catalog-qwen") != "catalog-qwen":
        raise ValueError("A custom local model is configured. Start that server yourself, or remove the CATALOG_MODEL_URL / CATALOG_MODEL_NAME overrides to use one-click setup.")
    with LOCK:
        if JOB["busy"]:
            return {"busy": True, "phase": JOB["phase"], "message": JOB["message"]}
        JOB.update(busy=True, phase="starting", message="Preparing local AI…")
    threading.Thread(target=_worker, args=(cpu,), daemon=True).start()
    return snapshot()


def _worker(cpu):
    try:
        RUNTIME.mkdir(exist_ok=True)
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        with (RUNTIME / "setup.log").open("w", encoding="utf-8") as log:
            if not installed():
                update(phase="downloading", message="Downloading and verifying the local model (about 672 MB). This may take several minutes. Keep the app running.")
                command = [sys.executable, str(ROOT / "scripts" / "setup_model.py")]
                if cpu:
                    command.append("--cpu")
                subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=2400, creationflags=flags)
            update(phase="starting", message="Starting the local model…")
            command = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts" / "start_model.ps1")]
            if cpu:
                command.append("-Cpu")
            subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=90, creationflags=flags)
            if not model.status()["ready"]:
                raise RuntimeError("Model did not become ready")
        update(busy=False, phase="ready", message="Local AI is ready. No API key is needed.")
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
        update(busy=False, phase="error", message="Local setup/start failed. Try CPU mode if GPU startup failed. See .runtime/setup.log for details, or use an API service.")
