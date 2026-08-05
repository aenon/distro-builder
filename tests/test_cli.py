from __future__ import annotations

import subprocess
from pathlib import Path

from click.testing import CliRunner

from distro_builder import __version__
from distro_builder.cli.main import cli

FIXTURES = Path(__file__).parent / "fixtures"


class TestHelp:
    def test_help_exits_zero(self):
        result = CliRunner().invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.output
        for subcmd in ("validate", "list", "build"):
            assert subcmd in result.output

    def test_version(self):
        result = CliRunner().invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.output


class TestValidate:
    def test_valid_manifest_exits_zero(self):
        result = CliRunner().invoke(cli, ["validate", str(FIXTURES / "valid_manifest.yaml")])
        assert result.exit_code == 0
        assert "OK: 1 distribution" in result.output

    def test_invalid_manifest_exits_nonzero(self):
        result = CliRunner().invoke(cli, ["validate", str(FIXTURES / "invalid_manifest.yaml")])
        assert result.exit_code == 1
        combined = result.output + (result.stderr or "")
        assert "error" in combined.lower()

    def test_missing_file_exits_nonzero(self):
        result = CliRunner().invoke(cli, ["validate", "/definitely/does/not/exist.yaml"])
        assert result.exit_code != 0


class TestList:
    def test_list_shows_distribution(self):
        result = CliRunner().invoke(cli, ["list", str(FIXTURES / "valid_manifest.yaml")])
        assert result.exit_code == 0
        assert "alpine-minimal" in result.output
        assert "alpine" in result.output
        assert "oci" in result.output

    def test_list_shows_target_platforms(self):
        result = CliRunner().invoke(cli, ["list", str(FIXTURES / "valid_manifest.yaml")])
        assert result.exit_code == 0
        assert "x86_64" in result.output
        assert "arm64" in result.output


class TestBuild:
    def test_build_dry_run_prints_all_targets(self):
        result = CliRunner().invoke(
            cli,
            ["build", str(FIXTURES / "valid_manifest.yaml"), "--dry-run"],
        )
        assert result.exit_code == 0
        assert "Would build" in result.output
        assert "alpine-minimal" in result.output
        assert "x86_64" in result.output
        assert "arm64" in result.output

    def test_build_filter_by_distribution(self):
        result = CliRunner().invoke(
            cli,
            [
                "build",
                str(FIXTURES / "valid_manifest.yaml"),
                "--distribution",
                "alpine-minimal",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        assert "alpine-minimal" in result.output

    def test_build_filter_by_target(self):
        result = CliRunner().invoke(
            cli,
            [
                "build",
                str(FIXTURES / "valid_manifest.yaml"),
                "--target",
                "x86_64",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        assert "x86_64" in result.output
        assert "arm64" not in result.output

    def test_build_unknown_distribution_exits_nonzero(self):
        result = CliRunner().invoke(
            cli,
            [
                "build",
                str(FIXTURES / "valid_manifest.yaml"),
                "--distribution",
                "does-not-exist",
                "--dry-run",
            ],
        )
        assert result.exit_code != 0
        combined = result.output + (result.stderr or "")
        assert "not found" in combined.lower()

    def test_build_empty_plan_exits_nonzero(self):
        result = CliRunner().invoke(
            cli,
            [
                "build",
                str(FIXTURES / "valid_manifest.yaml"),
                "--target",
                "riscv64",
                "--dry-run",
            ],
        )
        assert result.exit_code != 0
        combined = result.output + (result.stderr or "")
        assert "no distribution/target" in combined.lower()

    def test_build_without_dry_run_prints_placeholder(self, mocker):
        run = mocker.patch(
            "subprocess.run",
            return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
        )
        result = CliRunner().invoke(
            cli,
            ["build", str(FIXTURES / "valid_manifest.yaml")],
        )
        assert result.exit_code == 0
        assert "built:" in result.output
        assert run.called

    def test_build_output_dir_respected(self):
        result = CliRunner().invoke(
            cli,
            [
                "build",
                str(FIXTURES / "valid_manifest.yaml"),
                "--output-dir",
                "/tmp/customdir",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        assert "/tmp/customdir" in result.output
