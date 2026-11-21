# Complexity Guard (`complexity-guard`)

> **Лёгкий pre-commit хук и CLI-инструмент для защиты от алгоритмической сложности, глубоких вложенных циклов $O(N^2)/O(N^3)$ и запутанных ветвлений.**

[![CI](https://github.com/GlebKostousov/complexity-guard/actions/workflows/ci.yml/badge.svg)](https://github.com/GlebKostousov/complexity-guard/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)](#)

---

## Зачем это нужно (Философия O(1))

Многие ошибки производительности на бэкенде возникают не из-за базы данных, а из-за незаметного появления вложенных циклов:
- Поиск элемента во внутреннем цикле превращает операцию в $O(N^2)$ или $O(N^3)$.
- Сервер отлично работает на 10 записях в тестах и уходит в 100% CPU на проде при 5 000 записей.
- Функции с десятком ветвлений (`if`/`elif`/`match`) и множеством точек выхода (`return`) становятся нечитаемыми, хрупкими и трудно тестируемыми.

`complexity-guard` работает прямо в вашем Git pre-commit контуре:
1. **Запрещает глубокие циклы (порог по умолчанию $\le 2$):** заставляет разработчика либо вынести вложенный обход во вспомогательную функцию, либо переписать алгоритм на $O(1)$ поиск через `dict` / `set` / хэш-мапу.
2. **Ограничивает цикломатическую сложность и ветвления:** стимулирует простую и линейную структуру функций.
3. **Работает мгновенно и без внешних зависимостей:** только стандартная библиотека Python (`ast`, `argparse`, `pathlib`).

---

## Правила (Rules)

| Код | Правило | Порог по умолчанию | Смысл |
|---|---|---|---|
| **CG001** | `loop-depth` | $\le 2$ | Максимальная глубина вложенности `for` / `async for`. Защищает от $O(N^3)$ и стимулирует $O(1)$ структуры данных. |
| **CG002** | `cyclomatic-complexity` | $\le 5$ (строгий: $3$) | Цикломатическая сложность функции по Маккейбу (McCabe). |
| **CG003** | `max-branches` | $\le 6$ | Количество ветвей условий (`if`, `elif`, `match`, `except`, тернарные операторы). |
| **CG004** | `max-returns` | $\le 4$ | Количество операторов `return` в одной функции. |

---

## Быстрый старт (Pre-commit)

Добавьте в ваш `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/GlebKostousov/complexity-guard
    rev: v0.1.0
    hooks:
      - id: complexity-guard
```

Или с переопределением порогов:

```yaml
repos:
  - repo: https://github.com/GlebKostousov/complexity-guard
    rev: v0.1.0
    hooks:
      - id: complexity-guard
        args:
          - --max-loop-depth=2
          - --max-complexity=3
          - --max-branches=6
          - --max-returns=4
```

---

## Использование через CLI

Установка через `pip` или `uv`:

```bash
pip install complexity-guard
# или
uv add --dev complexity-guard
```

Запуск проверки:

```bash
complexity-guard .
# или по конкретным путям:
complexity-guard app/ tests/
```

### Формат вывода

Формат полностью совместим со стандартом UNIX-линтеров и IDE (VS Code, PyCharm, Neovim):

```text
app/services/reports.py:45:8: CG001 Глубина вложенных циклов 3 превышает максимум 2
app/core/matcher.py:12:4: CG003 Количество ветвлений 8 в функции 'match_records' превышает максимум 6
```

---

## Конфигурация в `pyproject.toml`

Все пороги можно настроить в `pyproject.toml` вашего проекта:

```toml
[tool.complexity-guard]
max-loop-depth = 2
max-complexity = 3
max-branches = 6
max-returns = 4
exclude = [
    ".git",
    ".venv",
    "tests",
]
```

---

## Подавление правил (`# noqa`)

В редких обоснованных случаях проверку можно точечно отключить:

```python
for item in dataset:
    for sub in item.children:
        for leaf in sub.leaves:  # noqa: CG001
            process(leaf)
```

Поддерживаются:
- `# noqa: CG001` — отключение конкретного правила.
- `# noqa: complexity` — отключение проверок сложности.
- `# noqa` — полное подавление строки или заголовка функции.

---

## Пример рефакторинга: $O(N^2) \to O(1)$

### До (плохо — $O(N \cdot M)$):
```python
def link_orders_to_customers(orders, customers):
    result = []
    for order in orders:
        for customer in customers:  # Вложенный цикл O(N*M)
            if customer.id == order.customer_id:
                result.append((order, customer))
    return result
```

### После (хорошо — $O(N + M)$ с $O(1)$ lookup):
```python
def link_orders_to_customers(orders, customers):
    customer_by_id = {c.id: c for c in customers}  # O(M)
    return [
        (order, customer_by_id[order.customer_id])  # O(1) поиск в словаре
        for order in orders
        if order.customer_id in customer_by_id
    ]
```

---

## Лицензия

MIT License. Автор: Gleb Kostousov.
