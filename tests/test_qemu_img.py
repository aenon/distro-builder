from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from distro_builder.qemu import QemuImg, QemuImgError


def _fake_completed(
    returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


class TestQemuImgRunArgs:
    def test_create_raw_builds_correct_args(self, mocker):
        run = mocker.patch("subprocess.run", return_value=_fake_completed())
        q = QemuImg()
        q.create(Path("/tmp/disk.raw"), "raw", "10M")
        argv = run.call_args.args[0]
        assert argv[0] == "qemu-img"
        assert argv[1:5] == ["create", "-f", "raw", "/tmp/disk.raw"]
        assert argv[-1] == "10M"

    def test_create_qcow2_with_options(self, mocker):
        run = mocker.patch("subprocess.run", return_value=_fake_completed())
        q = QemuImg()
        q.create(
            Path("/tmp/d.qcow2"),
            "qcow2",
            "1G",
            options={"compression_type": "zstd", "cluster_size": "65536"},
        )
        argv = run.call_args.args[0]
        assert "-o" in argv
        opt_idx = argv.index("-o")
        opts = argv[opt_idx + 1]
        assert "compression_type=zstd" in opts
        assert "cluster_size=65536" in opts

    def test_create_with_backing_file(self, mocker):
        run = mocker.patch("subprocess.run", return_value=_fake_completed())
        q = QemuImg()
        q.create(
            Path("/tmp/overlay.qcow2"),
            "qcow2",
            "0",
            backing_file=Path("/tmp/base.qcow2"),
            backing_format="qcow2",
        )
        argv = run.call_args.args[0]
        opts = argv[argv.index("-o") + 1]
        assert "backing_file=/tmp/base.qcow2" in opts
        assert "backing_fmt=qcow2" in opts

    def test_convert_builds_correct_args(self, mocker):
        run = mocker.patch("subprocess.run", return_value=_fake_completed())
        q = QemuImg()
        q.convert(Path("/s.qcow2"), Path("/d.raw"), "qcow2", "raw", compressed=True)
        argv = run.call_args.args[0]
        assert "-f" in argv and "-O" in argv and "-c" in argv
        assert argv[argv.index("-f") + 1] == "qcow2"
        assert argv[argv.index("-O") + 1] == "raw"

    def test_info_parses_json(self, mocker):
        sample = '{"virtual-size": 1048576, "format": "qcow2"}'
        mocker.patch("subprocess.run", return_value=_fake_completed(stdout=sample))
        q = QemuImg()
        info = q.info(Path("/tmp/x.qcow2"))
        assert info["format"] == "qcow2"
        assert info["virtual-size"] == 1048576

    def test_info_invalid_json_raises(self, mocker):
        mocker.patch("subprocess.run", return_value=_fake_completed(stdout="not json"))
        q = QemuImg()
        with pytest.raises(QemuImgError, match="invalid JSON"):
            q.info(Path("/tmp/x.qcow2"))

    def test_snapshot_create(self, mocker):
        run = mocker.patch("subprocess.run", return_value=_fake_completed())
        q = QemuImg()
        q.snapshot_create(Path("/d.qcow2"), "snap-1")
        argv = run.call_args.args[0]
        assert argv[1:5] == ["snapshot", "-c", "snap-1", "/d.qcow2"]

    def test_snapshot_list_filters_header(self, mocker):
        stdout = (
            "Snapshot list:\n"
            "ID     TAG      VM SIZE  DATE\n"
            "1      snap-1   0        2025-04-20\n"
            "2      snap-2   0        2025-04-20\n"
        )
        mocker.patch("subprocess.run", return_value=_fake_completed(stdout=stdout))
        q = QemuImg()
        lines = q.snapshot_list(Path("/d.qcow2"))
        assert len(lines) == 2
        assert all("snap-" in line for line in lines)

    def test_resize(self, mocker):
        run = mocker.patch("subprocess.run", return_value=_fake_completed())
        q = QemuImg()
        q.resize(Path("/d.qcow2"), "+1G")
        argv = run.call_args.args[0]
        assert argv[1:] == ["resize", "/d.qcow2", "+1G"]

    def test_rebase_unsafe_mode(self, mocker):
        run = mocker.patch("subprocess.run", return_value=_fake_completed())
        q = QemuImg()
        q.rebase(
            Path("/overlay.qcow2"),
            Path("/new-base.qcow2"),
            backing_format="qcow2",
            safe=False,
        )
        argv = run.call_args.args[0]
        assert "-u" in argv
        assert "-F" in argv
        assert argv[-1] == "/overlay.qcow2"

    def test_nonzero_exit_raises(self, mocker):
        mocker.patch(
            "subprocess.run",
            return_value=_fake_completed(returncode=1, stderr="something broke"),
        )
        q = QemuImg()
        with pytest.raises(QemuImgError, match="exit 1"):
            q.create(Path("/tmp/x.raw"), "raw", "10M")

    def test_missing_binary_raises(self, mocker):
        mocker.patch("subprocess.run", side_effect=FileNotFoundError())
        q = QemuImg(binary="/nonexistent/qemu-img")
        with pytest.raises(QemuImgError, match="not found"):
            q.create(Path("/tmp/x.raw"), "raw", "10M")


QEMU_IMG_AVAILABLE = shutil.which("qemu-img") is not None


@pytest.mark.skipif(not QEMU_IMG_AVAILABLE, reason="qemu-img not installed")
class TestQemuImgIntegration:
    def test_create_and_info_real_qcow2(self, tmp_path: Path):
        q = QemuImg()
        disk = tmp_path / "real.qcow2"
        q.create(disk, "qcow2", "10M")
        assert disk.exists()
        assert disk.stat().st_size > 0
        info = q.info(disk)
        assert info["format"] == "qcow2"
        assert info["virtual-size"] == 10 * 1024 * 1024

    def test_create_parent_dir_auto(self, tmp_path: Path):
        q = QemuImg()
        disk = tmp_path / "deep" / "nested" / "disk.raw"
        q.create(disk, "raw", "1M")
        assert disk.exists()
