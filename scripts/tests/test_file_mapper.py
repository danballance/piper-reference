from __future__ import annotations

import subprocess
from pathlib import Path

from upstream import build_file_map, FileMapping


def _create_template_tree(tmp_path: Path) -> Path:
    """Create a minimal template directory structure inside a git repo."""
    # Init a git repo so git ls-files works
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path, capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path, capture_output=True, check=True,
    )

    template_dir = tmp_path / "_template"
    template_dir.mkdir()
    # Regular file
    (template_dir / "docker-compose.yml").write_text("version: '3'")
    # Jinja file
    (template_dir / "README.md.jinja").write_text("# {{ project_name }}")
    # Nested file
    backend = template_dir / "backend"
    backend.mkdir()
    (backend / "pyproject.toml.jinja").write_text("[project]\nname = '{{ project_name }}'")
    (backend / "Dockerfile").write_text("FROM python:3.12")
    # Copier answers file (should be skipped)
    (template_dir / "{{ _copier_conf.answers_file }}.jinja").write_text("---")

    # Stage all files so git ls-files can see them
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, check=True)

    return template_dir


def test_build_file_map(tmp_path: Path) -> None:
    template_dir = _create_template_tree(tmp_path)
    file_map = build_file_map(template_dir)

    # Regular file maps to itself
    assert FileMapping(
        template_path=template_dir / "docker-compose.yml",
        downstream_path=Path("docker-compose.yml"),
        is_jinja=False,
    ) in file_map

    # Jinja file maps with extension stripped
    assert FileMapping(
        template_path=template_dir / "README.md.jinja",
        downstream_path=Path("README.md"),
        is_jinja=True,
    ) in file_map

    # Nested jinja file
    assert FileMapping(
        template_path=template_dir / "backend" / "pyproject.toml.jinja",
        downstream_path=Path("backend/pyproject.toml"),
        is_jinja=True,
    ) in file_map

    # Copier answers file is excluded
    downstream_paths = [m.downstream_path for m in file_map]
    assert not any("copier" in str(p) for p in downstream_paths)
    assert not any("_copier_conf" in str(p) for p in downstream_paths)


def test_build_file_map_counts(tmp_path: Path) -> None:
    template_dir = _create_template_tree(tmp_path)
    file_map = build_file_map(template_dir)
    # 5 files created, minus 1 skipped (answers file) = 4
    assert len(file_map) == 4
