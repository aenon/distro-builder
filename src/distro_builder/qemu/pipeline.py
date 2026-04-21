from __future__ import annotations

from pathlib import Path

from distro_builder.manifest.models import Distribution, Target
from distro_builder.qemu.formats import Qcow2Builder, RawDiskBuilder


class QemuPipelineError(Exception):
    pass


def _find_size(distribution: Distribution) -> str:
    for stage in distribution.stages:
        size = stage.params.get("size") if stage.params else None
        if size:
            return str(size)
    return "1G"


def build_qemu_image(
    distribution: Distribution,
    target: Target,
    workdir: Path,
) -> Path:
    if distribution.format not in ("qcow2", "raw"):
        raise QemuPipelineError(
            f"build_qemu_image called for distribution {distribution.name!r} "
            f"with format={distribution.format!r} (expected 'qcow2' or 'raw')"
        )
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    output = workdir / target.output_name
    size = _find_size(distribution)

    if distribution.format == "qcow2":
        Qcow2Builder().build(output, size)
    else:
        RawDiskBuilder().build(output, size)
    return output
