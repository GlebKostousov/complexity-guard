# Complexity Guard (`complexity-guard`)

> **Лёгкий pre-commit хук и CLI-инструмент для защиты от алгоритмической сложности $O(N^2)/O(N^3)$, скрытого линейного поиска в циклах, глубокой вложенности и запутанных ветвлений.**

[![CI](https://github.com/GlebKostousov/complexity-guard/actions/workflows/ci.yml/badge.svg)](https://github.com/GlebKostousov/complexity-guard/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)](#)

---

## Зачем это нужно (Философия O(1) и защита от скрытого O(N²))

Многие критические просадки производительности на бэкенде возникают не из-за базы данных, а из-за **скрытого квадратичного времени выполнения в коде**:
- **Скрытый $O(N^2)$ через `in list`:** проверка `if item in my_list` внутри цикла выглядит как $O(1)$, но в Python для списков и кортежей это полный линейный перебор $O(M)$. Итоговая сложность — $O(N \cdot M) \approx O(N^2)$.
- **Методы $O(N)$ в цикле:** вызовы `.index()`, `.count()`, `.remove()` или `.pop(0)` на списках заставляют процессор сканировать или сдвигать массив на каждом шаге цикла.
- **Конкатенация строк `s += chunk` в цикле:** строки в Python неизменяемы. Каждое `+=` копирует всю строку заново, превращая сборку текста в $O(N^2)$ по памяти и CPU.
- **Вложенные циклы `for` и `while`:** тройная вложенность обходов гарантирует зависание сервера при росте входящих данных.
- **Функции-лабиринты:** десятки ветвлений (`if`/`elif`/`match`) и хаотичные точки выхода (`return`) делают логику нетестируемой.

`complexity-guard` работает прямо в вашем Git pre-commit контуре:
1. **Находит скрытые $O(N^2)$ операции:** отслеживает типы коллекций через локальный AST-инференс и запрещает линейный поиск в цикле.
2. **Запрещает глубокие циклы (порог $\le 2$):** стимулирует плоские алгоритмы и $O(1)$ поиск через `dict` / `set`.
3. **Ограничивает цикломатическую сложность и ветвления:** стимулирует простую и линейную структуру функций.
4. **Работает мгновенно и без внешних зависимостей:** только стандартная библиотека Python (`ast`, `argparse`, `pathlib`).

---

## Правила (Rules)

| Код | Правило | Порог по умолчанию | Смысл |
|---|---|---|---|
| **CG001** | `loop-depth` | $\le 2$ | Максимальная глубина вложенности циклов `for`, `async for` и `while`. Защищает от $O(N^3)$ и стимулирует $O(1)$ структуры данных. |
| **CG002** | `cyclomatic-complexity` | $\le 5$ (строгий: $3$) | Цикломатическая сложность функции по Маккейбу (McCabe). |
| **CG003** | `max-branches` | $\le 6$ | Количество ветвей условий (`if`, `elif`, `match`, `except`, тернарные операторы). |
| **CG004** | `max-returns` | $\le 4$ | Количество операторов `return` в одной функции. |
| **CG005** | `linear-in-loop` | Запрещено | Линейный поиск `in list` / `in tuple` / `in Sequence` внутри цикла ($O(N^2)$ smell). Требует вынести во множество `set()` до цикла. |
| **CG006** | `quadratic-methods` | Запрещено | Вызовы $O(N)$ методов (`.index()`, `.count()`, `.remove()`, `.pop(0)`, `.insert(0, ...)`) на коллекциях внутри циклов. |
| **CG007** | `quadratic-string-concat` | Запрещено | Конкатенация строк `s += chunk` внутри цикла. Требует сборки списка и `''.join(...)`. |
| **CG008** | `nested-comprehension` | $\le 1$ | Вложенные списковые включения `[[... for ...] for ...]` или несколько `for` в одном comprehension ($O(N^2)+$). |

---

## Быстрый старт (Pre-commit)

Добавьте в ваш `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/GlebKostousov/complexity-guard
    rev: v0.2.0
    hooks:
      - id: complexity-guard
```

Или с переопределением порогов:

```yaml
repos:
  - repo: https://github.com/GlebKostousov/complexity-guard
    rev: v0.2.0
    hooks:
      - id: complexity-guard
        args:
          - --max-loop-depth=2
          - --max-complexity=3
          - --max-branches=6
          - --max-returns=4
          - --max-comprehension-depth=1
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

### Доступные флаги CLI:

- `--max-loop-depth=N` — максимальная глубина циклов (по умолчанию: `2`).
- `--max-complexity=N` — максимальная сложность по Маккейбу (по умолчанию: `5`).
- `--max-branches=N` — максимальное число ветвлений (по умолчанию: `6`).
- `--max-returns=N` — максимальное число точек выхода (по умолчанию: `4`).
- `--max-comprehension-depth=N` — глубина вложенности comprehension (по умолчанию: `1`).
- `--no-linear-in-loop` — отключить проверку поиска `in list` в циклах (CG005).
- `--no-quadratic-methods` — отключить проверку $O(N)$ методов в циклах (CG006).
- `--no-string-concat` — отключить проверку `s += ...` в циклах (CG007).
- `--strict` — строгий профиль качества (`complexity=3`, `branches=4`, `returns=3`).
- `--lang=ru|en` — язык сообщений об ошибках (по умолчанию `en`).
- `--format=text|github|json` — формат вывода (UNIX, GitHub Actions или JSON).

### Формат вывода

Формат полностью совместим со стандартом UNIX-линтеров и IDE (VS Code, PyCharm, Neovim):

```text
app/services/orders.py:42:15: CG005 Линейный поиск 'banned_ids' через 'in' внутри цикла превращает сложность в O(N²). Преобразуйте коллекцию в set перед циклом или используйте словарь
app/core/matcher.py:18:8: CG006 Вызов O(N) метода 'index' на коллекции 'items' внутри цикла приводит к сложности O(N²). Вынесите индексацию до цикла или используйте deque
app/utils/export.py:85:4: CG007 Конкатенация строк 'output += ...' внутри цикла приводит к квадратичному копированию памяти O(N²). Собирайте части в список и используйте ''.join(...)
```

---

## Конфигурация в `pyproject.toml`

Все пороги можно настроить в `pyproject.toml` вашего проекта:

```toml
[tool.complexity-guard]
max-loop-depth = 2
max-complexity = 5
max-branches = 6
max-returns = 4
max-comprehension-depth = 1
check-linear-in-loop = true
check-quadratic-methods = true
check-string-concat = true
lang = "ru"
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
    if item in target_list:  # noqa: CG005
        s += "!"  # noqa: CG007
```

Поддерживаются:
- `# noqa: CG001`, `# noqa: CG005`, `# noqa: CG006`, `# noqa: CG007`, `# noqa: CG008` — конкретные коды.
- `# noqa: complexity` — отключение всех правил сложности на строке или функции.
- `# noqa` — универсальное подавление.

---

## Примеры оптимизации: от $O(N^2)$ к $O(1)$

### 1. Линейный поиск в цикле: $O(N \cdot M) \to O(N + M)$ (CG005)

**До (плохо — $O(N \cdot M)$):**
```python
def filter_active_users(users: list[User], banned_ids: list[int]):
    result = []
    for user in users:
        if user.id in banned_ids:  # CG005: линейный поиск O(M) на каждой итерации
            continue
        result.append(user)
    return result
```

**После (хорошо — $O(N + M)$ с $O(1)$ lookup):**
```python
def filter_active_users(users: list[User], banned_ids: list[int]):
    banned_set = set(banned_ids)  # O(M) один раз
    return [user for user in users if user.id not in banned_set]  # O(1) поиск в хэш-сете
```

### 2. Сборка строк в цикле: $O(N^2) \to O(N)$ (CG007)

**До (плохо — $O(N^2)$ аллокаций памяти):**
```python
def build_report(rows):
    html = ""
    for row in rows:
        html += f"<tr><td>{row.title}</td></tr>"  # CG007: перезапись всей строки
    return html
```

**После (хорошо — $O(N)$ через список и join):**
```python
def build_report(rows):
    parts = [f"<tr><td>{row.title}</td></tr>" for row in rows]
    return "".join(parts)  # O(N) единым буфером
```

---

## Лицензия

MIT License. Автор: Gleb Kostousov.
