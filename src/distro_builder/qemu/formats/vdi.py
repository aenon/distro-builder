from __future__ import annotations

from pathlib import Path

from distro_builder.qemu.qemu_img import QemuImg


class VdiBuilder:
    def __init__(self, qemu_img: QemuImg | None = None) -> None:
        self.qemu_img = qemu_img or QemuImg()

    def build(self, output: Path, size: str) -> Path:
        return self.qemu_img.create(output, "vdi", size)
