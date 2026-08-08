from __future__ import annotations

from pathlib import Path

from distro_builder.qemu.qemu_img import QemuImg


class VmdkBuilder:
    def __init__(self, qemu_img: QemuImg | None = None) -> None:
        self.qemu_img = qemu_img or QemuImg()

    def build(
        self,
        output: Path,
        size: str,
        *,
        adapter_type: str = "lsilogic",
        subformat: str = "monolithicFlat",
    ) -> Path:
        options = {
            "adapter_type": adapter_type,
            "subformat": subformat,
        }
        return self.qemu_img.create(output, "vmdk", size, options=options)
