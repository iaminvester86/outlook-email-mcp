"""Filesystem and operation policy; no arbitrary paths or destructive mail ops."""

from __future__ import annotations

import os
from pathlib import Path

from .errors import PolicyError


class SafePathPolicy:
    def __init__(self, roots: tuple[Path, ...] | list[Path] = ()) -> None:
        self.roots = tuple(Path(root).expanduser().resolve() for root in roots)

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
        return name[:255]

    def target(self, directory: str | os.PathLike[str], filename: str) -> Path:
        directory_path = self.resolve_save_path(directory)
        if not directory_path.is_dir():
            raise PolicyError("attachment destination must be an existing directory")
        return self.resolve_save_path(directory_path / self.filename(filename))
