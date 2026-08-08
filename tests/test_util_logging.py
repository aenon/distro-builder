from __future__ import annotations

import logging

import pytest

from distro_builder.util.logging import get_logger, set_level


class TestGetLogger:
    def test_returns_logger_instance(self):
        logger = get_logger("mytest")
        assert isinstance(logger, logging.Logger)

    def test_logger_has_rich_handler_on_root(self):
        get_logger("child")
        root = logging.getLogger("distro_builder")
        from rich.logging import RichHandler

        assert any(isinstance(h, RichHandler) for h in root.handlers)

    def test_child_logger_inherits_root_prefix(self):
        logger = get_logger("build.iso")
        assert logger.name == "distro_builder.build.iso"

    def test_already_prefixed_name_preserved(self):
        logger = get_logger("distro_builder.foo")
        assert logger.name == "distro_builder.foo"


class TestSetLevel:
    def test_set_debug_level(self):
        set_level("DEBUG")
        assert logging.getLogger("distro_builder").level == logging.DEBUG

    def test_set_level_info(self):
        set_level("INFO")
        assert logging.getLogger("distro_builder").level == logging.INFO

    def test_set_level_warning(self):
        set_level("WARNING")
        assert logging.getLogger("distro_builder").level == logging.WARNING

    def test_set_level_with_int(self):
        set_level(logging.ERROR)
        assert logging.getLogger("distro_builder").level == logging.ERROR

    def test_unknown_level_raises(self):
        with pytest.raises(ValueError, match="unknown log level"):
            set_level("NOTALEVEL")
