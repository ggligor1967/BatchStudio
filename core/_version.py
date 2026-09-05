"""Canonical BatchStudio version.

This module is the single source of truth for the application version. It is
imported by the runtime banner (``main.py``), the desktop UI version/About
displays (``ui/main_window.py``), and consumed as packaging metadata through the
``[tool.setuptools.dynamic]`` ``version = {attr = "core._version.__version__"}``
declaration in ``pyproject.toml``.

Keep this module free of imports so setuptools can read ``__version__``
statically at build time without importing the ``core`` package.
"""

__version__ = "1.1.0"
