from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from distro_builder.cli.main import cli
from distro_builder.manifest.models import Distribution, Stage, Target
from distro_builder.qemu.pipeline import QemuPipelineError, build_qemu_image

FIXTURES = Path(__file__).parent / "fixtures"


def _qcow2_distribution(**overrides) -> Distribution:
    data = {
        "name": "demo-qemu",
        "family": "debian",
        "format": "qcow2",
        "base_image": "debian:bookworm",
        "targets": [Target(platform="x86_64", output_name="demo.qcow2")],
        "stages": [Stage(name="sizing", type="run", params={"size": "64M"})],
    }
    data.update(overrides)
    return Distribution(**data)


def _fake_completed() -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")


class TestBuildQemuImageMocked:
    def test_qcow2_invokes_correct_args(self, mocker, tmp_path: Path):
        run = mocker.patch("subprocess.run", return_value=_fake_completed())
        dist = _qcow2_distribution()
        out = build_qemu_image(dist, dist.targets[0], tmp_path)
        assert out == tmp_path / "demo.qcow2"
        argv = run.call_args.args[0]
        assert argv[argv.index("-f") + 1] == "qcow2"
        assert argv[-1] == "64M"

    def test_raw_invokes_correct_args(self, mocker, tmp_path: Path):
        run = mocker.patch("subprocess.run", return_value=_fake_completed())
        dist = _qcow2_distribution(format="raw")
        build_qemu_image(dist, dist.targets[0], tmp_path)
        argv = run.call_args.args[0]
        assert argv[argv.index("-f") + 1] == "raw"

    def test_default_size_when_no_stage(self, mocker, tmp_path: Path):
        run = mocker.patch("subprocess.run", return_value=_fake_completed())
        dist = _qcow2_distribution(stages=[])
        build_qemu_image(dist, dist.targets[0], tmp_path)
        argv = run.call_args.args[0]
        assert argv[-1] == "1G"

    def test_wrong_format_rejected(self, tmp_path: Path):
        dist = _qcow2_distribution(format="iso")
        with pytest.raises(QemuPipelineError, match="unsupported format"):
            build_qemu_image(dist, dist.targets[0], tmp_path)


QEMU_IMG_AVAILABLE = shutil.which("qemu-img") is not None


@pytest.mark.skipif(not QEMU_IMG_AVAILABLE, reason="qemu-img not installed")
class TestBuildQemuImageIntegration:
    def test_real_qcow2_creation(self, tmp_path: Path):
        dist = _qcow2_distribution()
        out = build_qemu_image(dist, dist.targets[0], tmp_path)
        assert out.exists()


class TestCliQemuBuild:
    def test_cli_invokes_pipeline(self, mocker, tmp_path: Path):
        run = mocker.patch("subprocess.run", return_value=_fake_completed())
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "build",
                str(FIXTURES / "qemu_manifest.yaml"),
                "--output-dir",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 0, result.output
        assert "built:" in result.output
        assert run.called
