from __future__ import annotations

import subprocess
from pathlib import Path

from upstream import (
    re_template_content,
    apply_upstream,
    build_substitution_map,
    FileMapping,
    FileChange,
    ChangeType,
)


def test_re_template_content_simple() -> None:
    content = 'name = "my-app"\npackage = "my_app"'
    subs = build_substitution_map({
        "project_name": "my-app",
        "python_package_name": "my_app",
    })
    result = re_template_content(content, subs)
    assert '{{ project_name }}' in result
    assert '{{ python_package_name }}' in result
    assert "my-app" not in result
    assert "my_app" not in result


def test_re_template_content_longest_first() -> None:
    """Ensure 'my_app_name' is substituted before 'my_app'."""
    content = "import my_app_name\nimport my_app"
    subs = build_substitution_map({
        "short": "my_app",
        "long": "my_app_name",
    })
    result = re_template_content(content, subs)
    # 'my_app_name' should be replaced as a whole, not partially
    assert "{{ long }}" in result
    assert "{{ short }}" in result
    assert "{{ long }}_name" not in result


def test_re_template_content_preserves_non_matching() -> None:
    content = "some random text with no variables"
    subs = build_substitution_map({"project_name": "my-app"})
    result = re_template_content(content, subs)
    assert result == content


def test_apply_upstream_writes_file(tmp_path: Path) -> None:
    template_dir = tmp_path / "_template"
    template_dir.mkdir()
    downstream_dir = tmp_path / "downstream"
    downstream_dir.mkdir()

    # Create downstream file with expanded values
    (downstream_dir / "config.yml").write_text('name: "my-app"')
    # Create existing template file
    (template_dir / "config.yml").write_text('name: "old"')

    mapping = FileMapping(
        template_path=template_dir / "config.yml",
        downstream_path=Path("config.yml"),
        is_jinja=False,
    )
    change = FileChange(mapping=mapping, change_type=ChangeType.MODIFIED)
    subs = build_substitution_map({"project_name": "my-app"})

    apply_upstream([change], downstream_dir, subs)
    result = (template_dir / "config.yml").read_text()
    assert '{{ project_name }}' in result


def test_apply_upstream_jinja_file(tmp_path: Path) -> None:
    """When upstreaming to a .jinja file, content is re-templated and written to the .jinja path."""
    template_dir = tmp_path / "_template"
    template_dir.mkdir()
    downstream_dir = tmp_path / "downstream"
    downstream_dir.mkdir()

    (downstream_dir / "README.md").write_text("# my-app\nA cool project")
    (template_dir / "README.md.jinja").write_text("# old")

    mapping = FileMapping(
        template_path=template_dir / "README.md.jinja",
        downstream_path=Path("README.md"),
        is_jinja=True,
    )
    change = FileChange(mapping=mapping, change_type=ChangeType.MODIFIED)
    subs = build_substitution_map({"project_name": "my-app"})

    apply_upstream([change], downstream_dir, subs)
    result = (template_dir / "README.md.jinja").read_text()
    assert "{{ project_name }}" in result
    assert "A cool project" in result


def test_apply_upstream_deletes_file(tmp_path: Path) -> None:
    # git rm requires a git repo
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
    downstream_dir = tmp_path / "downstream"
    downstream_dir.mkdir()

    template_file = template_dir / "obsolete.txt"
    template_file.write_text("old content")

    # Track the file in git so git rm works
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=tmp_path, capture_output=True, check=True,
    )

    mapping = FileMapping(
        template_path=template_file,
        downstream_path=Path("obsolete.txt"),
        is_jinja=False,
    )
    change = FileChange(mapping=mapping, change_type=ChangeType.DELETED)

    result = apply_upstream([change], downstream_dir, build_substitution_map({}))
    assert not template_file.exists()
    assert len(result.deleted) == 1
    assert len(result.written) == 0
