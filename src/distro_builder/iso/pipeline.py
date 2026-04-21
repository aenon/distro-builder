from __future__ import annotations

from pathlib import Path

from distro_builder.iso.grub2 import GrubConfig, MenuEntry, write_grub_cfg
from distro_builder.iso.pycdlib_wrapper import IsoBuilder
from distro_builder.manifest.models import Distribution, Stage, Target


class PipelineError(Exception):
    pass


def _stages_by_type(stages: list[Stage], stage_type: str) -> list[Stage]:
    return [s for s in stages if s.type == stage_type]


def _get_single(stages: list[Stage], stage_type: str, required: bool = False) -> Stage | None:
    found = _stages_by_type(stages, stage_type)
    if len(found) > 1:
        raise PipelineError(f"multiple {stage_type!r} stages defined, expected at most one")
    if not found:
        if required:
            raise PipelineError(f"{stage_type!r} stage required for ISO builds")
        return None
    return found[0]


def _placeholder_kernel(workdir: Path, name: str) -> Path:
    path = workdir / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(b"\x00" * 64)
    return path


def build_iso(
    distribution: Distribution,
    target: Target,
    workdir: Path,
) -> Path:
    if distribution.format != "iso":
        raise PipelineError(
            f"build_iso called for distribution {distribution.name!r} "
            f"with format={distribution.format!r} (expected 'iso')"
        )
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    staging = workdir / f"{distribution.name}-{target.platform}-staging"
    staging.mkdir(parents=True, exist_ok=True)
    boot_dir = staging / "boot"
    grub_dir = boot_dir / "grub"
    grub_dir.mkdir(parents=True, exist_ok=True)

    kernel_stage = _get_single(distribution.stages, "kernel")
    initramfs_stage = _get_single(distribution.stages, "initramfs")
    grub_stage = _get_single(distribution.stages, "grub")

    kernel_src = (
        Path(kernel_stage.params["path"])
        if kernel_stage and "path" in kernel_stage.params
        else _placeholder_kernel(workdir / "placeholders", "vmlinuz")
    )
    initrd_src = (
        Path(initramfs_stage.params["path"])
        if initramfs_stage and "path" in initramfs_stage.params
        else _placeholder_kernel(workdir / "placeholders", "initrd.img")
    )
    if not kernel_src.is_file():
        raise PipelineError(f"kernel source not found: {kernel_src}")
    if not initrd_src.is_file():
        raise PipelineError(f"initrd source not found: {initrd_src}")

    kernel_iso_path = "/boot/vmlinuz"
    initrd_iso_path = "/boot/initrd.img"
    grub_iso_path = "/boot/grub/grub.cfg"

    title_default = f"{distribution.name} ({target.platform})"
    cmdline_default = "root=/dev/sr0 ro quiet"
    if grub_stage is not None:
        title = grub_stage.params.get("title", title_default)
        cmdline = grub_stage.params.get("kernel_cmdline", cmdline_default)
        timeout = int(grub_stage.params.get("timeout", 5))
    else:
        title = title_default
        cmdline = cmdline_default
        timeout = 5

    grub_cfg = GrubConfig(
        timeout=timeout,
        default=0,
        menuentries=[
            MenuEntry(
                title=title,
                kernel_path=kernel_iso_path,
                initrd_path=initrd_iso_path,
                kernel_cmdline=cmdline,
            ),
        ],
    )
    grub_cfg_path = grub_dir / "grub.cfg"
    write_grub_cfg(grub_cfg, grub_cfg_path)

    output_path = workdir / target.output_name
    builder = IsoBuilder(
        output_path,
        vol_ident=distribution.name.upper().replace("-", "_")[:32],
    )
    builder.add_file(kernel_src, kernel_iso_path)
    builder.add_file(initrd_src, initrd_iso_path)
    builder.add_file(grub_cfg_path, grub_iso_path)
    builder.set_boot_record(kernel_iso_path, "el_torito_bios")
    builder.write()
    return output_path
