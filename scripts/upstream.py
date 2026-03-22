# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "pyyaml>=6.0",
#   "questionary>=2.0",
# ]
# ///
"""Upstream changes from a downstream copier project back to the template."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Any
from pathlib import Path

import questionary
import yaml


@dataclass(frozen=True)
class CopierConfig:
    subdirectory: str


def read_copier_config(config_path: Path) -> CopierConfig:
    """Read copier.yml and extract template configuration."""
    with open(config_path) as f:
        raw = yaml.safe_load(f)

    subdirectory = raw.get("_subdirectory", "")

    return CopierConfig(subdirectory=subdirectory)


def read_answers(answers_path: Path) -> dict[str, Any]:
    """Read .copier-answers.yml and return user-defined answers (no internal keys)."""
    with open(answers_path) as f:
        raw = yaml.safe_load(f)

    return {k: v for k, v in raw.items() if not k.startswith("_")}


@dataclass(frozen=True)
class FileMapping:
    template_path: Path
    downstream_path: Path
    is_jinja: bool


# Patterns that indicate copier internal files to skip
_COPIER_INTERNAL_PATTERNS = {"_copier_conf", ".copier-answers"}


def _is_copier_internal(path: Path) -> bool:
    """Check if a path is a copier internal file that should be skipped."""
    path_str = str(path)
    return any(pattern in path_str for pattern in _COPIER_INTERNAL_PATTERNS)


def _git_listed_files(directory: Path) -> list[Path]:
    """Return non-ignored files within a directory (tracked + untracked, respecting .gitignore)."""
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=directory,
        capture_output=True,
        text=True,
        check=True,
    )
    return sorted(
        directory / line
        for line in result.stdout.splitlines()
        if line
    )


def build_file_map(template_dir: Path) -> list[FileMapping]:
    """Walk the template directory and build mappings to downstream paths.

    - Only includes files visible to git (tracked + untracked, respecting .gitignore)
    - .jinja suffix is stripped for the downstream path
    - Copier internal files (answers file) are excluded
    """
    mappings: list[FileMapping] = []

    for template_path in _git_listed_files(template_dir):
        if _is_copier_internal(template_path):
            continue

        # Compute the relative path from the template dir
        rel_path = template_path.relative_to(template_dir)

        # Check if this is a jinja template
        is_jinja = template_path.suffix == ".jinja"
        if is_jinja:
            # Strip .jinja extension for downstream path
            downstream_path = rel_path.with_suffix("")
        else:
            downstream_path = rel_path

        mappings.append(FileMapping(
            template_path=template_path,
            downstream_path=downstream_path,
            is_jinja=is_jinja,
        ))

    return mappings


def build_substitution_map(answers: dict[str, Any]) -> dict[str, str]:
    """Build a reverse substitution map: expanded_value -> '{{ variable_name }}'.

    Only string values are included. Sorted by value length descending
    to prevent partial matches (e.g., 'my_app' before 'my').
    """
    subs: dict[str, str] = {}
    for var_name, value in answers.items():
        if not isinstance(value, str) or not value:
            continue
        subs[value] = "{{ " + var_name + " }}"

    # Sort by key length descending (longest values substituted first)
    return dict(sorted(subs.items(), key=lambda item: len(item[0]), reverse=True))


class ChangeType(Enum):
    MODIFIED = "modified"
    DELETED = "deleted"


@dataclass(frozen=True)
class FileChange:
    mapping: FileMapping
    change_type: ChangeType


def _is_binary(path: Path) -> bool:
    """Heuristic: check if file contains null bytes."""
    try:
        chunk = path.read_bytes()[:8192]
        return b"\x00" in chunk
    except OSError:
        return False


def compute_changes(
    file_map: list[FileMapping],
    downstream_dir: Path,
    substitution_map: dict[str, str],
) -> list[FileChange]:
    """Compare template files against downstream files and return changes.

    Downstream content is re-templated before comparison so that expanded
    values (e.g. 'my-app') are converted back to Jinja tags (e.g. '{{ project_name }}')
    before diffing against the template. This prevents already-upstreamed files
    from reappearing as modified.

    Only returns files that differ or are deleted. Unchanged files are excluded.
    """
    changes: list[FileChange] = []

    for mapping in file_map:
        downstream_file = downstream_dir / mapping.downstream_path

        if not downstream_file.exists():
            changes.append(FileChange(mapping=mapping, change_type=ChangeType.DELETED))
            continue

        # Compare file contents
        if _is_binary(mapping.template_path) or _is_binary(downstream_file):
            if mapping.template_path.read_bytes() != downstream_file.read_bytes():
                changes.append(FileChange(mapping=mapping, change_type=ChangeType.MODIFIED))
        else:
            template_content = mapping.template_path.read_text()
            downstream_content = re_template_content(
                downstream_file.read_text(), substitution_map,
            )
            if template_content != downstream_content:
                changes.append(FileChange(mapping=mapping, change_type=ChangeType.MODIFIED))

    return changes


def re_template_content(content: str, substitution_map: dict[str, str]) -> str:
    """Replace expanded variable values with Jinja template tags.

    The substitution_map is already sorted longest-first to prevent partial matches.
    """
    for expanded_value, jinja_tag in substitution_map.items():
        content = content.replace(expanded_value, jinja_tag)
    return content


@dataclass(frozen=True)
class UpstreamResult:
    written: list[Path]
    deleted: list[Path]


def apply_upstream(
    changes: list[FileChange],
    downstream_dir: Path,
    substitution_map: dict[str, str],
) -> UpstreamResult:
    """Apply selected changes: re-template modified files, delete removed files.

    Returns paths that were written and deleted.
    """
    written: list[Path] = []
    deleted: list[Path] = []

    for change in changes:
        template_path = change.mapping.template_path

        if change.change_type == ChangeType.DELETED:
            if template_path.exists():
                subprocess.run(
                    ["git", "rm", "-f", str(template_path)],
                    cwd=template_path.parent,
                    capture_output=True,
                    check=True,
                )
                deleted.append(template_path)
            continue

        downstream_file = downstream_dir / change.mapping.downstream_path

        # Ensure parent directory exists
        template_path.parent.mkdir(parents=True, exist_ok=True)

        if _is_binary(downstream_file):
            shutil.copy2(downstream_file, template_path)
        else:
            content = downstream_file.read_text()
            content = re_template_content(content, substitution_map)
            template_path.write_text(content)

        written.append(template_path)

    return UpstreamResult(written=written, deleted=deleted)


def select_changes(changes: list[FileChange]) -> list[FileChange]:
    """Present an interactive checkbox list of changed files for user selection."""
    if not changes:
        print("No changes detected between downstream and template.")
        return []

    choices = []
    for change in changes:
        label = f"{change.mapping.downstream_path}  ({change.change_type.value})"
        choices.append(questionary.Choice(title=label, value=change))

    selected = questionary.checkbox(
        "Select files to upstream:",
        choices=choices,
    ).ask()

    if selected is None:
        # User cancelled (Ctrl+C)
        return []

    return selected


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Upstream changes from a downstream copier project to this template.",
    )
    parser.add_argument(
        "downstream",
        type=Path,
        help="Path to the downstream project directory",
    )
    args = parser.parse_args(argv)

    downstream_dir = args.downstream.resolve()
    # Assume script is run from template repo root, or find it
    template_repo = Path.cwd()
    copier_config_path = template_repo / "copier.yml"

    # Validate inputs
    if not downstream_dir.is_dir():
        print(f"Error: {downstream_dir} is not a directory", file=sys.stderr)
        return 1

    answers_path = downstream_dir / ".copier-answers.yml"
    if not answers_path.exists():
        print(f"Error: {answers_path} not found — is this a copier project?", file=sys.stderr)
        return 1

    if not copier_config_path.exists():
        print(f"Error: {copier_config_path} not found — run from template repo root.", file=sys.stderr)
        return 1

    # 1. Read config
    config = read_copier_config(copier_config_path)
    answers = read_answers(answers_path)
    substitution_map = build_substitution_map(answers)

    template_dir = template_repo / config.subdirectory
    if not template_dir.is_dir():
        print(f"Error: template subdirectory {template_dir} not found.", file=sys.stderr)
        return 1

    # 2. Build file map
    file_map = build_file_map(template_dir)
    print(f"Found {len(file_map)} template files.")

    # 3. Compute changes
    changes = compute_changes(file_map, downstream_dir, substitution_map)
    if not changes:
        print("No changes detected. Downstream matches the template.")
        return 0

    print(f"Detected {len(changes)} changed files.\n")

    # 4. Select changes
    selected = select_changes(changes)
    if not selected:
        print("No files selected. Nothing to do.")
        return 0

    # 5. Apply upstream
    result = apply_upstream(selected, downstream_dir, substitution_map)

    # 6. Summary
    if result.written:
        print(f"\nUpstreamed {len(result.written)} files:")
        for path in result.written:
            print(f"  {path.relative_to(template_repo)}")
    if result.deleted:
        print(f"\nDeleted {len(result.deleted)} files:")
        for path in result.deleted:
            print(f"  {path.relative_to(template_repo)}")
    if not result.written and not result.deleted:
        print("\nNo changes applied.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
