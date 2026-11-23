"""Тесты для механизма подавления нарушений через inline-комментарии # noqa."""

from complexity_guard.checker import check_source


def test_suppress_cg001_with_specific_code() -> None:
    """Проверь подавление правила CG001 через конкретный код noqa: CG001."""
    source = """
def process(matrix):
    for a in matrix:
        for b in a:
            for c in b:  # noqa: CG001
                print(c)
"""
    violations = check_source(source)
    assert not any(v.code == "CG001" for v in violations)


def test_suppress_cg001_with_complexity_keyword() -> None:
    """Проверь подавление через ключевое слово noqa: complexity."""
    source = """
def process(matrix):
    for a in matrix:
        for b in a:
            for c in b:  # noqa: complexity
                print(c)
"""
    violations = check_source(source)
    assert not any(v.code == "CG001" for v in violations)


def test_suppress_cg001_with_bare_noqa() -> None:
    """Проверь подавление всех правил через универсальный комментарий # noqa."""
    source = """
def process(matrix):
    for a in matrix:
        for b in a:
            for c in b:  # noqa
                print(c)
"""
    violations = check_source(source)
    assert len(violations) == 0


def test_suppress_cg002_on_def_line() -> None:
    """Проверь подавление CG002 на строке определения функции def."""
    source = """
def complex_func(x):  # noqa: CG002
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
    assert not any(v.code == "CG002" for v in violations)


def test_suppress_cg003_and_cg004_multiple_codes() -> None:
    """Проверь одновременное подавление нескольких кодов через запятую."""
    source = """
def complex_branches_and_returns(x):  # noqa: CG003, CG004
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
    elif x == 6:
        return 6
    elif x == 7:
        return 7
    return 0
"""
    violations = check_source(source)
    assert not any(v.code in {"CG003", "CG004"} for v in violations)


def test_suppress_with_decorator_line() -> None:
    """Проверь распространение комментария noqa со строки декоратора."""
    source = """
@some_decorator  # noqa: complexity
def complex_func(x):
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
    assert not any(v.code == "CG002" for v in violations)


def test_case_insensitive_noqa() -> None:
    """Проверь регистронезависимость кодов в комментарии noqa."""
    source = """
def complex_func(x):  # noqa: cg002
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
    assert not any(v.code == "CG002" for v in violations)


def test_unrelated_noqa_does_not_suppress() -> None:
    """Убедись, что посторонний код noqa (например F401) не подавляет правила CG."""
    source = """
def process(matrix):
    for a in matrix:
        for b in a:
            for c in b:  # noqa: F401
                print(c)
"""
    violations = check_source(source)
    cg001 = [v for v in violations if v.code == "CG001"]
    assert len(cg001) == 1


def test_suppress_cg005_cg006_cg007_cg008() -> None:
    """Проверь подавление новых правил алгоритмической сложности."""
    source = """
def process(items: list[int], target: list[int]):
    s = ""
    for x in items:
        if x in target:  # noqa: CG005
            items.index(x)  # noqa: CG006
            s += "a"  # noqa: CG007

    grid = [[val for val in row] for row in items]  # noqa: CG008
"""
    violations = check_source(source)
    assert len(violations) == 0
