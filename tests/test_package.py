import json
from pathlib import Path
import tomllib
import yaml

from outlook_email_mcp import __version__

ROOT = Path(__file__).resolve().parents[1]


def test_python_and_plugin_versions_match():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    plugin = json.loads((ROOT / "plugin/outlook-email-mcp/plugin.json").read_text(encoding="utf-8"))
    assert project["project"]["version"] == __version__ == plugin["version"]
    assert plugin["repository"] == "https://github.com/iaminvester86/outlook-email-mcp"


def test_plugin_manifests_and_skill_are_valid_data():
    directory = ROOT / "plugin/outlook-email-mcp"
    plugin = json.loads((directory / "plugin.json").read_text(encoding="utf-8"))
    mcp = json.loads((directory / "mcp.json").read_text(encoding="utf-8"))
    assert plugin["$schema"] == "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
    assert mcp["$schema"] == "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"
    assert plugin["name"] == directory.name
    config = mcp["mcpServers"]["outlook-email"]
    assert config["type"] == "stdio"
    assert config["env"]["OUTLOOK_EMAIL_ENABLE_SEND"] == "false"
    assert config["env"]["OUTLOOK_EMAIL_ENABLE_DRAFTS"] == "false"
    skill = (directory / "skills/outlook-email/SKILL.md").read_text(encoding="utf-8")
    metadata = yaml.safe_load(skill.split("---", 2)[1])
    assert metadata["name"] == "outlook-email"
    assert isinstance(metadata["description"], str) and metadata["description"]


def test_client_template_has_no_credentials_or_enabled_writes():
    config = json.loads((ROOT / "examples/mcp-client.config.json").read_text(encoding="utf-8"))["mcpServers"][
        "outlook-email"
    ]
    assert config["env"]["OUTLOOK_EMAIL_ENABLE_SEND"] == "false"
    assert config["env"]["OUTLOOK_EMAIL_ENABLE_DRAFTS"] == "false"
    assert config["env"]["OUTLOOK_EMAIL_OUTLOOK_STORES"] == ""
    assert not any("PASSWORD" in name or "TOKEN" in name for name in config["env"])


def test_generated_and_private_files_have_ignore_rules():
    rules = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for value in (".env", "*.pst", "*.ost", "*.key", "__pycache__/", "dist/", "build/", ".venv/"):
        assert value in rules
