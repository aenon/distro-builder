from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from distro_builder.oci.dockerfile import (
    DockerfileSpec,
    DockerStage,
    Mount,
    render_dockerfile,
    write_dockerfile,
)


class TestDockerStage:
    def test_minimal_stage(self):
        s = DockerStage(from_image="alpine:3.19")
        assert s.from_image == "alpine:3.19"
        assert s.commands == []

    def test_empty_from_image_rejected(self):
        with pytest.raises(ValidationError):
            DockerStage(from_image="")

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            DockerStage(from_image="alpine", bogus=1)


class TestDockerfileSpec:
    def test_empty_stages_rejected(self):
        with pytest.raises(ValidationError):
            DockerfileSpec(stages=[])


class TestRenderDockerfile:
    def test_single_stage_from_and_run(self):
        spec = DockerfileSpec(
            stages=[
                DockerStage(
                    from_image="alpine:3.19",
                    commands=["apk add --no-cache curl"],
                ),
            ],
        )
        output = render_dockerfile(spec)
        assert output.startswith("# syntax=docker/dockerfile:")
        assert "FROM alpine:3.19" in output
        assert "RUN apk add --no-cache curl" in output

    def test_multi_stage_with_as_alias(self):
        spec = DockerfileSpec(
            stages=[
                DockerStage(from_image="golang:1.22", name="builder", commands=["go build"]),
                DockerStage(from_image="alpine:3.19", commands=["echo done"]),
            ],
        )
        output = render_dockerfile(spec)
        assert "FROM golang:1.22 AS builder" in output
        assert "FROM alpine:3.19" in output
        assert output.count("FROM ") == 2

    def test_platform_prefix(self):
        spec = DockerfileSpec(
            stages=[
                DockerStage(from_image="alpine:3.19", platform="$BUILDPLATFORM"),
            ],
        )
        output = render_dockerfile(spec)
        assert "FROM --platform=$BUILDPLATFORM alpine:3.19" in output

    def test_run_mount_cache_syntax(self):
        spec = DockerfileSpec(
            stages=[
                DockerStage(
                    from_image="ubuntu:22.04",
                    run_mounts=[Mount(type="cache", target="/var/cache/apt")],
                    commands=["apt-get update"],
                ),
            ],
        )
        output = render_dockerfile(spec)
        assert "--mount=type=cache,target=/var/cache/apt" in output

    def test_env_rendered(self):
        spec = DockerfileSpec(
            stages=[
                DockerStage(from_image="alpine", env={"FOO": "bar", "DEBUG": "1"}),
            ],
        )
        output = render_dockerfile(spec)
        assert "ENV FOO=bar" in output
        assert "ENV DEBUG=1" in output

    def test_workdir_rendered(self):
        spec = DockerfileSpec(
            stages=[DockerStage(from_image="alpine", workdir="/app")],
        )
        assert "WORKDIR /app" in render_dockerfile(spec)

    def test_entrypoint_and_cmd_as_json_array(self):
        spec = DockerfileSpec(
            stages=[
                DockerStage(
                    from_image="alpine",
                    entrypoint=["/bin/sh", "-c"],
                    cmd=["echo hello"],
                ),
            ],
        )
        output = render_dockerfile(spec)
        assert 'ENTRYPOINT ["/bin/sh", "-c"]' in output
        assert 'CMD ["echo hello"]' in output


class TestWriteDockerfile:
    def test_writes_file(self, tmp_path: Path):
        spec = DockerfileSpec(
            stages=[DockerStage(from_image="alpine", commands=["echo ok"])],
        )
        out = tmp_path / "Dockerfile"
        result = write_dockerfile(spec, out)
        assert result == out
        assert out.exists()
        text = out.read_text()
        assert "FROM alpine" in text
        assert "RUN echo ok" in text

    def test_creates_parent_dirs(self, tmp_path: Path):
        spec = DockerfileSpec(stages=[DockerStage(from_image="alpine")])
        out = tmp_path / "nested" / "sub" / "Dockerfile"
        write_dockerfile(spec, out)
        assert out.exists()
