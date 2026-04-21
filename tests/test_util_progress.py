from __future__ import annotations

import pytest

from distro_builder.util.progress import stream_subprocess


class TestStreamSubprocess:
    def test_echo_returns_zero(self, capsys):
        rc = stream_subprocess(["echo", "hello"], description="say-hello")
        assert rc == 0

    def test_false_returns_nonzero(self):
        rc = stream_subprocess(["false"], description="expect-fail")
        assert rc != 0

    def test_missing_binary_returns_127(self):
        rc = stream_subprocess(["/definitely/not/a/binary/xyz"], description="missing")
        assert rc == 127

    def test_empty_cmd_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            stream_subprocess([], description="nope")

    def test_exit_code_preserved(self):
        rc = stream_subprocess(["sh", "-c", "exit 3"], description="exit3")
        assert rc == 3
