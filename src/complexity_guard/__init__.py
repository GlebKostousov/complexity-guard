"""Контроль алгоритмической сложности кода, ветвлений и глубины циклов."""

from .checker import ComplexityChecker, Violation, check_file, check_source
from .config import Config

__version__ = "0.2.0"
__all__ = [
    "ComplexityChecker",
    "Config",
    "Violation",
    "check_file",
    "check_source",
    "__version__",
]
