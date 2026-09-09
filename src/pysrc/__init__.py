# src/pysrc/__init__.py
from __future__ import annotations

from typing import Any
import importlib
import sys

sys.modules.setdefault("intern", importlib.import_module("pysrc.intern"))

# # Declare the attribute so mypy knows the package exposes it.
# my_intern: Any

# # Try to bind the real compiled extension at runtime (when built).
# try:
#     my_intern = importlib.import_module(__name__ + ".my_intern")
# except Exception:
#     # During static analysis or before the .so is built, leave the declared Any.
#     pass

# __all__ = ["my_intern"]
