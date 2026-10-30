"""Unit tests for toml_doctor.cli."""
from __future__ import annotations

import pytest
from toml_doctor.cli import main


def test_cli_help(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "usage: toml-doctor" in captured.out
    assert "validate" in captured.out
    assert "sort" in captured.out
    assert "fix" in captured.out


def test_cli_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "toml-doctor 0.1.0" in captured.out


def test_cli_validate_valid_file(tmp_path, capsys):
    f = tmp_path / "pyproject.toml"
    f.write_text("""[build-system]
requires = ["setuptools"]

[project]
name = "demo"
version = "0.1.0"
""", encoding="utf-8")

    ret = main(["validate", str(f), "--no-color"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "[✔ PASS]" in captured.out


def test_cli_validate_invalid_file(tmp_path, capsys):
    f = tmp_path / "bad.toml"
    f.write_text("[bad_table\n", encoding="utf-8")

    ret = main(["validate", str(f), "--no-color"])
    assert ret == 1
    captured = capsys.readouterr()
    assert "[✖ FAIL]" in captured.out


def test_cli_validate_strict_warning(tmp_path, capsys):
    f = tmp_path / "warning.toml"
    f.write_text("[tool]\nspacing=123\n", encoding="utf-8")

    # Strict mode should exit 1 on warnings
    ret = main(["validate", str(f), "--strict", "--no-color"])
    assert ret == 1


def test_cli_sort_command(tmp_path, capsys):
    f = tmp_path / "pyproject.toml"
    f.write_text("""[tool.ruff]
key = "val"

[build-system]
requires = ["setuptools"]
""", encoding="utf-8")

    # Check mode without in-place exits 1 because modification needed
    ret = main(["sort", str(f), "--diff", "--no-color"])
    assert ret == 1
    captured = capsys.readouterr()
    assert "[SORTED]" in captured.out

    # With --in-place
    ret = main(["sort", str(f), "--in-place", "--backup", "--no-color"])
    assert ret == 0
    assert (tmp_path / "pyproject.toml.bak").exists()


def test_cli_fix_command(tmp_path, capsys):
    f = tmp_path / "pyproject.toml"
    f.write_text("[project]\nname= 'demo'  \nversion='0.1.0'\n", encoding="utf-8")

    # Dry-run
    ret = main(["fix", str(f), "--diff", "--no-color"])
    assert ret == 1
    captured = capsys.readouterr()
    assert "[FIXED]" in captured.out

    # In-place fix
    ret = main(["fix", str(f), "--in-place", "--backup", "--no-color"])
    assert ret == 0

    content = f.read_text(encoding="utf-8")
    assert "name = 'demo'" in content
    assert "version = '0.1.0'" in content
