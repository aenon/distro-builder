from __future__ import annotations

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
