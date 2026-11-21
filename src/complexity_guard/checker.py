"""AST-анализатор сложности кода: глубина циклов, ветвления и возвраты."""

import ast
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterator

from .config import Config

NOQA_PATTERN = re.compile(r"#\s*noqa(?::\s*([a-zA-Z0-9_,\s-]+))?", re.IGNORECASE)

_DECISION_NODES = (
    ast.If,
    ast.IfExp,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.ExceptHandler,
    ast.match_case,
)


@dataclass(frozen=True)
class Violation:
    """Храни данные об обнаруженном нарушении правила сложности."""

    code: str
    line: int
    column: int
    message: str
    symbol: str

    def format(self, file_path: str | Path) -> str:
        """Сформируй строку ошибки в стандартном формате UNIX."""
        return f"{file_path}:{self.line}:{self.column}: {self.code} {self.message}"


def _parse_noqa_codes(raw: str | None) -> set[str]:
    """Извлеки коды подавления из комментария noqa."""
    if not raw:
        return {"*"}
    return {c.strip().upper() for c in raw.split(",") if c.strip()}


def _parse_suppressions(source: str) -> dict[int, set[str]]:
    """Собери сопоставление номеров строк и кодов подавления."""
    suppressions: dict[int, set[str]] = {}
    for lineno, line in enumerate(source.splitlines(), start=1):
        match = NOQA_PATTERN.search(line)
        if match:
            suppressions[lineno] = _parse_noqa_codes(match.group(1))
    return suppressions


def _matches_tag(code: str, tags: set[str]) -> bool:
    """Проверь соответствие кода нарушения тегам подавления."""
    return "*" in tags or code in tags or ("COMPLEXITY" in tags and code.startswith("CG00"))


def _is_suppressed(
    code: str,
    lineno: int,
    suppressions: dict[int, set[str]],
    extra_lines: list[int] | None = None,
) -> bool:
    """Проверь наличие подавления на строке или в заголовке функции."""
    lines = [lineno, *(extra_lines or ())]
    for line in lines:
        tags = suppressions.get(line)
        if tags and _matches_tag(code, tags):
            return True
    return False


def _iter_shallow_nodes(node: ast.AST) -> Iterator[ast.AST]:
    """Обойди дочерние узлы функции без захода во вложенные def и lambda."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        yield child
        yield from _iter_shallow_nodes(child)


def _comp_increment(comp: ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp) -> int:
    """Посчитай сложность генераторов и фильтров в comprehension."""
    return sum(1 + len(gen.ifs) for gen in comp.generators)


def _node_complexity(node: ast.AST) -> int:
    """Определи вклад узла AST в цикломатическую сложность."""
    if isinstance(node, _DECISION_NODES):
        return 1
    if isinstance(node, ast.BoolOp):
        return len(node.values) - 1
    if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
        return _comp_increment(node)
    return 0


def _compute_cyclomatic_complexity(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Вычисли цикломатическую сложность функции по Маккейбу."""
    return 1 + sum(_node_complexity(child) for child in _iter_shallow_nodes(func_node))


def _compute_branches(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Посчитай количество ветвлений внутри функции."""
    count = 0
    for child in _iter_shallow_nodes(func_node):
        if isinstance(child, (ast.If, ast.IfExp, ast.match_case, ast.ExceptHandler)):
            count += 1
    return count


def _compute_returns(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Посчитай количество операторов return внутри функции."""
    count = 0
    for child in _iter_shallow_nodes(func_node):
        if isinstance(child, ast.Return):
            count += 1
    return count


class ComplexityChecker(ast.NodeVisitor):
    """Обходи AST и фиксируй нарушения правил сложности."""

    def __init__(self, config: Config, suppressions: dict[int, set[str]]) -> None:
        """Инициализируй чекер конфигурацией и таблицей подавлений."""
        self.config = config
        self.suppressions = suppressions
        self.violations: list[Violation] = []
        self._loop_depth = 0

    def visit_For(self, node: ast.For) -> None:
        """Проверь глубину синхронного цикла for."""
        self._check_loop(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        """Проверь глубину асинхронного цикла async for."""
        self._check_loop(node)

    def _check_loop(self, node: ast.For | ast.AsyncFor) -> None:
        """Зафиксируй нарушение при превышении лимита вложенности циклов."""
        self._loop_depth += 1
        if self._loop_depth > self.config.max_loop_depth:
            code = "CG001"
            col = node.col_offset + 1
            if not _is_suppressed(code, node.lineno, self.suppressions):
                msg = (
                    f"Loop nesting depth {self._loop_depth} exceeds limit of "
                    f"{self.config.max_loop_depth} (consider extracting to a helper "
                    f"or using O(1) lookup/flat map)"
                )
                self.violations.append(
                    Violation(code=code, line=node.lineno, column=col, message=msg, symbol="<loop>")
                )

        self.generic_visit(node)
        self._loop_depth -= 1

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Проверь сложность синхронной функции."""
        self._check_function(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Проверь сложность асинхронной функции."""
        self._check_function(node)
        self.generic_visit(node)

    def _collect_header_lines(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[int]:
        """Собери номера строк сигнатуры и декораторов функции."""
        lines = [node.lineno]
        for deco in node.decorator_list:
            lines.append(deco.lineno)
        if node.body:
            lines.extend(range(node.lineno, node.body[0].lineno))
        return lines

    def _check_func_complexity(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        col: int,
        header: list[int],
    ) -> None:
        """Проверь цикломатическую сложность функции (CG002)."""
        complexity = _compute_cyclomatic_complexity(node)
        if complexity > self.config.max_complexity:
            code = "CG002"
            if not _is_suppressed(code, node.lineno, self.suppressions, header):
                msg = (
                    f"Function '{node.name}' has cyclomatic complexity of "
                    f"{complexity} (limit: {self.config.max_complexity})"
                )
                self.violations.append(
                    Violation(code=code, line=node.lineno, column=col, message=msg, symbol=node.name)
                )

    def _check_func_branches(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        col: int,
        header: list[int],
    ) -> None:
        """Проверь количество ветвлений в функции (CG003)."""
        branches = _compute_branches(node)
        if branches > self.config.max_branches:
            code = "CG003"
            if not _is_suppressed(code, node.lineno, self.suppressions, header):
                msg = f"Function '{node.name}' has {branches} branches (limit: {self.config.max_branches})"
                self.violations.append(
                    Violation(code=code, line=node.lineno, column=col, message=msg, symbol=node.name)
                )

    def _check_func_returns(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        col: int,
        header: list[int],
    ) -> None:
        """Проверь количество точек выхода return в функции (CG004)."""
        returns = _compute_returns(node)
        if returns > self.config.max_returns:
            code = "CG004"
            if not _is_suppressed(code, node.lineno, self.suppressions, header):
                msg = f"Function '{node.name}' has {returns} returns (limit: {self.config.max_returns})"
                self.violations.append(
                    Violation(code=code, line=node.lineno, column=col, message=msg, symbol=node.name)
                )

    def _check_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        """Проанализируй функцию по правилам CG002, CG003 и CG004."""
        col = node.col_offset + 1
        header = self._collect_header_lines(node)
        self._check_func_complexity(node, col, header)
        self._check_func_branches(node, col, header)
        self._check_func_returns(node, col, header)


def _handle_syntax_error(exc: SyntaxError, suppressions: dict[int, set[str]]) -> list[Violation]:
    """Сформируй нарушение CG000 при синтаксической ошибке в файле."""
    lineno = exc.lineno or 1
    col = (exc.offset or 0) + 1
    if _is_suppressed("CG000", lineno, suppressions):
        return []
    return [
        Violation(
            code="CG000",
            line=lineno,
            column=col,
            message=f"SyntaxError: {exc.msg}",
            symbol="<syntax>",
        )
    ]


def check_source(source: str, config: Config | None = None, filename: str = "<string>") -> list[Violation]:
    """Выполни проверку исходного кода Python и верни список нарушений."""
    effective_config = config or Config()
    suppressions = _parse_suppressions(source)

    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as exc:
        return _handle_syntax_error(exc, suppressions)

    checker = ComplexityChecker(effective_config, suppressions)
    checker.visit(tree)
    return sorted(checker.violations, key=lambda v: (v.line, v.column, v.code))


def check_file(file_path: Path | str, config: Config | None = None) -> list[Violation]:
    """Прочитай файл и верни список нарушений сложности."""
    path = Path(file_path)
    try:
        source = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as exc:
        return [
            Violation(
                code="CG000",
                line=1,
                column=1,
                message=f"Failed to read file: {exc}",
                symbol="<file>",
            )
        ]

    return check_source(source, config=config, filename=str(path))
