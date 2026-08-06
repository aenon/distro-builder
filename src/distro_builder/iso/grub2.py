from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class MenuEntry(_StrictModel):
    title: str = Field(min_length=1)
    kernel_path: str = Field(min_length=1)
    initrd_path: str = Field(min_length=1)
    kernel_cmdline: str = ""


class GrubConfig(_StrictModel):
    timeout: int = Field(default=5, ge=0)
    default: int = Field(default=0, ge=0)
    menuentries: list[MenuEntry] = Field(min_length=1)


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "'\\''")


def render_grub_cfg(config: GrubConfig) -> str:
    if config.default >= len(config.menuentries):
        raise ValueError(
            f"default index {config.default} out of range (have {len(config.menuentries)} entries)"
        )
    lines: list[str] = [
        f"set timeout={config.timeout}",
        f"set default={config.default}",
        "",
    ]
    for entry in config.menuentries:
        lines.append(f"menuentry '{_escape(entry.title)}' {{")
        linux_line = f"    linux {entry.kernel_path}"
        if entry.kernel_cmdline:
            linux_line += f" {entry.kernel_cmdline}"
        lines.append(linux_line)
        lines.append(f"    initrd {entry.initrd_path}")
        lines.append("}")
        lines.append("")
    return "\n".join(lines)


def write_grub_cfg(config: GrubConfig, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_grub_cfg(config), encoding="utf-8")
    return path


def generate_grub_boot_image(
    output: Path,
    *,
    modules: list[str] | None = None,
    grub_mkdir: str | None = "/boot/grub",
    config_path: str | None = "/boot/grub/grub.cfg",
    prefix: str | None = "/boot/grub",
) -> Path | None:
    """Generate a GRUB2 BIOS boot image using grub-mkimage.

    Returns the output path on success, or None if grub-mkimage is not available.
    """
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    grub_mkimage = shutil.which("grub-mkimage") or shutil.which("grub2-mkimage")
    if not grub_mkimage:
        return None

    default_modules = [
        "biosdisk",
        "boot",
        "cat",
        "configfile",
        "echo",
        "fat",
        "font",
        "gettext",
        "gfxterm",
        "grubenv",
        "halt",
        "iso9660",
        "linux",
        "normal",
        "part_msdos",
        "reboot",
        "search",
        "sleep",
        "test",
        "video",
    ]
    if modules is None:
        modules = default_modules

    argv = [grub_mkimage, "-o", str(output), "-O", "i386-pc", "-c", "/dev/null"]
    if grub_mkdir is not None:
        argv.extend(["--grub-mkdir", grub_mkdir])
    if config_path is not None:
        argv.extend(["-C", config_path])
    if prefix is not None:
        argv.extend(["-p", prefix])
    argv.extend(modules)

    try:
        proc = subprocess.run(argv, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            return None
    except OSError:
        return None

    return output
