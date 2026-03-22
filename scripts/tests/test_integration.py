from __future__ import annotations

import os
import subprocess
from pathlib import Path
from unittest.mock import patch

from upstream import main, FileChange


def _setup_template_and_downstream(tmp_path: Path) -> tuple[Path, Path]:
    """Create a mini template repo and a corresponding downstream project."""
    # Template repo structure
    repo = tmp_path / "template-repo"
    repo.mkdir()

    # Init git repo so git ls-files works
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo, capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo, capture_output=True, check=True,
    )

    (repo / "copier.yml").write_text(
        "_subdirectory: _template\n"
        "project_name:\n"
        "  type: str\n"
        "  default: my-app\n"
        "author_name:\n"
        "  type: str\n"
        "  default: Author\n"
    )

    template_dir = repo / "_template"
    template_dir.mkdir()
    (template_dir / "config.yml").write_text("app: old-value")
    (template_dir / "README.md.jinja").write_text("# {{ project_name }}\nOriginal readme")
    (template_dir / "static.txt").write_text("unchanged content")

    # Stage template files so git ls-files sees them
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, check=True)

    # Downstream project
    downstream = tmp_path / "downstream"
    downstream.mkdir()
    (downstream / ".copier-answers.yml").write_text(
        "_commit: abc123\n"
        "_src_path: .\n"
        "project_name: cool-project\n"
        "author_name: Jane Doe\n"
    )
    (downstream / "config.yml").write_text("app: new-value")
    (downstream / "README.md").write_text("# cool-project\nUpdated readme by Jane Doe")
    (downstream / "static.txt").write_text("unchanged content")

    return repo, downstream


def test_end_to_end_upstream(tmp_path: Path) -> None:
    repo, downstream = _setup_template_and_downstream(tmp_path)

    # Mock select_changes to auto-select all changes
    def mock_select(changes: list[FileChange]) -> list[FileChange]:
        return changes  # Select everything

    with patch("upstream.select_changes", side_effect=mock_select):
        original_cwd = os.getcwd()
        try:
            os.chdir(repo)
            result = main([str(downstream)])
        finally:
            os.chdir(original_cwd)

    assert result == 0

    # Verify: config.yml was updated (no templating needed — no vars in it)
    config_content = (repo / "_template" / "config.yml").read_text()
    assert config_content == "app: new-value"

    # Verify: README.md.jinja was re-templated
    readme_content = (repo / "_template" / "README.md.jinja").read_text()
    assert "{{ project_name }}" in readme_content
    assert "{{ author_name }}" in readme_content
    assert "cool-project" not in readme_content
    assert "Jane Doe" not in readme_content
    assert "Updated readme" in readme_content

    # Verify: static.txt was NOT written (unchanged)
    static_content = (repo / "_template" / "static.txt").read_text()
    assert static_content == "unchanged content"
