from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from distro_builder.manifest.models import Distribution, Stage, Target
from distro_builder.oci.buildx import BuildxBuilder
from distro_builder.oci.dockerfile import DockerfileSpec, DockerStage, render_dockerfile


class OciPipelineError(Exception):
    pass


_PLATFORM_MAP = {
    "x86_64": "linux/amd64",
    "arm64": "linux/arm64",
    "riscv64": "linux/riscv64",
}


@dataclass
class OciBuildPlan:
    dockerfile_text: str
    dockerfile_path: Path
    context_path: Path
    buildx_command: list[str]
    output_path: Path


def _stage_to_docker_command(stage: Stage) -> str | None:
    if stage.type == "run":
        cmd = stage.params.get("command") if stage.params else None
        return str(cmd) if cmd else None
    if stage.type == "install":
        packages = stage.params.get("packages") if stage.params else None
        if not packages:
            return None
        joined = " ".join(packages)
        manager = (stage.params or {}).get("manager", "auto")
        if manager == "apk":
            return f"apk add --no-cache {joined}"
        if manager == "apt":
            return (
                "apt-get update "
                f"&& apt-get install --no-install-recommends -y {joined} "
                "&& rm -rf /var/lib/apt/lists/*"
            )
        if manager == "dnf":
            return f"dnf install -y {joined} && dnf clean all"
        return f"apk add --no-cache {joined} || apt-get update && apt-get install -y {joined}"
    if stage.type == "copy":
        return None
    return None


def build_oci_plan(
    distribution: Distribution,
    target: Target,
    workdir: Path,
) -> OciBuildPlan:
    if distribution.format != "oci":
        raise OciPipelineError(
            f"build_oci called for distribution {distribution.name!r} "
            f"with format={distribution.format!r} (expected 'oci')"
        )
    if target.platform not in _PLATFORM_MAP:
        raise OciPipelineError(f"unsupported target platform: {target.platform!r}")

    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    context = workdir / f"{distribution.name}-{target.platform}-context"
    context.mkdir(parents=True, exist_ok=True)

    commands: list[str] = []
    for stage in distribution.stages:
        cmd = _stage_to_docker_command(stage)
        if cmd:
            commands.append(cmd)

    spec = DockerfileSpec(
        stages=[DockerStage(from_image=distribution.base_image, commands=commands)],
    )
    dockerfile_text = render_dockerfile(spec)
    dockerfile_path = context / "Dockerfile"
    dockerfile_path.write_text(dockerfile_text, encoding="utf-8")

    output_path = workdir / target.output_name
    platform = _PLATFORM_MAP[target.platform]
    tag = f"{distribution.name}:{target.platform}"

    builder = BuildxBuilder()
    buildx_cmd = builder.build_command(
        dockerfile=dockerfile_path,
        context=context,
        tag=tag,
        platforms=[platform],
        output={"type": "oci", "dest": str(output_path)},
    )
    return OciBuildPlan(
        dockerfile_text=dockerfile_text,
        dockerfile_path=dockerfile_path,
        context_path=context,
        buildx_command=buildx_cmd,
        output_path=output_path,
    )


def build_oci(
    distribution: Distribution,
    target: Target,
    workdir: Path,
    *,
    dry_run: bool = False,
) -> OciBuildPlan:
    plan = build_oci_plan(distribution, target, workdir)
    if dry_run:
        return plan
    BuildxBuilder().build(
        dockerfile=plan.dockerfile_path,
        context=plan.context_path,
        tag=f"{distribution.name}:{target.platform}",
        platforms=[_PLATFORM_MAP[target.platform]],
        output={"type": "oci", "dest": str(plan.output_path)},
    )
    return plan
