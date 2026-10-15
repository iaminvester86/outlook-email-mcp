from pathlib import Path

import pytest

from outlook_email_mcp.errors import PolicyError
from outlook_email_mcp.policy import SafePathPolicy


def test_policy_accepts_file_inside_root(tmp_path: Path):
    policy = SafePathPolicy((tmp_path,))
    assert policy.target(str(tmp_path), "report.pdf") == tmp_path / "report.pdf"


def test_policy_rejects_traversal_and_nested_filename(tmp_path: Path):
    policy = SafePathPolicy((tmp_path,))
    with pytest.raises(PolicyError):
        policy.resolve_save_path(tmp_path / ".." / "outside")
    with pytest.raises(PolicyError):
        policy.target(str(tmp_path), "nested/report.pdf")


def test_policy_requires_explicit_root(tmp_path: Path):
    with pytest.raises(PolicyError):
        SafePathPolicy().resolve_save_path(tmp_path / "file")


def test_policy_requires_attachment_root_and_containment(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    file = source / "note.txt"
    file.write_text("safe", encoding="utf-8")
    policy = SafePathPolicy(attachment_roots=(source,))
    assert policy.attachment(file, 100).samefile(file)
    with pytest.raises(PolicyError):
        SafePathPolicy().attachment(file, 100)


def test_policy_rejects_reserved_names_and_overwrites(tmp_path: Path):
    policy = SafePathPolicy((tmp_path,))
    with pytest.raises(PolicyError):
        policy.filename("CON.txt")
    existing = tmp_path / "existing.txt"
    existing.write_text("old", encoding="utf-8")
    with pytest.raises(PolicyError):
        policy.target(tmp_path, existing.name)


def test_policy_atomic_export_does_not_overwrite(tmp_path: Path):
    policy = SafePathPolicy((tmp_path,))
    target = policy.target(tmp_path, "new.txt")
    policy.write_new_file(target, b"safe")
    assert target.read_bytes() == b"safe"
    with pytest.raises(FileExistsError):
        policy.write_new_file(target, b"changed")
