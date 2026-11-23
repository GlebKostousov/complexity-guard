"""Тесты для модуля чтения и применения конфигурации."""

from pathlib import Path

from complexity_guard.config import (
    _parse_simple_toml_table,
    find_pyproject_toml,
    get_config,
    load_toml_config,
)


def test_parse_simple_toml_table() -> None:
    """Проверь разбор таблицы секции [tool.complexity-guard] встроенным парсером."""
    content = """
[tool.other]
foo = "bar"

[tool.complexity-guard]
max-loop-depth = 3
max-complexity = 8
max-branches = 10
max-returns = 5
strict = true
exclude = ["tests", "migrations"]

[build-system]
requires = ["hatchling"]
"""
    parsed = _parse_simple_toml_table(content)
    assert parsed["max_loop_depth"] == 3
    assert parsed["max_complexity"] == 8
    assert parsed["max_branches"] == 10
    assert parsed["max_returns"] == 5
    assert parsed["strict"] is True
    assert parsed["exclude"] == ["tests", "migrations"]


def test_load_toml_config_missing_file(tmp_path: Path) -> None:
    """Проверь корректную обработку отсутствующего файла конфигурации."""
    non_existent = tmp_path / "pyproject.toml"
    assert load_toml_config(non_existent) == {}


def test_load_toml_config_valid_file(tmp_path: Path) -> None:
    """Проверь считывание настроек из существующего файла pyproject.toml."""
    toml_file = tmp_path / "pyproject.toml"
    toml_file.write_text(
        """
[tool.complexity-guard]
max-loop-depth = 4
strict = false
""",
        encoding="utf-8",
    )
    data = load_toml_config(toml_file)
    assert data["max_loop_depth"] == 4
    assert data["strict"] is False


def test_get_config_cli_overrides_toml(tmp_path: Path) -> None:
    """Убедись, что аргументы CLI переопределяют значения из pyproject.toml."""
    toml_file = tmp_path / "pyproject.toml"
    toml_file.write_text(
        """
[tool.complexity-guard]
max-loop-depth = 3
max-complexity = 10
""",
        encoding="utf-8",
    )
    cfg = get_config(config_file=toml_file, max_complexity=4)
    assert cfg.max_loop_depth == 3
    assert cfg.max_complexity == 4


def test_get_config_strict_mode() -> None:
    """Проверь установку жестких порогов при активации строгого режима."""
    cfg = get_config(strict=True)
    assert cfg.strict is True
    assert cfg.max_complexity == 3
    assert cfg.max_branches == 4
    assert cfg.max_returns == 3


def test_find_pyproject_toml(tmp_path: Path) -> None:
    """Проверь автоматический поиск pyproject.toml вверх по дереву каталогов."""
    root = tmp_path / "my_project"
    sub = root / "src" / "pkg"
    sub.mkdir(parents=True)
    toml = root / "pyproject.toml"
    toml.write_text("[project]\nname='test'\n", encoding="utf-8")

    found = find_pyproject_toml(start_dir=sub)
    assert found is not None
    assert found.resolve() == toml.resolve()


def test_config_new_rules_defaults_and_overrides(tmp_path: Path) -> None:
    """Проверь значения по умолчанию и переопределение новых правил сложности."""
    toml_file = tmp_path / "pyproject.toml"
    toml_file.write_text(
        """
[tool.complexity-guard]
check-linear-in-loop = false
check-quadratic-methods = false
check-string-concat = false
max-comprehension-depth = 2
""",
        encoding="utf-8",
    )
    cfg = get_config(config_file=toml_file)
    assert cfg.check_linear_in_loop is False
    assert cfg.check_quadratic_methods is False
    assert cfg.check_string_concat is False
    assert cfg.max_comprehension_depth == 2
