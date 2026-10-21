"""Run a pinned official Gitleaks binary after validating its release checksum."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import platform
import subprocess
import tarfile
import tempfile
import urllib.request
import zipfile

VERSION = "8.30.1"


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "outlook-email-mcp-security-check"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def main() -> None:
    system = {"Windows": "windows", "Linux": "linux", "Darwin": "darwin"}.get(platform.system())
    architecture = {"AMD64": "x64", "x86_64": "x64", "arm64": "arm64", "aarch64": "arm64"}.get(platform.machine())
    if not system or not architecture:
        raise SystemExit("Unsupported Gitleaks platform; install Gitleaks and scan manually")
    extension = "zip" if system == "windows" else "tar.gz"
    release = json.loads(fetch(f"https://api.github.com/repos/gitleaks/gitleaks/releases/tags/v{VERSION}"))
    asset = next(a for a in release["assets"] if a["name"].endswith(f"{system}_{architecture}.{extension}"))
    checksum_asset = next(a for a in release["assets"] if "checksums" in a["name"])
    payload = fetch(asset["browser_download_url"])
    expected = next(
        line.split()[0]
        for line in fetch(checksum_asset["browser_download_url"]).decode().splitlines()
        if line.strip().endswith(asset["name"])
    )
    if hashlib.sha256(payload).hexdigest() != expected:
        raise SystemExit("Gitleaks checksum verification failed")
    filename = "gitleaks.exe" if system == "windows" else "gitleaks"
    if extension == "zip":
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            binary = archive.read(filename)
    else:
        with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
            member = archive.getmember(filename)
            if not member.isfile():
                raise SystemExit("Gitleaks archive did not contain a regular executable")
            stream = archive.extractfile(member)
            if stream is None:
                raise SystemExit("Gitleaks executable is missing")
            binary = stream.read()
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="outlook-mcp-gitleaks-") as scratch:
        executable = Path(scratch) / filename
        executable.write_bytes(binary)
        executable.chmod(0o700)
        for mode in ("dir", "git"):
            command = [str(executable), mode, str(root), "--redact", "--no-banner"]
            if mode == "git":
                command.append("--log-opts=--all")
            subprocess.run(command, check=True, cwd=root)


if __name__ == "__main__":
    main()
