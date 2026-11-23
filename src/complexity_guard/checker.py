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


_MESSAGES: dict[str, dict[str, str]] = {
    "ru": {
        "CG001": "Глубина вложенных циклов {depth} превышает максимум {limit} (вынесите во вспомогательную функцию или используйте O(1) поиск через set/dict)",
        "CG002": "Функция '{name}' имеет цикломатическую сложность {complexity} (лимит: {limit})",
        "CG003": "Функция '{name}' содержит {branches} ветвлений (лимит: {limit})",
        "CG004": "Функция '{name}' содержит {returns} точек выхода return (лимит: {limit})",
        "CG005": "Линейный поиск '{target}' через 'in' внутри цикла превращает сложность в O(N²). Преобразуйте коллекцию в set перед циклом или используйте словарь",
        "CG006": "Вызов O(N) метода '{method}' на коллекции '{target}' внутри цикла приводит к сложности O(N²). Вынесите индексацию до цикла или используйте deque",
        "CG007": "Конкатенация строк '{target} += ...' внутри цикла приводит к квадратичному копированию памяти O(N²). Собирайте части в список и используйте ''.join(...)",
        "CG008": "Глубина вложенности списковых включений {depth} превышает максимум {limit} (сложность O(N²)+). Разверните в явную структуру или плоскую итерацию",
    },
    "en": {
        "CG001": "Loop nesting depth {depth} exceeds limit of {limit} (consider extracting to a helper or using O(1) lookup/flat map)",
        "CG002": "Function '{name}' has cyclomatic complexity of {complexity} (limit: {limit})",
        "CG003": "Function '{name}' has {branches} branches (limit: {limit})",
        "CG004": "Function '{name}' has {returns} returns (limit: {limit})",
        "CG005": "Linear search '{target}' with 'in' inside a loop causes O(N²) complexity. Convert collection to set before loop or use a dict",
        "CG006": "Call to O(N) method '{method}' on '{target}' inside a loop causes O(N²) complexity. Precompute indices before loop or use collections.deque",
        "CG007": "String concatenation '{target} += ...' inside a loop causes quadratic O(N²) memory copying. Collect parts in a list and use ''.join(...)",
        "CG008": "Comprehension nesting depth {depth} exceeds limit of {limit} (O(N²)+ complexity). Flatten or refactor to generator",
    },
}


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


class _TypeKind:
    """Классификация типов коллекций и переменных для оценки сложности."""

    UNKNOWN = 0
    LINEAR = 1  # list, tuple, sequence, deque
    HASH = 2    # set, dict, mapping, frozenset, keysview
    STRING = 3  # str
    NUMBER = 4  # int, float


_LINEAR_TYPE_NAMES = frozenset({"list", "sequence", "tuple", "iterable", "deque"})
_HASH_TYPE_NAMES = frozenset({"set", "dict", "mapping", "frozenset", "keysview"})
_STRING_TYPE_NAMES = frozenset({"str"})
_NUMBER_TYPE_NAMES = frozenset({"int", "float"})
_STRING_VAR_NAMES = frozenset({"s", "text", "string", "buffer", "html", "sql", "output", "msg", "message"})

_LITERAL_TYPE_MAP: dict[type[ast.AST], int] = {
    ast.List: _TypeKind.LINEAR,
    ast.Tuple: _TypeKind.LINEAR,
    ast.ListComp: _TypeKind.LINEAR,
    ast.Set: _TypeKind.HASH,
    ast.Dict: _TypeKind.HASH,
    ast.SetComp: _TypeKind.HASH,
    ast.DictComp: _TypeKind.HASH,
    ast.JoinedStr: _TypeKind.STRING,
}
_FUNC_LINEAR = frozenset({"list", "tuple", "deque", "split", "splitlines", "findall"})
_FUNC_HASH = frozenset({"set", "frozenset", "dict", "keys", "values", "items"})


def _classify_name(name: str) -> int:
    """Определи класс типа по строковому имени типа."""
    if name in _LINEAR_TYPE_NAMES:
        return _TypeKind.LINEAR
    if name in _HASH_TYPE_NAMES:
        return _TypeKind.HASH
    if name in _STRING_TYPE_NAMES:
        return _TypeKind.STRING
    return _TypeKind.NUMBER if name in _NUMBER_TYPE_NAMES else _TypeKind.UNKNOWN


def _type_from_binop_union(node: ast.BinOp) -> int:
    """Извлеки тип объединения типов через побитовое ИЛИ (|)."""
    if isinstance(node.op, ast.BitOr):
        left_t = _type_from_annotation(node.left)
        return left_t if left_t != _TypeKind.UNKNOWN else _type_from_annotation(node.right)
    return _TypeKind.UNKNOWN


def _type_from_annotation(node: ast.AST | None) -> int:
    """Извлеки классификацию типа из аннотации типа."""
    if isinstance(node, (ast.Name, ast.Attribute)):
        raw = node.id if isinstance(node, ast.Name) else node.attr
        return _classify_name(raw.lower())
    if isinstance(node, ast.Subscript):
        return _type_from_annotation(node.value)
    if isinstance(node, ast.BinOp):
        return _type_from_binop_union(node)
    return _TypeKind.UNKNOWN


def _type_from_constant(val: object) -> int:
    """Определи тип константы."""
    if isinstance(val, str):
        return _TypeKind.STRING
    return _TypeKind.NUMBER if isinstance(val, (int, float)) else _TypeKind.UNKNOWN


def _type_from_call(node: ast.Call) -> int:
    """Определи возвращаемый тип стандартного вызова."""
    name = node.func.id.lower() if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "").lower()
    if name in _FUNC_LINEAR:
        return _TypeKind.LINEAR
    if name in _FUNC_HASH:
        return _TypeKind.HASH
    return _TypeKind.STRING if name == "str" else _TypeKind.UNKNOWN


def _type_from_value(node: ast.AST | None) -> int:
    """Определи класс типа выражения по литералу или вызову фабрики."""
    if node is None:
        return _TypeKind.UNKNOWN
    t = _LITERAL_TYPE_MAP.get(type(node))
    if t is not None:
        return t
    if isinstance(node, (ast.Constant, ast.Call)):
        return _type_from_constant(node.value) if isinstance(node, ast.Constant) else _type_from_call(node)
    return _TypeKind.UNKNOWN


def _scan_ann_assign(stmt: ast.AnnAssign, types: dict[str, int]) -> None:
    """Собери тип из аннотированного присваивания."""
    if isinstance(stmt.target, ast.Name):
        t = _type_from_annotation(stmt.annotation)
        effective = t if t != _TypeKind.UNKNOWN else _type_from_value(stmt.value)
        if effective != _TypeKind.UNKNOWN:
            types[stmt.target.id] = effective


def _scan_assign(stmt: ast.Assign, types: dict[str, int]) -> None:
    """Собери тип из обычного присваивания."""
    t = _type_from_value(stmt.value)
    if t != _TypeKind.UNKNOWN:
        for target in stmt.targets:
            if isinstance(target, ast.Name):
                types[target.id] = t


def _scan_block_types(statements: list[ast.stmt]) -> dict[str, int]:
    """Извлеки типы переменных из аннотаций и присваиваний в блоке кода."""
    types: dict[str, int] = {}
    for stmt in statements:
        if isinstance(stmt, ast.AnnAssign):
            _scan_ann_assign(stmt, types)
        elif isinstance(stmt, ast.Assign):
            _scan_assign(stmt, types)
    return types


def _build_func_scope(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, int]:
    """Собери таблицу типов аргументов и локальных переменных функции."""
    scope: dict[str, int] = {}
    for arg in (
        func_node.args.posonlyargs
        + func_node.args.args
        + func_node.args.kwonlyargs
    ):
        t = _type_from_annotation(arg.annotation)
        if t != _TypeKind.UNKNOWN:
            scope[arg.arg] = t
        elif arg.arg.endswith(("_list", "_tuple", "_seq", "_array")):
            scope[arg.arg] = _TypeKind.LINEAR
        elif arg.arg.endswith(("_set", "_dict", "_map")):
            scope[arg.arg] = _TypeKind.HASH

    scope.update(_scan_block_types(func_node.body))
    return scope


def _get_comprehension_depth(comp: ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp) -> int:
    """Вычисли совокупную глубину генераторов и вложенных включений."""
    depth = len(comp.generators)
    inner = comp.elt if hasattr(comp, "elt") else getattr(comp, "value", None)
    if isinstance(inner, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
        depth += _get_comprehension_depth(inner)
    return depth


def _is_linear_tuple(node: ast.Tuple) -> bool:
    """Проверь, является ли кортеж динамическим или длинным."""
    return any(not isinstance(e, ast.Constant) for e in node.elts) or len(node.elts) > 5


def _is_linear_call(node: ast.Call) -> bool:
    """Проверь, возвращает ли вызов линейную последовательность."""
    name = node.func.id.lower() if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "").lower()
    return name in _FUNC_LINEAR


def _is_index_zero_arg(args: list[ast.expr]) -> bool:
    """Проверь равенство первого аргумента целочисленному нулю 0."""
    if not args:
        return False
    first = args[0]
    return isinstance(first, ast.Constant) and first.value == 0


class ComplexityChecker(ast.NodeVisitor):
    """Обходи AST и фиксируй нарушения правил сложности."""

    def __init__(self, config: Config, suppressions: dict[int, set[str]]) -> None:
        """Инициализируй чекер конфигурацией и таблицей подавлений."""
        self.config = config
        self.suppressions = suppressions
        self.violations: list[Violation] = []
        self._loop_depth = 0
        self._scopes: list[dict[str, int]] = [{}]

    def _msg(self, code: str, **kwargs: object) -> str:
        """Сформируй текст сообщения на настроенном языке (ru/en)."""
        lang = self.config.lang if self.config.lang in _MESSAGES else "en"
        template = _MESSAGES[lang].get(code, "")
        return template.format(**kwargs)

    def _lookup_type(self, name: str) -> int:
        """Найди тип переменной в стеке областей видимости."""
        for scope in reversed(self._scopes):
            if name in scope:
                return scope[name]
        return self._infer_name_suffix_type(name)

    def _infer_name_suffix_type(self, name: str) -> int:
        """Определи тип по семантическому суффиксу имени переменной."""
        if name.endswith(("_list", "_tuple", "_seq", "_array")):
            return _TypeKind.LINEAR
        if name.endswith(("_set", "_dict", "_map")):
            return _TypeKind.HASH
        return _TypeKind.STRING if name in _STRING_VAR_NAMES else _TypeKind.UNKNOWN

    def visit_For(self, node: ast.For) -> None:
        """Проверь глубину синхронного цикла for."""
        self._check_loop(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        """Проверь глубину асинхронного цикла async for."""
        self._check_loop(node)

    def visit_While(self, node: ast.While) -> None:
        """Проверь глубину цикла while."""
        self._check_loop(node)

    def _check_loop(self, node: ast.For | ast.AsyncFor | ast.While) -> None:
        """Зафиксируй нарушение при превышении лимита вложенности циклов."""
        self._loop_depth += 1
        if self.config.max_loop_depth > 0 and self._loop_depth > self.config.max_loop_depth:
            code = "CG001"
            col = node.col_offset + 1
            if not _is_suppressed(code, node.lineno, self.suppressions):
                msg = self._msg(code, depth=self._loop_depth, limit=self.config.max_loop_depth)
                self.violations.append(
                    Violation(code=code, line=node.lineno, column=col, message=msg, symbol="<loop>")
                )

        self.generic_visit(node)
        self._loop_depth -= 1

    def _is_linear_named_target(self, node: ast.AST, target_name: str) -> tuple[bool, str]:
        """Проверь линейность переменной или атрибута."""
        if isinstance(node, ast.Name):
            t = self._lookup_type(node.id)
            return (t == _TypeKind.LINEAR or (self.config.strict and t != _TypeKind.HASH)), node.id
        if isinstance(node, ast.Attribute):
            is_linear = node.attr.endswith(("_list", "_tuple", "_seq", "_array"))
            return is_linear, target_name
        return False, target_name

    def _is_linear_target(self, node: ast.AST) -> tuple[bool, str]:
        """Определи, является ли правый операнд 'in' линейной коллекцией O(N)."""
        target_name = ast.unparse(node) if hasattr(ast, "unparse") else "<target>"
        if isinstance(node, (ast.List, ast.ListComp, ast.GeneratorExp)):
            return True, target_name
        if isinstance(node, ast.Tuple):
            return _is_linear_tuple(node), target_name
        if isinstance(node, ast.Call):
            return _is_linear_call(node), target_name
        return self._is_linear_named_target(node, target_name)

    def _check_compare_op(self, node: ast.Compare, op: ast.cmpop, comparator: ast.AST) -> None:
        """Проверь отдельную операцию сравнения на линейный поиск."""
        if isinstance(op, (ast.In, ast.NotIn)):
            is_linear, target_repr = self._is_linear_target(comparator)
            if is_linear and not _is_suppressed("CG005", node.lineno, self.suppressions):
                msg = self._msg("CG005", target=target_repr)
                self.violations.append(
                    Violation(code="CG005", line=node.lineno, column=node.col_offset + 1, message=msg, symbol=target_repr)
                )

    def visit_Compare(self, node: ast.Compare) -> None:
        """Проверь линейный поиск in/not in внутри циклов (CG005)."""
        if self._loop_depth > 0 and self.config.check_linear_in_loop:
            for op, comparator in zip(node.ops, node.comparators):
                self._check_compare_op(node, op, comparator)
        self.generic_visit(node)

    def _check_pop_insert_call(self, node: ast.Call, attr: str, target: str) -> tuple[bool, str, str]:
        """Проверь вызовы pop(0) и insert(0, ...)."""
        if not _is_index_zero_arg(node.args):
            return False, "", ""
        if attr in ("pop", "insert"):
            desc = "pop(0)" if attr == "pop" else "insert(0, ...)"
            return True, desc, target
        return False, "", ""

    def _check_remove_call(self, value_node: ast.AST, attr: str, target: str) -> tuple[bool, str, str]:
        """Проверь вызов .remove() на коллекции."""
        t = self._lookup_type(value_node.id) if isinstance(value_node, ast.Name) else _TypeKind.UNKNOWN
        return (t != _TypeKind.HASH), attr, target

    def _check_quadratic_call(self, node: ast.Call) -> tuple[bool, str, str]:
        """Определи наличие вызова O(N) метода в цикле."""
        if not isinstance(node.func, ast.Attribute):
            return False, "", ""
        attr = node.func.attr
        target = ast.unparse(node.func.value) if hasattr(ast, "unparse") else "<col>"
        if attr in ("index", "count"):
            return True, attr, target
        if attr == "remove":
            return self._check_remove_call(node.func.value, attr, target)
        return self._check_pop_insert_call(node, attr, target)

    def visit_Call(self, node: ast.Call) -> None:
        """Проверь вызовы O(N) методов списков внутри циклов (CG006)."""
        if self._loop_depth > 0 and self.config.check_quadratic_methods:
            is_viol, desc, target = self._check_quadratic_call(node)
            if is_viol and not _is_suppressed("CG006", node.lineno, self.suppressions):
                msg = self._msg("CG006", method=desc, target=target)
                self.violations.append(
                    Violation(code="CG006", line=node.lineno, column=node.col_offset + 1, message=msg, symbol=desc)
                )
        self.generic_visit(node)

    def _is_string_value(self, val: ast.AST) -> bool:
        """Проверь, является ли выражение строковым значением."""
        if isinstance(val, ast.Constant):
            return isinstance(val.value, str)
        is_str_call = bool(isinstance(val, ast.Call) and isinstance(val.func, ast.Name) and val.func.id == "str")
        return isinstance(val, ast.JoinedStr) or is_str_call

    def _is_string_aug_assign(self, node: ast.AugAssign) -> bool:
        """Определи, относится ли += к конкатенации строк."""
        if not isinstance(node.target, ast.Name):
            return False
        t = self._lookup_type(node.target.id)
        if t == _TypeKind.STRING:
            return True
        if t == _TypeKind.NUMBER:
            return False
        return self._is_string_value(node.value)

    def _record_string_concat(self, node: ast.AugAssign) -> None:
        """Зафиксируй нарушение правила конкатенации строк (CG007)."""
        target_repr = ast.unparse(node.target) if hasattr(ast, "unparse") else "<str>"
        if not _is_suppressed("CG007", node.lineno, self.suppressions):
            msg = self._msg("CG007", target=target_repr)
            self.violations.append(
                Violation(code="CG007", line=node.lineno, column=node.col_offset + 1, message=msg, symbol=target_repr)
            )

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        """Проверь квадратичную конкатенацию строк += в цикле (CG007)."""
        if self._loop_depth > 0 and self.config.check_string_concat:
            if isinstance(node.op, ast.Add) and self._is_string_aug_assign(node):
                self._record_string_concat(node)
        self.generic_visit(node)

    def visit_ListComp(self, node: ast.ListComp) -> None:
        """Проверь вложенность списковых включений (CG008)."""
        self._check_comprehension(node)
        self.generic_visit(node)

    def visit_SetComp(self, node: ast.SetComp) -> None:
        """Проверь вложенность включений множеств (CG008)."""
        self._check_comprehension(node)
        self.generic_visit(node)

    def visit_DictComp(self, node: ast.DictComp) -> None:
        """Проверь вложенность словарных включений (CG008)."""
        self._check_comprehension(node)
        self.generic_visit(node)

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        """Проверь вложенность генераторных выражений (CG008)."""
        self._check_comprehension(node)
        self.generic_visit(node)

    def _check_comprehension(
        self,
        node: ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp,
    ) -> None:
        """Зафиксируй нарушение при превышении лимита вложенности comprehension."""
        if self.config.max_comprehension_depth <= 0:
            return
        depth = _get_comprehension_depth(node)
        if depth > self.config.max_comprehension_depth:
            code = "CG008"
            if not _is_suppressed(code, node.lineno, self.suppressions):
                msg = self._msg(code, depth=depth, limit=self.config.max_comprehension_depth)
                self.violations.append(
                    Violation(
                        code=code,
                        line=node.lineno,
                        column=node.col_offset + 1,
                        message=msg,
                        symbol="<comprehension>",
                    )
                )

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Проверь сложность синхронной функции."""
        self._check_function(node)
        scope = _build_func_scope(node)
        self._scopes.append(scope)
        self.generic_visit(node)
        self._scopes.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Проверь сложность асинхронной функции."""
        self._check_function(node)
        scope = _build_func_scope(node)
        self._scopes.append(scope)
        self.generic_visit(node)
        self._scopes.pop()

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
        if self.config.max_complexity <= 0:
            return
        complexity = _compute_cyclomatic_complexity(node)
        if complexity > self.config.max_complexity:
            code = "CG002"
            if not _is_suppressed(code, node.lineno, self.suppressions, header):
                msg = self._msg(code, name=node.name, complexity=complexity, limit=self.config.max_complexity)
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
        if self.config.max_branches <= 0:
            return
        branches = _compute_branches(node)
        if branches > self.config.max_branches:
            code = "CG003"
            if not _is_suppressed(code, node.lineno, self.suppressions, header):
                msg = self._msg(code, name=node.name, branches=branches, limit=self.config.max_branches)
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
        if self.config.max_returns <= 0:
            return
        returns = _compute_returns(node)
        if returns > self.config.max_returns:
            code = "CG004"
            if not _is_suppressed(code, node.lineno, self.suppressions, header):
                msg = self._msg(code, name=node.name, returns=returns, limit=self.config.max_returns)
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
    if hasattr(tree, "body"):
        checker._scopes[0].update(_scan_block_types(tree.body))
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
