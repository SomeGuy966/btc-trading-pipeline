# src/pysrc/__init__.py
"""BTC-USD trading research pipeline.

``cppcore`` is the compiled pybind11 extension holding the C++ feature
implementations and REST client. It is aliased into ``sys.modules`` under its
bare name so it can be imported either as ``pysrc.cppcore`` or ``cppcore``.
"""

from __future__ import annotations

import importlib
import sys

sys.modules.setdefault("cppcore", importlib.import_module("pysrc.cppcore"))
