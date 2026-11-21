"""Интерфейс командной строки complexity-guard."""

import argparse
import fnmatch
import json
from pathlib import Path
import sys
from typing import Sequence

from . import __version__
from .checker import Violation, check_file
from .config import Config, get_config


def _get_rel_path_str(path: Path, root: Path) -> str:
    """Вычисли относительный путь в виде нормализованной строки."""
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path.resolve()).replace("\\", "/")


def _pattern_matches(pattern: str, rel_str: str, parts: set[str], name: str) -> bool:
    """Проверь соответствие пути шаблону исключения."""
    pat = pattern.replace("\\", "/").rstrip("/")
    if pat in parts or fnmatch.fnmatch(name, pat):
        return True
    return fnmatch.fnmatch(rel_str, pat) or fnmatch.fnmatch(rel_str, f"*/{pat}/*") or fnmatch.fnmatch(rel_str, f"{pat}/*")


def _matches_exclude(path: Path, root: Path, excludes: Sequence[str]) -> bool:
    """Проверь, попадает ли путь под исключения."""
    rel_str = _get_rel_path_str(path, root)
    parts = set(rel_str.split("/"))
    name = path.name
    for pattern in excludes:
        if _pattern_matches(pattern, rel_str, parts, name):
            return True
    return False


def _collect_dir_files(directory: Path, root: Path, excludes: Sequence[str]) -> list[Path]:
    """Собери все Python-файлы в директории с учетом исключений."""
    return [
        p for p in sorted(directory.rglob("*.py"))
        if p.is_file() and not _matches_exclude(p, root, excludes)
    ]


def _collect_file_if_valid(path: Path, root: Path, excludes: Sequence[str]) -> list[Path]:
    """Верни файл в списке, если он является валидным Python-файлом."""
    if path.suffix != ".py" or _matches_exclude(path, root, excludes):
        return []
    return [path]


def _collect_single_path(path: Path, root: Path, excludes: Sequence[str]) -> list[Path]:
    """Собери Python-файлы из переданного пути."""
    if path.is_file():
        return _collect_file_if_valid(path, root, excludes)
    if path.is_dir():
        return _collect_dir_files(path, root, excludes)
    return []


def collect_python_files(paths: Sequence[str | Path], config: Config) -> list[Path]:
    """Собери уникальный список Python-файлов для проверки."""
    collected: list[Path] = []
    root = Path.cwd()

    for p in paths:
        path = Path(p)
        if path.exists():
            collected.extend(_collect_single_path(path, root, config.exclude))

    return sorted(set(collected), key=lambda x: str(x))


def build_parser() -> argparse.ArgumentParser:
    """Сконфигурируй парсер аргументов командной строки."""
    parser = argparse.ArgumentParser(
        prog="complexity-guard",
        description="Контроль алгоритмической сложности, глубины циклов и ветвлений.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=["."],
        help="Файлы или директории для проверки (по умолчанию текущая директория).",
    )
    parser.add_argument(
        "--max-loop-depth",
        type=int,
        default=None,
        help="Максимальная глубина циклов for/async for (по умолчанию: 2).",
    )
    parser.add_argument(
        "--max-complexity",
        type=int,
        default=None,
        help="Максимальная цикломатическая сложность функции (по умолчанию: 5, strict: 3).",
    )
    parser.add_argument(
        "--max-branches",
        type=int,
        default=None,
        help="Максимальное число ветвлений if/match/try/ternary (по умолчанию: 6).",
    )
    parser.add_argument(
        "--max-returns",
        type=int,
        default=None,
        help="Максимальное число return statements в функции (по умолчанию: 4).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        default=None,
        help="Включить строгий режим (max-complexity=3, max-branches=4, max-returns=3).",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        help="Шаблоны исключений (через запятую или повторным флагом).",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Путь к конфигурационному файлу pyproject.toml.",
    )
    parser.add_argument(
        "--lang",
        choices=["ru", "en"],
        default=None,
        help="Язык сообщений об ошибках и сводки (ru или en, по умолчанию ru).",
    )
    parser.add_argument(
        "--format",
        choices=["text", "github", "json"],
        default="text",
        help="Формат вывода: text (UNIX), github (workflow commands) или json.",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Тихий режим: выводить только нарушения без итоговой сводки.",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Показать версию программы и завершить работу.",
    )
    return parser


def _collect_all_violations(files: list[Path], config: Config) -> list[tuple[Path, Violation]]:
    """Проверь список файлов и собери все найденные нарушения."""
    violations: list[tuple[Path, Violation]] = []
    for file_path in files:
        for v in check_file(file_path, config=config):
            violations.append((file_path, v))
    return violations


def _output_json(violations: list[tuple[Path, Violation]]) -> None:
    """Выведи нарушения в формате JSON."""
    data = [
        {
            "file": str(p),
            "line": v.line,
            "column": v.column,
            "code": v.code,
            "message": v.message,
            "symbol": v.symbol,
        }
        for p, v in violations
    ]
    sys.stdout.write(json.dumps(data, indent=2) + "\n")


def _output_github(violations: list[tuple[Path, Violation]]) -> None:
    """Выведи нарушения в формате GitHub Actions workflow commands."""
    for p, v in violations:
        sys.stdout.write(f"::error file={p},line={v.line},col={v.column}::{v.code} {v.message}\n")


def _output_text(violations: list[tuple[Path, Violation]], files_count: int, quiet: bool, lang: str = "en") -> None:
    """Выведи нарушения в стандартном формате UNIX."""
    for p, v in violations:
        sys.stdout.write(f"{v.format(p)}\n")

    if not quiet:
        if violations:
            files_with_errors = len({p for p, _ in violations})
            if lang == "ru":
                sys.stderr.write(
                    f"\nНайдено нарушений: {len(violations)} в {files_with_errors} файл(ах).\n"
                )
            else:
                sys.stderr.write(
                    f"\nFound {len(violations)} violation(s) in {files_with_errors} file(s).\n"
                )
        else:
            if lang == "ru":
                sys.stderr.write(f"Проверено файлов: {files_count}. Нарушений не обнаружено.\n")
            else:
                sys.stderr.write(f"Checked {files_count} file(s). No violations found.\n")


def _output_results(fmt: str, violations: list[tuple[Path, Violation]], files_count: int, quiet: bool, lang: str = "en") -> None:
    """Направь вывод нарушений в соответствующий форматтер."""
    if fmt == "json":
        _output_json(violations)
    elif fmt == "github":
        _output_github(violations)
    else:
        _output_text(violations, files_count, quiet, lang)


def _parse_excludes_arg(raw: Sequence[str] | None) -> list[str] | None:
    """Разбери список шаблонов исключений из аргументов CLI."""
    if not raw:
        return None
    items: list[str] = []
    for item in raw:
        items.extend([x.strip() for x in item.split(",") if x.strip()])
    return items


def run(argv: Sequence[str] | None = None) -> int:
    """Запусти проверку файлов и верни код возврата 0 или 1."""
    parser = build_parser()
    args = parser.parse_args(argv)

    config = get_config(
        config_file=args.config,
        max_loop_depth=args.max_loop_depth,
        max_complexity=args.max_complexity,
        max_branches=args.max_branches,
        max_returns=args.max_returns,
        strict=args.strict,
        lang=args.lang,
        exclude=_parse_excludes_arg(args.exclude),
    )

    files = collect_python_files(args.paths, config)
    violations = _collect_all_violations(files, config)
    _output_results(args.format, violations, len(files), args.quiet, config.lang)
    return 1 if violations else 0


def main() -> None:
    """Точка входа в CLI-утилиту."""
    sys.exit(run())


if __name__ == "__main__":
    main()
