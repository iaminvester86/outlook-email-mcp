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
