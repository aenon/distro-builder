from __future__ import annotations

import subprocess
from pathlib import Path

from distro_builder.qemu.formats import Qcow2Builder, RawDiskBuilder


def _fake_completed() -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")


class TestRawDiskBuilder:
    def test_build_invokes_qemu_img_create(self, mocker):
        run = mocker.patch("subprocess.run", return_value=_fake_completed())
        b = RawDiskBuilder()
        out = b.build(Path("/tmp/d.raw"), "20M")
        argv = run.call_args.args[0]
        assert argv[0] == "qemu-img"
        assert argv[1:4] == ["create", "-f", "raw"]
        assert argv[-2:] == ["/tmp/d.raw", "20M"]
        assert out == Path("/tmp/d.raw")


class TestQcow2Builder:
    def test_default_compression(self, mocker):
        run = mocker.patch("subprocess.run", return_value=_fake_completed())
        Qcow2Builder().build(Path("/tmp/d.qcow2"), "1G")
        argv = run.call_args.args[0]
        opts = argv[argv.index("-o") + 1]
        assert "compression_type=zstd" in opts

    def test_disable_compression(self, mocker):
        run = mocker.patch("subprocess.run", return_value=_fake_completed())
        Qcow2Builder().build(Path("/tmp/d.qcow2"), "1G", compression=None)
        argv = run.call_args.args[0]
        assert "-o" not in argv or "compression_type" not in argv[argv.index("-o") + 1]

    def test_backing_file_passed(self, mocker):
        run = mocker.patch("subprocess.run", return_value=_fake_completed())
        Qcow2Builder().build(
            Path("/tmp/overlay.qcow2"),
            "0",
            backing_file=Path("/tmp/base.qcow2"),
            backing_format="qcow2",
        )
        argv = run.call_args.args[0]
        opts = argv[argv.index("-o") + 1]
        assert "backing_file=/tmp/base.qcow2" in opts
        assert "backing_fmt=qcow2" in opts

    def test_cluster_size_passed(self, mocker):
        run = mocker.patch("subprocess.run", return_value=_fake_completed())
        Qcow2Builder().build(Path("/tmp/d.qcow2"), "1G", cluster_size=65536)
        argv = run.call_args.args[0]
        opts = argv[argv.index("-o") + 1]
        assert "cluster_size=65536" in opts

    def test_output_format_is_qcow2(self, mocker):
        run = mocker.patch("subprocess.run", return_value=_fake_completed())
        Qcow2Builder().build(Path("/tmp/d.qcow2"), "1G")
        argv = run.call_args.args[0]
        assert argv[argv.index("-f") + 1] == "qcow2"
