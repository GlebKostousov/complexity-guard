"""Конфигурация порогов сложности и путей сканирования."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

DEFAULT_EXCLUDES = [
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "build",
    "dist",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".eggs",
    "*.egg-info",
]

_INT_FIELDS = (
    "max_loop_depth",
    "max_complexity",
    "max_branches",
    "max_returns",
    "max_comprehension_depth",
)
_BOOL_FIELDS = (
    "strict",
    "check_linear_in_loop",
    "check_quadratic_methods",
    "check_string_concat",
)
_BOOL_MAP = {"true": True, "false": False}


@dataclass
class Config:
    """Храни пороги сложности и параметры обхода файлов."""

    max_loop_depth: int = 2
    max_complexity: int = 5
    max_branches: int = 6
    max_returns: int = 4
    check_linear_in_loop: bool = True
    check_quadratic_methods: bool = True
    check_string_concat: bool = True
    max_comprehension_depth: int = 1
    strict: bool = False
    lang: str = "en"
    exclude: list[str] = field(default_factory=lambda: list(DEFAULT_EXCLUDES))

    def apply_strict_mode(self) -> None:
        """Примени строгие лимиты при включении строгого режима."""
        if self.strict:
            self.max_complexity = min(self.max_complexity, 3)
            self.max_branches = min(self.max_branches, 4)
            self.max_returns = min(self.max_returns, 3)
            self.max_comprehension_depth = min(self.max_comprehension_depth, 1)


def _parse_toml_list(val: str) -> list[str]:
    """Извлеки список строк из TOML-массива."""
    return [item.strip().strip("'\"") for item in val[1:-1].split(",") if item.strip()]


def _parse_toml_scalar(val: str) -> Any:
    """Распарси скалярное значение из строки TOML."""
    clean = val.split("#")[0].strip()
    if clean.lower() in _BOOL_MAP:
        return _BOOL_MAP[clean.lower()]
    if clean.lstrip("-").isdigit():
        return int(clean)
    if clean.startswith("[") and clean.endswith("]"):
        return _parse_toml_list(clean)
    return clean.strip("'\"")


def _is_toml_comment_or_empty(line: str) -> bool:
    """Проверь, является ли строка пустой или комментарием."""
    return not line or line.startswith("#")


def _extract_toml_kv(line: str) -> tuple[str, str] | None:
    """Извлеки пару ключ-значение из строки TOML."""
    if "=" not in line:
        return None
    key, val = line.split("=", 1)
    return key.strip().replace("-", "_"), val


def _append_toml_kv(result: dict[str, Any], line: str) -> None:
    """Запиши извлеченную пару ключ-значение в результирующий словарь."""
    kv = _extract_toml_kv(line)
    if kv:
        result[kv[0]] = _parse_toml_scalar(kv[1])


def _parse_simple_toml_table(content: str, section: str = "tool.complexity-guard") -> dict[str, Any]:
    """Собери секцию TOML встроенным парсером при отсутствии tomllib/tomli."""
    target_header = f"[{section}]"
    in_section = False
    result: dict[str, Any] = {}

    for raw in content.splitlines():
        line = raw.strip()
        if _is_toml_comment_or_empty(line):
            continue
        if line.startswith("["):
            in_section = line == target_header
            continue
        if in_section:
            _append_toml_kv(result, line)

    return result


def _load_with_toml_module(content: str) -> dict[str, Any] | None:
    """Прочитай TOML через библиотечный модуль tomllib или tomli."""
    for mod_name in ("tomllib", "tomli"):
        try:
            mod = __import__(mod_name)
            data = mod.loads(content)
            tool_sec = data.get("tool", {}).get("complexity-guard", {})
            return {k.replace("-", "_"): v for k, v in tool_sec.items()}
        except (ImportError, Exception):
            continue
    return None


def load_toml_config(file_path: Path) -> dict[str, Any]:
    """Загрузи настройки из pyproject.toml."""
    if not file_path.is_file():
        return {}
    try:
        content = file_path.read_text(encoding="utf-8")
    except OSError:
        return {}

    parsed = _load_with_toml_module(content)
    if parsed is not None:
        return parsed
    return _parse_simple_toml_table(content)


def find_pyproject_toml(start_dir: Path | None = None) -> Path | None:
    """Найди pyproject.toml в текущей или родительской директории."""
    current = (start_dir or Path.cwd()).resolve()
    for parent in [current, *current.parents]:
        candidate = parent / "pyproject.toml"
        if candidate.is_file():
            return candidate
    return None


def _apply_bool_overrides(cfg: Config, data: dict[str, Any]) -> None:
    """Запиши логические параметры из словаря в конфигурацию."""
    for key in _BOOL_FIELDS:
        if key in data:
            val = data[key]
            effective = _BOOL_MAP[val.lower()] if isinstance(val, str) and val.lower() in _BOOL_MAP else bool(val)
            setattr(cfg, key, effective)


def _apply_dict_overrides(cfg: Config, data: dict[str, Any]) -> None:
    """Запиши значения из словаря TOML в объект конфигурации."""
    for key in _INT_FIELDS:
        if key in data:
            setattr(cfg, key, int(data[key]))
    _apply_bool_overrides(cfg, data)
    if "lang" in data:
        cfg.lang = str(data["lang"]).lower()
    if isinstance(data.get("exclude"), list):
        cfg.exclude = list(data["exclude"])


def _apply_cli_overrides(cfg: Config, overrides: dict[str, Any]) -> None:
    """Запиши переданные через CLI аргументы в объект конфигурации."""
    for key, val in overrides.items():
        if val is not None:
            setattr(cfg, key, val)


def get_config(
    config_file: Path | None = None,
    max_loop_depth: int | None = None,
    max_complexity: int | None = None,
    max_branches: int | None = None,
    max_returns: int | None = None,
    check_linear_in_loop: bool | None = None,
    check_quadratic_methods: bool | None = None,
    check_string_concat: bool | None = None,
    max_comprehension_depth: int | None = None,
    strict: bool | None = None,
    lang: str | None = None,
    exclude: Sequence[str] | None = None,
) -> Config:
    """Собери итоговую конфигурацию с приоритетом CLI-флагов над pyproject.toml."""
    toml_path = config_file or find_pyproject_toml()
    cfg = Config()
    if toml_path:
        _apply_dict_overrides(cfg, load_toml_config(toml_path))

    cli_values = {
        "max_loop_depth": max_loop_depth,
        "max_complexity": max_complexity,
        "max_branches": max_branches,
        "max_returns": max_returns,
        "check_linear_in_loop": check_linear_in_loop,
        "check_quadratic_methods": check_quadratic_methods,
        "check_string_concat": check_string_concat,
        "max_comprehension_depth": max_comprehension_depth,
        "strict": strict,
        "lang": lang,
        "exclude": list(exclude) if exclude is not None else None,
    }
    _apply_cli_overrides(cfg, cli_values)
    cfg.apply_strict_mode()
    return cfg
