"""Тесты для правил контроля сложности CG001-CG004."""

from complexity_guard.checker import check_source
from complexity_guard.config import Config


def test_cg001_single_loop_passes() -> None:
    """Проверь успешный проход одиночного цикла."""
    source = """
def process(items):
    for item in items:
        print(item)
"""
    violations = check_source(source)
    assert not any(v.code == "CG001" for v in violations)


def test_cg001_double_loop_passes_by_default() -> None:
    """Проверь допустимость двойного цикла при лимите по умолчанию 2."""
    source = """
def process(matrix):
    for row in matrix:
        for val in row:
            print(val)
"""
    violations = check_source(source)
    assert not any(v.code == "CG001" for v in violations)


def test_cg001_triple_loop_triggers_violation() -> None:
    """Проверь фиксацию нарушения CG001 при тройной вложенности циклов."""
    source = """
def search_3d(cube):
    for plane in cube:
        for row in plane:
            for item in row:
                if item == 42:
                    return item
"""
    violations = check_source(source)
    cg001 = [v for v in violations if v.code == "CG001"]
    assert len(cg001) == 1
    assert cg001[0].line == 5
    assert "Loop nesting depth 3 exceeds limit of 2" in cg001[0].message


def test_cg001_async_for_counts_towards_depth() -> None:
    """Проверь учет асинхронных циклов async for в глубине вложенности."""
    source = """
async def fetch_all(streams):
    async for stream in streams:
        for chunk in stream:
            async for record in chunk:
                yield record
"""
    violations = check_source(source)
    cg001 = [v for v in violations if v.code == "CG001"]
    assert len(cg001) == 1
    assert cg001[0].line == 5


def test_cg001_comprehensions_do_not_increase_loop_depth() -> None:
    """Убедись, что списковые включения не увеличивают глубину for-циклов."""
    source = """
def transform(data):
    for row in data:
        items = [x * 2 for x in row if x > 0]
        mapped = {k: v for k, v in enumerate(items)}
        for item in items:
            pass
"""
    violations = check_source(source)
    assert not any(v.code == "CG001" for v in violations)


def test_cg001_custom_threshold() -> None:
    """Проверь работу настраиваемого порога глубины циклов."""
    source = """
def process(matrix):
    for row in matrix:
        for val in row:
            pass
"""
    config = Config(max_loop_depth=1)
    violations = check_source(source, config=config)
    cg001 = [v for v in violations if v.code == "CG001"]
    assert len(cg001) == 1
    assert "exceeds limit of 1" in cg001[0].message


def test_cg002_cyclomatic_complexity_below_threshold() -> None:
    """Проверь проход функции с цикломатической сложностью в пределах нормы."""
    source = """
def simple_decision(a, b):
    if a > 0:
        return a
    elif b > 0:
        return b
    return 0
"""
    violations = check_source(source)
    assert not any(v.code == "CG002" for v in violations)


def test_cg002_cyclomatic_complexity_exceeds_threshold() -> None:
    """Проверь фиксацию нарушения CG002 при превышении сложности функции."""
    source = """
def overly_complex(x):
    if x == 1:
        return 1
    elif x == 2:
        return 2
    elif x == 3:
        return 3
    elif x == 4:
        return 4
    elif x == 5:
        return 5
    return 0
"""
    violations = check_source(source)
    cg002 = [v for v in violations if v.code == "CG002"]
    assert len(cg002) == 1
    assert "cyclomatic complexity of 6" in cg002[0].message
    assert cg002[0].symbol == "overly_complex"


def test_cg002_boolean_operators_add_complexity() -> None:
    """Проверь учет логических операторов and/or в цикломатической сложности."""
    source = """
def bool_decision(a, b, c, d, e):
    if a and b and c and d and e:
        return True
    return False
"""
    violations = check_source(source)
    cg002 = [v for v in violations if v.code == "CG002"]
    assert len(cg002) == 1
    assert "cyclomatic complexity of 6" in cg002[0].message


def test_cg002_strict_mode() -> None:
    """Проверь работу строгого режима с порогом цикломатической сложности 3."""
    source = """
def moderate_func(x):
    if x > 10:
        return 1
    elif x > 5:
        return 2
    elif x > 0:
        return 3
    return 0
"""
    normal = check_source(source, config=Config(max_complexity=5))
    assert not any(v.code == "CG002" for v in normal)

    strict_cfg = Config(strict=True)
    strict_cfg.apply_strict_mode()
    strict_violations = check_source(source, config=strict_cfg)
    cg002 = [v for v in strict_violations if v.code == "CG002"]
    assert len(cg002) == 1
    assert "limit: 3" in cg002[0].message


def test_cg003_branches_within_threshold() -> None:
    """Проверь проход функции с допустимым количеством ветвлений."""
    source = """
def handle(val):
    if val == 1:
        pass
    elif val == 2:
        pass
    elif val == 3:
        pass
    elif val == 4:
        pass
    elif val == 5:
        pass
    elif val == 6:
        pass
"""
    violations = check_source(source)
    assert not any(v.code == "CG003" for v in violations)


def test_cg003_branches_exceeds_threshold() -> None:
    """Проверь фиксацию нарушения CG003 при превышении лимита ветвлений."""
    source = """
def handle_many(val):
    if val == 1:
        pass
    elif val == 2:
        pass
    elif val == 3:
        pass
    elif val == 4:
        pass
    elif val == 5:
        pass
    elif val == 6:
        pass
    elif val == 7:
        pass
"""
    violations = check_source(source)
    cg003 = [v for v in violations if v.code == "CG003"]
    assert len(cg003) == 1
    assert "has 7 branches" in cg003[0].message


def test_cg003_mixed_branch_types() -> None:
    """Проверь подсчет смешанных конструкций ветвления (if, ternary, match, except)."""
    source = """
def mixed_branches(x, y):
    try:
        a = 1 if x > 0 else 2
        if y > 10:
            pass
        elif y > 5:
            pass
        match x:
            case 1:
                pass
            case 2:
                pass
            case 3:
                pass
    except ValueError:
        pass
"""
    violations = check_source(source)
    cg003 = [v for v in violations if v.code == "CG003"]
    assert len(cg003) == 1
    assert "has 7 branches" in cg003[0].message


def test_cg004_returns_within_threshold() -> None:
    """Проверь допустимость функции с количеством return statements в пределах нормы."""
    source = """
def check_status(code):
    if code == 200:
        return "OK"
    if code == 400:
        return "Bad Request"
    if code == 404:
        return "Not Found"
    return "Unknown"
"""
    violations = check_source(source)
    assert not any(v.code == "CG004" for v in violations)


def test_cg004_returns_exceeds_threshold() -> None:
    """Проверь фиксацию нарушения CG004 при избыточном числе return statements."""
    source = """
def validate(x):
    if x < 0:
        return "negative"
    if x == 0:
        return "zero"
    if x == 1:
        return "one"
    if x == 2:
        return "two"
    if x == 3:
        return "three"
    return "other"
"""
    violations = check_source(source)
    cg004 = [v for v in violations if v.code == "CG004"]
    assert len(cg004) == 1
    assert "has 6 returns" in cg004[0].message


def test_nested_functions_do_not_leak_to_outer() -> None:
    """Убедись, что вложенные функции не влияют на метрики родительской функции."""
    source = """
def outer():
    def inner():
        if True:
            return 1
        return 2

    return inner()
"""
    violations = check_source(source)
    assert len(violations) == 0


def test_syntax_error_reported_gracefully() -> None:
    """Проверь корректное формирование CG000 при ошибке синтаксиса Python."""
    source = "def broken(:\n    pass"
    violations = check_source(source)
    assert len(violations) == 1
    assert violations[0].code == "CG000"
    assert "SyntaxError" in violations[0].message


def test_cg001_while_loop_nesting() -> None:
    """Проверь учет циклов while в глубине вложенности CG001."""
    source = """
def process(items):
    while items:
        for x in items:
            while x > 0:
                x -= 1
"""
    violations = check_source(source)
    cg001 = [v for v in violations if v.code == "CG001"]
    assert len(cg001) == 1
    assert cg001[0].line == 5


def test_cg005_linear_search_in_list_literal() -> None:
    """Проверь обнаружение поиска in [literal list] внутри цикла (CG005)."""
    source = """
def find_matches(items):
    for x in items:
        if x in [10, 20, 30]:
            print(x)
"""
    violations = check_source(source)
    cg005 = [v for v in violations if v.code == "CG005"]
    assert len(cg005) == 1
    assert "[10, 20, 30]" in cg005[0].message
    assert cg005[0].line == 4


def test_cg005_linear_search_in_typed_list() -> None:
    """Проверь обнаружение поиска in sequence по аннотации типа (CG005)."""
    source = """
from typing import Sequence

def check_users(active_ids: list[int], banned_ids: Sequence[int]):
    for uid in active_ids:
        if uid in banned_ids:
            pass
"""
    violations = check_source(source)
    cg005 = [v for v in violations if v.code == "CG005"]
    assert len(cg005) == 1
    assert "banned_ids" in cg005[0].message
    assert cg005[0].line == 6


def test_cg005_linear_search_in_assigned_list() -> None:
    """Проверь обнаружение поиска по списку, присвоенному ранее (CG005)."""
    source = """
def process_data(raw_text: str, targets: str):
    forbidden = raw_text.split(",")
    for item in targets.split():
        if item in forbidden:
            pass
"""
    violations = check_source(source)
    cg005 = [v for v in violations if v.code == "CG005"]
    assert len(cg005) == 1
    assert "forbidden" in cg005[0].message


def test_cg005_linear_search_in_list_comp() -> None:
    """Проверь обнаружение поиска in [comp] внутри цикла (CG005)."""
    source = """
def match_records(records, users):
    for r in records:
        if r.uid in [u.id for u in users]:
            pass
"""
    violations = check_source(source)
    cg005 = [v for v in violations if v.code == "CG005"]
    assert len(cg005) == 1


def test_cg005_safe_set_and_dict_search() -> None:
    """Убедись, что O(1) поиск в set и dict не вызывает нарушений CG005."""
    source = """
def safe_check(items: list[int], allowed_set: set[int], lookup_dict: dict[int, str]):
    for item in items:
        if item in allowed_set:
            pass
        if item in lookup_dict:
            pass
"""
    violations = check_source(source)
    assert not any(v.code == "CG005" for v in violations)


def test_cg005_safe_constant_tuple() -> None:
    """Убедись, что проверка по небольшому кортежу констант считается O(1)."""
    source = """
def check_status(orders):
    for order in orders:
        if order.status in ("pending", "completed"):
            pass
"""
    violations = check_source(source)
    assert not any(v.code == "CG005" for v in violations)


def test_cg005_disabled_by_config() -> None:
    """Проверь отключение правила CG005 через конфигурацию."""
    source = """
def check(items: list[int], bad: list[int]):
    for x in items:
        if x in bad:
            pass
"""
    cfg = Config(check_linear_in_loop=False)
    violations = check_source(source, config=cfg)
    assert not any(v.code == "CG005" for v in violations)


def test_cg006_index_and_count_in_loop() -> None:
    """Проверь вызовы O(N) методов .index() и .count() внутри цикла (CG006)."""
    source = """
def scan(items, targets):
    for t in targets:
        pos = items.index(t)
        cnt = items.count(t)
"""
    violations = check_source(source)
    cg006 = [v for v in violations if v.code == "CG006"]
    assert len(cg006) == 2
    methods = {v.symbol for v in cg006}
    assert methods == {"index", "count"}


def test_cg006_remove_in_loop_on_list() -> None:
    """Проверь вызов .remove() на списке внутри цикла (CG006)."""
    source = """
def prune(candidates: list[int], to_remove: list[int]):
    for item in to_remove:
        candidates.remove(item)
"""
    violations = check_source(source)
    cg006 = [v for v in violations if v.code == "CG006"]
    assert len(cg006) == 1
    assert cg006[0].symbol == "remove"


def test_cg006_remove_in_loop_on_set_is_safe() -> None:
    """Убедись, что вызов .remove() на множестве set O(1) допустим."""
    source = """
def prune_set(active: set[int], to_remove: list[int]):
    for item in to_remove:
        active.remove(item)
"""
    violations = check_source(source)
    assert not any(v.code == "CG006" for v in violations)


def test_cg006_pop_zero_in_loop() -> None:
    """Проверь обнаружение .pop(0) как линейной операции внутри цикла (CG006)."""
    source = """
def drain(queue: list[int]):
    while queue:
        task = queue.pop(0)
"""
    violations = check_source(source)
    cg006 = [v for v in violations if v.code == "CG006"]
    assert len(cg006) == 1
    assert "pop(0)" in cg006[0].message


def test_cg006_pop_end_in_loop_is_safe() -> None:
    """Убедись, что .pop() без аргументов (O(1)) не триггерит CG006."""
    source = """
def drain_stack(stack: list[int]):
    while stack:
        task = stack.pop()
"""
    violations = check_source(source)
    assert not any(v.code == "CG006" for v in violations)


def test_cg006_insert_zero_in_loop() -> None:
    """Проверь обнаружение .insert(0, ...) внутри цикла (CG006)."""
    source = """
def build_reverse(items):
    res = []
    for x in items:
        res.insert(0, x)
"""
    violations = check_source(source)
    cg006 = [v for v in violations if v.code == "CG006"]
    assert len(cg006) == 1
    assert "insert(0, ...)" in cg006[0].message


def test_cg007_string_concat_in_loop() -> None:
    """Проверь фиксацию квадратичной конкатенации строк += в цикле (CG007)."""
    source = """
def join_items(items):
    s = ""
    for item in items:
        s += str(item)
"""
    violations = check_source(source)
    cg007 = [v for v in violations if v.code == "CG007"]
    assert len(cg007) == 1
    assert cg007[0].line == 5


def test_cg007_numeric_addition_in_loop_is_safe() -> None:
    """Убедись, что арифметическое сложение чисел += не считается конкатенацией."""
    source = """
def sum_values(items: list[int]):
    total = 0
    for x in items:
        total += x
"""
    violations = check_source(source)
    assert not any(v.code == "CG007" for v in violations)


def test_cg008_nested_comprehension() -> None:
    """Проверь фиксацию вложенных списковых включений [[... for ...] for ...] (CG008)."""
    source = """
def double_grid(matrix):
    return [[val * 2 for val in row] for row in matrix]
"""
    violations = check_source(source)
    cg008 = [v for v in violations if v.code == "CG008"]
    assert len(cg008) == 1
    assert "depth 2 exceeds limit of 1" in cg008[0].message


def test_cg008_multiple_generators_in_single_comp() -> None:
    """Проверь фиксацию нескольких for в одном comprehension (CG008)."""
    source = """
def flatten(matrix):
    return [cell for row in matrix for cell in row]
"""
    violations = check_source(source)
    cg008 = [v for v in violations if v.code == "CG008"]
    assert len(cg008) == 1


def test_cg008_single_comprehension_is_safe() -> None:
    """Убедись, что одномерный comprehension допустим."""
    source = """
def double_list(items):
    return [x * 2 for x in items]
"""
    violations = check_source(source)
    assert not any(v.code == "CG008" for v in violations)


def test_cg008_custom_threshold() -> None:
    """Проверь настраиваемый порог глубины включений."""
    source = """
def double_grid(matrix):
    return [[val * 2 for val in row] for row in matrix]
"""
    cfg = Config(max_comprehension_depth=2)
    violations = check_source(source, config=cfg)
    assert not any(v.code == "CG008" for v in violations)


def test_ru_language_messages() -> None:
    """Проверь генерацию понятных сообщений на русском языке."""
    source = """
def search(items: list[int], targets: list[int]):
    for t in targets:
        if t in items:
            pass
"""
    cfg = Config(lang="ru")
    violations = check_source(source, config=cfg)
    cg005 = [v for v in violations if v.code == "CG005"]
    assert len(cg005) == 1
    assert "Линейный поиск 'items'" in cg005[0].message
    assert "O(N²)" in cg005[0].message
