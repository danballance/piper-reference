from __future__ import annotations

from pathlib import Path

from upstream import main, read_copier_config, read_answers, build_substitution_map


def test_main_missing_dir(tmp_path: Path) -> None:
    result = main([str(tmp_path / "nonexistent")])
    assert result == 1


def test_main_no_answers_file(tmp_path: Path) -> None:
    result = main([str(tmp_path)])
    assert result == 1


def test_read_answers(tmp_path: Path) -> None:
    answers_file = tmp_path / ".copier-answers.yml"
    answers_file.write_text(
        "_commit: abc123\n"
        "_src_path: .\n"
        "project_name: my-app\n"
        "python_package_name: my_app\n"
        "author_name: Test User\n"
    )
    answers = read_answers(answers_file)
    assert answers == {
        "project_name": "my-app",
        "python_package_name": "my_app",
        "author_name": "Test User",
    }
    # Internal keys (starting with _) are excluded
    assert "_commit" not in answers
    assert "_src_path" not in answers


def test_read_copier_config(tmp_path: Path) -> None:
    config_file = tmp_path / "copier.yml"
    config_file.write_text(
        "_subdirectory: _template\n"
        "_min_copier_version: '9.0.0'\n"
        "project_name:\n"
        "  type: str\n"
        "  default: my-app\n"
    )
    config = read_copier_config(config_file)
    assert config.subdirectory == "_template"


def test_build_substitution_map() -> None:
    answers = {
        "project_name": "my-app",
        "python_package_name": "my_app",
        "author_name": "Test User",
        "include_nix_devenv": True,  # booleans skipped
    }
    subs = build_substitution_map(answers)
    # Longest values first
    keys = list(subs.keys())
    assert keys == sorted(keys, key=len, reverse=True)
    assert subs["my_app"] == "{{ python_package_name }}"
    assert subs["my-app"] == "{{ project_name }}"
    assert subs["Test User"] == "{{ author_name }}"
    # Booleans are not in the map
    assert True not in subs.values()
