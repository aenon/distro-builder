from __future__ import annotations

import logging

from rich.logging import RichHandler

_CONFIGURED = False
_LOGGER_NAME_PREFIX = "distro_builder"


def _configure_root_once() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    root = logging.getLogger(_LOGGER_NAME_PREFIX)
    root.setLevel(logging.INFO)
    handler = RichHandler(
        show_time=False,
        show_path=False,
        rich_tracebacks=True,
        markup=False,
    )
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    root.addHandler(handler)
    root.propagate = False
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    _configure_root_once()
    if name == _LOGGER_NAME_PREFIX or name.startswith(f"{_LOGGER_NAME_PREFIX}."):
        return logging.getLogger(name)
    return logging.getLogger(f"{_LOGGER_NAME_PREFIX}.{name}")


def set_level(level: str | int) -> None:
    _configure_root_once()
    if isinstance(level, str):
        resolved = logging.getLevelName(level.upper())
        if not isinstance(resolved, int):
            raise ValueError(f"unknown log level: {level!r}")
        level = resolved
    logging.getLogger(_LOGGER_NAME_PREFIX).setLevel(level)
