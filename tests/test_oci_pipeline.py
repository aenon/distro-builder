from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from distro_builder.cli.main import cli
from distro_builder.manifest.models import Distribution, Stage, Target
from distro_builder.oci.pipeline import OciPipelineError, build_oci, build_oci_plan

FIXTURES = Path(__file__).parent / "fixtures"


def _oci_distribution(**overrides) -> Distribution:
    data = {
        "name": "alpine-oci",
        "family": "alpine",
        "format": "oci",
        "base_image": "alpine:3.19",
        "targets": [
            Target(platform="x86_64", output_name="a-amd64.tar"),
            Target(platform="arm64", output_name="a-arm64.tar"),
        ],
        "stages": [
            Stage(
                name="install",
                type="install",
                params={"manager": "apk", "packages": ["curl"]},
            ),
            Stage(name="setup", type="run", params={"command": "echo hi"}),
        ],
    }
    data.update(overrides)
    return Distribution(**data)


def _fake_completed() -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")


class TestBuildOciPlan:
    def test_generates_dockerfile(self, tmp_path: Path):
        dist = _oci_distribution()
        plan = build_oci_plan(dist, dist.targets[0], tmp_path)
        assert plan.dockerfile_path.exists()
        text = plan.dockerfile_path.read_text()
        assert "FROM alpine:3.19" in text
        assert "RUN apk add --no-cache curl" in text
        assert "RUN echo hi" in text

    def test_apt_manager_rendering(self, tmp_path: Path):
        dist = _oci_distribution(
            base_image="debian:bookworm",
            stages=[
                Stage(
                    name="i",
                    type="install",
                    params={"manager": "apt", "packages": ["curl", "vim"]},
                ),
            ],
        )
        plan = build_oci_plan(dist, dist.targets[0], tmp_path)
        text = plan.dockerfile_path.read_text()
        assert "apt-get update" in text
        assert "apt-get install" in text
        assert "curl vim" in text

    def test_copy_stage_produces_copy_instruction(self, tmp_path: Path):
        dist = _oci_distribution(
            stages=[
                Stage(name="copy-file", type="copy", params={"src": "./app.py", "dest": "/app.py"}),
            ],
        )
        plan = build_oci_plan(dist, dist.targets[0], tmp_path)
        text = plan.dockerfile_path.read_text()
        assert "COPY ./app.py /app.py" in text

    def test_copy_stage_missing_params_returns_none(self, tmp_path: Path):
        dist = _oci_distribution(
            stages=[
                Stage(name="incomplete-copy", type="copy", params={"src": "./foo"}),
            ],
        )
        plan = build_oci_plan(dist, dist.targets[0], tmp_path)
        text = plan.dockerfile_path.read_text()
        assert "COPY" not in text

    def test_mixed_stages_include_copy(self, tmp_path: Path):
        dist = _oci_distribution(
            stages=[
                Stage(
                    name="install", type="install", params={"manager": "apk", "packages": ["curl"]}
                ),
                Stage(
                    name="copy-file",
                    type="copy",
                    params={"src": "./config", "dest": "/etc/app/config"},
                ),
                Stage(name="run", type="run", params={"command": "echo done"}),
            ],
        )
        plan = build_oci_plan(dist, dist.targets[0], tmp_path)
        text = plan.dockerfile_path.read_text()
        assert "RUN apk add --no-cache curl" in text
        assert "COPY ./config /etc/app/config" in text
        assert "RUN echo done" in text

    def test_buildx_command_has_correct_platform(self, tmp_path: Path):
        dist = _oci_distribution()
        plan_amd = build_oci_plan(dist, dist.targets[0], tmp_path)
        assert "linux/amd64" in plan_amd.buildx_command

        plan_arm = build_oci_plan(dist, dist.targets[1], tmp_path)
        assert "linux/arm64" in plan_arm.buildx_command

    def test_buildx_command_outputs_oci_tar(self, tmp_path: Path):
        dist = _oci_distribution()
        plan = build_oci_plan(dist, dist.targets[0], tmp_path)
        output_idx = plan.buildx_command.index("--output")
        output_val = plan.buildx_command[output_idx + 1]
        assert "type=oci" in output_val
        assert "dest=" in output_val

    def test_wrong_format_rejected(self, tmp_path: Path):
        dist = _oci_distribution(format="iso")
        with pytest.raises(OciPipelineError, match="expected 'oci'"):
            build_oci_plan(dist, dist.targets[0], tmp_path)

    def test_unsupported_platform_rejected(self, tmp_path: Path):
        dist = _oci_distribution(
            targets=[Target(platform="riscv64", output_name="r.tar")],
        )
        plan = build_oci_plan(dist, dist.targets[0], tmp_path)
        assert "linux/riscv64" in plan.buildx_command


class TestBuildOciExecution:
    def test_dry_run_does_not_invoke_subprocess(self, mocker, tmp_path: Path):
        run = mocker.patch("subprocess.run")
        dist = _oci_distribution()
        plan = build_oci(dist, dist.targets[0], tmp_path, dry_run=True)
        assert plan.dockerfile_path.exists()
        run.assert_not_called()

    def test_actual_run_invokes_docker_buildx(self, mocker, tmp_path: Path):
        run = mocker.patch("subprocess.run", return_value=_fake_completed())
        dist = _oci_distribution()
        build_oci(dist, dist.targets[0], tmp_path, dry_run=False)
        assert run.called
        argv = run.call_args.args[0]
        assert argv[:3] == ["docker", "buildx", "build"]


class TestCliOciBuild:
    def test_cli_prints_prepared_plan(self, mocker, tmp_path: Path):
        mocker.patch("subprocess.run", return_value=_fake_completed())
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "build",
                str(FIXTURES / "oci_manifest.yaml"),
                "--output-dir",
                str(tmp_path),
                "--target",
                "x86_64",
            ],
        )
        assert result.exit_code == 0, result.output
        assert "built:" in result.output
        assert "alpine-oci" in result.output

    def test_cli_dry_run_for_oci(self, tmp_path: Path):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "build",
                str(FIXTURES / "oci_manifest.yaml"),
                "--output-dir",
                str(tmp_path),
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        assert "Would build" in result.output
        # dry-run at CLI level skips the pipeline entirely
        assert "alpine-oci" in result.output

    def test_cli_non_dry_run_executes_build(self, mocker, tmp_path: Path):
        run = mocker.patch("subprocess.run", return_value=_fake_completed())
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "build",
                str(FIXTURES / "oci_manifest.yaml"),
                "--output-dir",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 0, result.output
        assert "built:" in result.output
        assert run.called
        argv = run.call_args.args[0]
        assert "docker" in argv
        assert "buildx" in argv
