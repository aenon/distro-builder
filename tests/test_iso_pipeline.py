from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from distro_builder.cli.main import cli
from distro_builder.iso.pipeline import PipelineError, build_iso
from distro_builder.manifest.models import Distribution, Stage, Target

FIXTURES = Path(__file__).parent / "fixtures"


def _iso_distribution(stages: list[Stage] | None = None, **overrides) -> Distribution:
    data = {
        "name": "demo-iso",
        "family": "debian",
        "format": "iso",
        "base_image": "debian:bookworm",
        "targets": [Target(platform="x86_64", output_name="demo.iso")],
        "stages": stages or [],
    }
    data.update(overrides)
    return Distribution(**data)


class TestBuildIso:
    def test_produces_iso_file(self, tmp_path: Path):
        dist = _iso_distribution()
        target = dist.targets[0]
        out = build_iso(dist, target, tmp_path)
        assert out.exists()
        assert out.suffix == ".iso"
        assert out.stat().st_size > 0

    def test_output_is_iso9660(self, tmp_path: Path):
        import pycdlib

        dist = _iso_distribution()
        out = build_iso(dist, dist.targets[0], tmp_path)
        iso = pycdlib.PyCdlib()
        iso.open(str(out))
        try:
            assert iso.get_record(joliet_path="/boot/vmlinuz") is not None
            assert iso.get_record(joliet_path="/boot/initrd.img") is not None
            assert iso.get_record(joliet_path="/boot/grub/grub.cfg") is not None
            assert iso.eltorito_boot_catalog is not None
        finally:
            iso.close()

    def test_grub_stage_applied(self, tmp_path: Path):
        import pycdlib

        stages = [
            Stage(
                name="boot",
                type="grub",
                params={"title": "Custom Title", "kernel_cmdline": "console=ttyS0", "timeout": 7},
            ),
        ]
        dist = _iso_distribution(stages=stages)
        out = build_iso(dist, dist.targets[0], tmp_path)

        iso = pycdlib.PyCdlib()
        iso.open(str(out))
        try:
            buf = bytearray()

            class _Sink:
                def write(self, data):
                    buf.extend(data)
                    return len(data)

            iso.get_file_from_iso_fp(outfp=_Sink(), joliet_path="/boot/grub/grub.cfg")
            content = bytes(buf).decode()
            assert "Custom Title" in content
            assert "console=ttyS0" in content
            assert "set timeout=7" in content
        finally:
            iso.close()

    def test_wrong_format_rejected(self, tmp_path: Path):
        dist = _iso_distribution(format="oci")
        with pytest.raises(PipelineError, match="expected 'iso'"):
            build_iso(dist, dist.targets[0], tmp_path)

    def test_kernel_path_param_used(self, tmp_path: Path):
        import pycdlib

        real_kernel = tmp_path / "my-kernel.bin"
        real_kernel.write_bytes(b"KERNEL-CONTENT-" + b"X" * 100)
        stages = [Stage(name="k", type="kernel", params={"path": str(real_kernel)})]
        dist = _iso_distribution(stages=stages)

        out = build_iso(dist, dist.targets[0], tmp_path)
        iso = pycdlib.PyCdlib()
        iso.open(str(out))
        try:
            buf = bytearray()

            class _Sink:
                def write(self, data):
                    buf.extend(data)
                    return len(data)

            iso.get_file_from_iso_fp(outfp=_Sink(), joliet_path="/boot/vmlinuz")
            assert bytes(buf).startswith(b"KERNEL-CONTENT-")
        finally:
            iso.close()

    def test_missing_kernel_path_raises(self, tmp_path: Path):
        stages = [Stage(name="k", type="kernel", params={"path": "/no/such/file"})]
        dist = _iso_distribution(stages=stages)
        with pytest.raises(PipelineError, match="kernel source not found"):
            build_iso(dist, dist.targets[0], tmp_path)


class TestCliIsoBuild:
    def test_cli_builds_iso(self, tmp_path: Path):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["build", str(FIXTURES / "iso_manifest.yaml"), "--output-dir", str(tmp_path)],
        )
        assert result.exit_code == 0, result.output
        iso_path = tmp_path / "demo-x86_64.iso"
        assert iso_path.exists()
        assert iso_path.stat().st_size > 0
        assert "built:" in result.output

    def test_cli_dry_run_does_not_create_file(self, tmp_path: Path):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "build",
                str(FIXTURES / "iso_manifest.yaml"),
                "--output-dir",
                str(tmp_path),
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        assert "Would build" in result.output
        assert not (tmp_path / "demo-x86_64.iso").exists()
