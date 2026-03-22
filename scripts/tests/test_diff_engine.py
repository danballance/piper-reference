from __future__ import annotations

from pathlib import Path

from upstream import compute_changes, FileChange, ChangeType, FileMapping, build_substitution_map


def test_modified_file(tmp_path: Path) -> None:
    template_dir = tmp_path / "_template"
    template_dir.mkdir()
    downstream_dir = tmp_path / "downstream"
    downstream_dir.mkdir()

    (template_dir / "config.yml").write_text("old: value")
    (downstream_dir / "config.yml").write_text("new: value")

    mapping = FileMapping(
        template_path=template_dir / "config.yml",
        downstream_path=Path("config.yml"),
        is_jinja=False,
    )
    changes = compute_changes([mapping], downstream_dir, {})
    assert len(changes) == 1
    assert changes[0].change_type == ChangeType.MODIFIED
    assert changes[0].mapping == mapping


def test_unchanged_file(tmp_path: Path) -> None:
    template_dir = tmp_path / "_template"
    template_dir.mkdir()
    downstream_dir = tmp_path / "downstream"
    downstream_dir.mkdir()

    (template_dir / "config.yml").write_text("same: value")
    (downstream_dir / "config.yml").write_text("same: value")

    mapping = FileMapping(
        template_path=template_dir / "config.yml",
        downstream_path=Path("config.yml"),
        is_jinja=False,
    )
    changes = compute_changes([mapping], downstream_dir, {})
    assert len(changes) == 0  # Unchanged files not included


def test_deleted_file(tmp_path: Path) -> None:
    template_dir = tmp_path / "_template"
    template_dir.mkdir()
    downstream_dir = tmp_path / "downstream"
    downstream_dir.mkdir()

    (template_dir / "old.txt").write_text("exists in template only")

    mapping = FileMapping(
        template_path=template_dir / "old.txt",
        downstream_path=Path("old.txt"),
        is_jinja=False,
    )
    changes = compute_changes([mapping], downstream_dir, {})
    assert len(changes) == 1
    assert changes[0].change_type == ChangeType.DELETED


def test_jinja_file_unchanged_after_retemplating(tmp_path: Path) -> None:
    """A jinja file whose downstream content matches the template after re-templating is not reported."""
    template_dir = tmp_path / "_template"
    template_dir.mkdir()
    downstream_dir = tmp_path / "downstream"
    downstream_dir.mkdir()

    (template_dir / "README.md.jinja").write_text("# {{ project_name }}")
    (downstream_dir / "README.md").write_text("# my-app")

    mapping = FileMapping(
        template_path=template_dir / "README.md.jinja",
        downstream_path=Path("README.md"),
        is_jinja=True,
    )
    subs = build_substitution_map({"project_name": "my-app"})
    changes = compute_changes([mapping], downstream_dir, subs)
    assert len(changes) == 0  # Re-templated downstream matches template


def test_jinja_file_modified_after_retemplating(tmp_path: Path) -> None:
    """A jinja file with real changes is still reported as modified."""
    template_dir = tmp_path / "_template"
    template_dir.mkdir()
    downstream_dir = tmp_path / "downstream"
    downstream_dir.mkdir()

    (template_dir / "README.md.jinja").write_text("# {{ project_name }}")
    (downstream_dir / "README.md").write_text("# my-app\nNew content added")

    mapping = FileMapping(
        template_path=template_dir / "README.md.jinja",
        downstream_path=Path("README.md"),
        is_jinja=True,
    )
    subs = build_substitution_map({"project_name": "my-app"})
    changes = compute_changes([mapping], downstream_dir, subs)
    assert len(changes) == 1
    assert changes[0].change_type == ChangeType.MODIFIED
