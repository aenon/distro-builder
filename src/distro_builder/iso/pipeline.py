from __future__ import annotations

import subprocess
from pathlib import Path

from distro_builder.iso.grub2 import (
    GrubConfig,
    MenuEntry,
    generate_grub_boot_image,
    write_grub_cfg,
)
from distro_builder.iso.initramfs import InitramfsSpec, render_dracut_command
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


def _build_initramfs(stage: Stage, workdir: Path, kernel_version: str | None) -> Path | None:
    """Try to build an initramfs via dracut from stage params.

    Returns the path to the generated initramfs, or None if dracut is not available.
    """
    output_path = workdir / "initrd.img"
    spec = InitramfsSpec(
        kernel_version=kernel_version or stage.params.get("version", "0.0.0"),
        modules=stage.params.get("modules", []),
        extra_files=stage.params.get("extra_files", []),
        compress=stage.params.get("compress", "zstd"),
        hostonly=stage.params.get("hostonly", False),
    )
    argv = render_dracut_command(spec, output_path)
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, check=False)
        if proc.returncode == 0 and output_path.is_file():
            return output_path
    except OSError:
        pass
    return None


def _get_initramfs_path(stage: Stage | None, workdir: Path, kernel_version: str | None) -> Path:
    """Resolve the initramfs source: pre-built path, dracut build, or placeholder."""
    if stage and "path" in stage.params:
        path = Path(stage.params["path"])
        if path.is_file():
            return path
    if stage:
        built = _build_initramfs(stage, workdir, kernel_version)
        if built is not None:
            return built
    return _placeholder_kernel(workdir / "placeholders", "initrd.img")


def _resolve_kernel_path(stage: Stage | None, workdir: Path) -> tuple[Path, str | None]:
    """Resolve kernel source and extract version string.

    Returns (path, version).
    """
    if stage and "path" in stage.params:
        path = Path(stage.params["path"])
        version = stage.params.get("version")
        return path, version
    kernel_path = _placeholder_kernel(workdir / "placeholders", "vmlinuz")
    version = stage.params.get("version") if stage else None
    return kernel_path, version


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

    kernel_src, kernel_version = _resolve_kernel_path(kernel_stage, staging)
    initrd_src = _get_initramfs_path(initramfs_stage, staging, kernel_version)
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

    # Generate GRUB2 BIOS boot image (boot.img) for bootable ISO
    grub_boot_path = grub_dir / "boot.img"
    grub_modules = grub_stage.params.get("grub_modules") if grub_stage is not None else None
    generated_boot = generate_grub_boot_image(
        grub_boot_path,
        modules=grub_modules,
        config_path=grub_iso_path,
        prefix="/boot/grub",
    )

    output_path = workdir / target.output_name
    builder = IsoBuilder(
        output_path,
        vol_ident=distribution.name.upper().replace("-", "_")[:32],
    )
    builder.add_file(kernel_src, kernel_iso_path)
    builder.add_file(initrd_src, initrd_iso_path)
    builder.add_file(grub_cfg_path, grub_iso_path)

    # Add the GRUB boot image if it was generated
    if generated_boot and generated_boot.is_file():
        builder.add_file(generated_boot, "/boot/grub/boot.img")
        # Point El Torito boot record at the bootloader binary, not the kernel
        builder.set_boot_record("/boot/grub/boot.img", "el_torito_bios")
    else:
        # Fallback to kernel boot (non-GRUB, not truly bootable)
        builder.set_boot_record(kernel_iso_path, "el_torito_bios")
    builder.write()
    return output_path
