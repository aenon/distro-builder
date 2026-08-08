from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


MountType = Literal["cache", "bind", "tmpfs", "secret", "ssh"]


class Mount(_StrictModel):
    type: MountType
    target: str = Field(min_length=1)
    source: str | None = None
    cache_id: str | None = None


class DockerStage(_StrictModel):
    from_image: str = Field(min_length=1)
    name: str | None = None
    platform: str | None = None
    commands: list[str] = Field(default_factory=list)
    run_mounts: list[Mount] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    workdir: str | None = None
    entrypoint: list[str] | None = None
    cmd: list[str] | None = None


class DockerfileSpec(_StrictModel):
    syntax: str = "docker/dockerfile:1.7"
    stages: list[DockerStage] = Field(min_length=1)


def _render_mount(mount: Mount) -> str:
    parts = [f"type={mount.type}", f"target={mount.target}"]
    if mount.source:
        parts.append(f"source={mount.source}")
    if mount.cache_id:
        parts.append(f"id={mount.cache_id}")
    return ",".join(parts)


def _render_stage(stage: DockerStage) -> str:
    lines: list[str] = []
    from_line = "FROM"
    if stage.platform:
        from_line += f" --platform={stage.platform}"
    from_line += f" {stage.from_image}"
    if stage.name:
        from_line += f" AS {stage.name}"
    lines.append(from_line)
    if stage.workdir:
        lines.append(f"WORKDIR {stage.workdir}")
    for k, v in stage.env.items():
        lines.append(f"ENV {k}={v}")
    for cmd in stage.commands:
        if stage.run_mounts:
            mount_flags = " ".join(f"--mount={_render_mount(m)}" for m in stage.run_mounts)
            lines.append(f"RUN {mount_flags} {cmd}")
        else:
            lines.append(f"RUN {cmd}")
    if stage.entrypoint is not None:
        entrypoint_json = "[" + ", ".join(f'"{x}"' for x in stage.entrypoint) + "]"
        lines.append(f"ENTRYPOINT {entrypoint_json}")
    if stage.cmd is not None:
        cmd_json = "[" + ", ".join(f'"{x}"' for x in stage.cmd) + "]"
        lines.append(f"CMD {cmd_json}")
    return "\n".join(lines)


def render_dockerfile(spec: DockerfileSpec) -> str:
    sections: list[str] = [f"# syntax={spec.syntax}"]
    for idx, stage in enumerate(spec.stages):
        if idx > 0:
            sections.append("")
        sections.append(_render_stage(stage))
    return "\n".join(sections) + "\n"


def write_dockerfile(spec: DockerfileSpec, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_dockerfile(spec), encoding="utf-8")
    return path
