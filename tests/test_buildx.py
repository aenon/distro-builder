from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from distro_builder.oci.buildx import BuildxBuilder, BuildxError


def _fake_completed(
    returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


class TestBuildCommand:
    def test_single_platform(self):
        b = BuildxBuilder()
        argv = b.build_command(
            dockerfile=Path("Dockerfile"),
            context=Path("."),
            tag="myimg:latest",
            platforms=["linux/amd64"],
        )
        assert argv[0:3] == ["docker", "buildx", "build"]
        assert "--platform" in argv
        assert argv[argv.index("--platform") + 1] == "linux/amd64"
        assert "--tag" in argv
        assert argv[argv.index("--tag") + 1] == "myimg:latest"
        assert argv[-1] == "."

    def test_multi_platform(self):
        b = BuildxBuilder()
        argv = b.build_command(
            dockerfile=Path("Dockerfile"),
            context=Path("."),
            tag="myimg:latest",
            platforms=["linux/amd64", "linux/arm64"],
        )
        assert argv[argv.index("--platform") + 1] == "linux/amd64,linux/arm64"

    def test_output_option(self):
        b = BuildxBuilder()
        argv = b.build_command(
            dockerfile=Path("Dockerfile"),
            context=Path("."),
            tag="myimg:latest",
            platforms=["linux/amd64"],
            output={"type": "oci", "dest": "/tmp/out.tar"},
        )
        assert "--output" in argv
        out_val = argv[argv.index("--output") + 1]
        assert "type=oci" in out_val
        assert "dest=/tmp/out.tar" in out_val

    def test_build_args(self):
        b = BuildxBuilder()
        argv = b.build_command(
            dockerfile=Path("Dockerfile"),
            context=Path("."),
            tag="myimg:latest",
            platforms=["linux/amd64"],
            build_args={"VERSION": "1.0", "DEBUG": "true"},
        )
        assert argv.count("--build-arg") == 2
        assert "VERSION=1.0" in argv
        assert "DEBUG=true" in argv

    def test_push_and_load_flags(self):
        b = BuildxBuilder()
        argv = b.build_command(
            dockerfile=Path("Dockerfile"),
            context=Path("."),
            tag="myimg:latest",
            platforms=["linux/amd64"],
            push=True,
            load=False,
        )
        assert "--push" in argv
        assert "--load" not in argv

    def test_builder_override(self):
        b = BuildxBuilder()
        argv = b.build_command(
            dockerfile=Path("Dockerfile"),
            context=Path("."),
            tag="t",
            platforms=["linux/amd64"],
            builder="mybuilder",
        )
        assert "--builder" in argv
        assert argv[argv.index("--builder") + 1] == "mybuilder"

    def test_empty_platforms_rejected(self):
        b = BuildxBuilder()
        with pytest.raises(BuildxError, match="at least one platform"):
            b.build_command(
                dockerfile=Path("Dockerfile"),
                context=Path("."),
                tag="t",
                platforms=[],
            )


class TestBuildxRun:
    def test_build_invokes_subprocess(self, mocker):
        run = mocker.patch("subprocess.run", return_value=_fake_completed())
        b = BuildxBuilder()
        b.build(
            dockerfile=Path("Dockerfile"),
            context=Path("."),
            tag="t:1",
            platforms=["linux/amd64"],
        )
        argv = run.call_args.args[0]
        assert argv[0:3] == ["docker", "buildx", "build"]

    def test_build_failure_raises(self, mocker):
        mocker.patch("subprocess.run", return_value=_fake_completed(returncode=1, stderr="oops"))
        b = BuildxBuilder()
        with pytest.raises(BuildxError, match="exit 1"):
            b.build(
                dockerfile=Path("Dockerfile"),
                context=Path("."),
                tag="t",
                platforms=["linux/amd64"],
            )

    def test_missing_docker_raises(self, mocker):
        mocker.patch("subprocess.run", side_effect=FileNotFoundError())
        b = BuildxBuilder(docker_binary="/no/such/docker")
        with pytest.raises(BuildxError, match="not found"):
            b.build(
                dockerfile=Path("Dockerfile"),
                context=Path("."),
                tag="t",
                platforms=["linux/amd64"],
            )


class TestEnsureBuilder:
    def test_creates_new_builder(self, mocker):
        run = mocker.patch("subprocess.run")
        ls_result = _fake_completed(stdout="other-builder  docker-container\n")
        create_result = _fake_completed()
        run.side_effect = [ls_result, create_result]

        b = BuildxBuilder()
        b.ensure_builder("mybuilder")

        last_call = run.call_args_list[-1]
        argv = last_call.args[0]
        assert "create" in argv
        assert "mybuilder" in argv
        assert "docker-container" in argv
        assert "--use" in argv

    def test_existing_builder_is_switched_to(self, mocker):
        run = mocker.patch("subprocess.run")
        ls_result = _fake_completed(stdout="mybuilder  docker-container\n")
        use_result = _fake_completed()
        run.side_effect = [ls_result, use_result]

        b = BuildxBuilder()
        b.ensure_builder("mybuilder")

        last_call = run.call_args_list[-1]
        argv = last_call.args[0]
        assert argv[1:] == ["buildx", "use", "mybuilder"]
