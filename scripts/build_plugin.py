"""Build a deterministic, credential-free portable plugin and release checksums."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import zipfile


def build(root: Path) -> Path:
    source = root / "plugin" / "outlook-email-mcp"
    manifest = json.loads((source / "plugin.json").read_text(encoding="utf-8"))
    output = root / "dist"
    output.mkdir(exist_ok=True)
    archive = output / f"outlook-email-mcp-agent-plugin-{manifest['version']}.zip"
    included = ["plugin.json", "mcp.json", "INSTALL.md", "skills/outlook-email/SKILL.md"]
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as package:
        for name in sorted(included):
            path = source / name
            if path.is_symlink() or not path.is_file():
                raise ValueError("plugin component must be a regular source file")
            entry = zipfile.ZipInfo("outlook-email-mcp/" + name, date_time=(2020, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            package.writestr(entry, path.read_bytes())
    artifacts = sorted(p for p in output.iterdir() if p.is_file() and p.name != "SHA256SUMS")
    checksums = "".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in artifacts)
    (output / "SHA256SUMS").write_text(checksums, encoding="utf-8", newline="\n")
    return archive


if __name__ == "__main__":
    print(build(Path(__file__).resolve().parents[1]))
