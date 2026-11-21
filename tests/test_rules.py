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
