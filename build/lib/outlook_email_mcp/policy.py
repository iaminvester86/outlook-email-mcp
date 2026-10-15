"""Filesystem and operation policy; no arbitrary paths or destructive mail ops."""

from __future__ import annotations

import os
from pathlib import Path

from .errors import PolicyError


class SafePathPolicy:
    def __init__(self, roots: tuple[Path, ...] | list[Path] = (), attachment_roots: tuple[Path, ...] | list[Path] = ()) -> None:
        self.roots = tuple(Path(root).expanduser().resolve() for root in roots)
        self.attachment_roots = tuple(Path(root).expanduser().resolve() for root in attachment_roots)

    def resolve_save_path(self, requested: str | os.PathLike[str]) -> Path:
        if not self.roots:
            raise PolicyError("attachment saving is disabled until OUTLOOK_EMAIL_SAVE_ROOTS is configured")
        raw = Path(requested).expanduser()
        if not str(raw).strip() or "\x00" in str(raw):
            raise PolicyError("invalid attachment path")
        candidate = raw.resolve(strict=False)
        if not any(self._inside(candidate, root) for root in self.roots):
            raise PolicyError("attachment path is outside an allowed save root")
        return candidate

    @staticmethod
    def _inside(candidate: Path, root: Path) -> bool:
        try:
            candidate.relative_to(root)
            return True
        except ValueError:
            return False

    def filename(self, value: str) -> str:
        name = str(value)
        if not name or name in {".", ".."} or "\x00" in name:
            raise PolicyError("invalid attachment filename")
        if Path(name).name != name or "/" in name or "\\" in name:
            raise PolicyError("attachment filename must not contain path separators")
        if ":" in name or any(ord(char) < 32 for char in name):
            raise PolicyError("attachment filename contains a reserved character")
        if name.rstrip(" .").split(".", 1)[0].upper() in {
            "CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4",
            "COM5", "COM6", "COM7", "COM8", "COM9", "LPT1", "LPT2",
            "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
        }:
            raise PolicyError("attachment filename is reserved on Windows")
        return name[:255]

    def attachment(self, requested: str | os.PathLike[str], max_bytes: int) -> Path:
        if not self.attachment_roots:
            raise PolicyError("attachments are disabled until OUTLOOK_EMAIL_ATTACHMENT_ROOTS is configured")
        path = Path(requested).expanduser().resolve(strict=True)
        if not path.is_file() or not any(self._inside(path, root) for root in self.attachment_roots):
            raise PolicyError("attachment path is outside an allowed attachment root")
        if path.stat().st_size > max_bytes:
            raise PolicyError("attachment exceeds configured safety limit")
        return path

    def target(self, directory: str | os.PathLike[str], filename: str) -> Path:
        directory_path = self.resolve_save_path(directory)
        if not directory_path.is_dir():
            raise PolicyError("attachment destination must be an existing directory")
        target = self.resolve_save_path(directory_path / self.filename(filename))
        if target.exists():
            raise PolicyError("refusing to overwrite an existing attachment")
        return target

    @staticmethod
    def write_new_file(target: Path, payload: bytes) -> None:
        """Create an export without following an existing replacement path."""
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_BINARY"):
            flags |= os.O_BINARY
        descriptor = os.open(os.fspath(target), flags, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                descriptor = -1
                stream.write(payload)
        finally:
            if descriptor != -1:
                os.close(descriptor)
