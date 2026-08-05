from __future__ import annotations

from pathlib import Path

from distro_builder.manifest.models import Distribution, Target
from distro_builder.qemu.formats import (
    Qcow2Builder,
    QedBuilder,
    RawDiskBuilder,
    VdiBuilder,
    VhdxBuilder,
    VmdkBuilder,
)

FORMAT_BUILDERS = {
    "qcow2": Qcow2Builder,
    "raw": RawDiskBuilder,
    "vmdk": VmdkBuilder,
    "vdi": VdiBuilder,
    "vhdx": VhdxBuilder,
    "qed": QedBuilder,
}


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
    if distribution.format not in FORMAT_BUILDERS:
        raise QemuPipelineError(
            f"unsupported format {distribution.format!r}; "
            f"supported: {', '.join(sorted(FORMAT_BUILDERS))}"
        )
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    output = workdir / target.output_name
    size = _find_size(distribution)

    FORMAT_BUILDERS[distribution.format]().build(output, size)
    return output
