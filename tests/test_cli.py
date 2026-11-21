"""Тесты для интерфейса командной строки complexity-guard."""

import json
from pathlib import Path

from complexity_guard.cli import run


def test_cli_clean_file_returns_zero(tmp_path: Path, capsys) -> None:
    """Проверь возврат кода 0 и сообщения об успехе при проверке чистого файла."""
    file = tmp_path / "clean.py"
    file.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

    code = run([str(file)])
    assert code == 0
    captured = capsys.readouterr()
    assert "No violations found" in captured.err


def test_cli_violation_returns_one(tmp_path: Path, capsys) -> None:
    """Проверь возврат кода 1 и вывод ошибки при обнаружении нарушения."""
    file = tmp_path / "dirty.py"
    file.write_text(
        """
def triple_loop(x):
    for a in x:
        for b in a:
            for c in b:
                pass
""",
        encoding="utf-8",
    )

    code = run([str(file)])
    assert code == 1
    captured = capsys.readouterr()
    assert "CG001" in captured.out
    assert "Loop nesting depth 3 exceeds limit of 2" in captured.out
    assert "Found 1 violation" in captured.err


def test_cli_lang_ru(tmp_path: Path, capsys) -> None:
    """Проверь локализованный вывод на русском языке при флаге --lang=ru."""
    file = tmp_path / "dirty.py"
    file.write_text(
        """
def triple_loop(x):
    for a in x:
        for b in a:
            for c in b:
                pass
""",
        encoding="utf-8",
    )

    code = run(["--lang=ru", str(file)])
    assert code == 1
    captured = capsys.readouterr()
    assert "CG001" in captured.out
    assert "Глубина вложенных циклов 3 превышает максимум 2" in captured.out
    assert "Найдено нарушений: 1" in captured.err


def test_cli_format_json(tmp_path: Path, capsys) -> None:
    """Проверь сериализацию нарушений в формат JSON при ключе --format=json."""
    file = tmp_path / "dirty.py"
    file.write_text(
        """
def triple_loop(x):
    for a in x:
        for b in a:
            for c in b:
                pass
""",
        encoding="utf-8",
    )

    code = run(["--format=json", str(file)])
    assert code == 1
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert len(data) == 1
    assert data[0]["code"] == "CG001"
    assert data[0]["line"] == 5


def test_cli_format_github(tmp_path: Path, capsys) -> None:
    """Проверь вывод в формате команд аннотаций GitHub Actions."""
    file = tmp_path / "dirty.py"
    file.write_text(
        """
def triple_loop(x):
    for a in x:
        for b in a:
            for c in b:
                pass
""",
        encoding="utf-8",
    )

    code = run(["--format=github", str(file)])
    assert code == 1
    captured = capsys.readouterr()
    assert "::error file=" in captured.out
    assert "CG001" in captured.out


def test_cli_exclude_flag(tmp_path: Path, capsys) -> None:
    """Проверь пропуск файлов, попадающих под шаблон исключения --exclude."""
    ignored_dir = tmp_path / "ignored"
    ignored_dir.mkdir()
    file = ignored_dir / "bad.py"
    file.write_text(
        """
def triple(x):
    for a in x:
        for b in a:
            for c in b:
                pass
""",
        encoding="utf-8",
    )

    code = run(["--exclude=ignored", str(tmp_path)])
    assert code == 0
    captured = capsys.readouterr()
    assert "No violations found" in captured.err


def test_cli_quiet_mode(tmp_path: Path, capsys) -> None:
    """Проверь подавление итоговой сводки в тихом режиме -q/--quiet."""
    file = tmp_path / "clean.py"
    file.write_text("x = 1\n", encoding="utf-8")

    code = run(["-q", str(file)])
    assert code == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
