from __future__ import annotations

from pathlib import Path

from distro_builder.qemu.qemu_img import DiskFormat, QemuImg


class Qcow2Builder:
    def __init__(self, qemu_img: QemuImg | None = None) -> None:
        self.qemu_img = qemu_img or QemuImg()

    def build(
        self,
        output: Path,
        size: str,
        *,
        backing_file: Path | None = None,
        backing_format: DiskFormat | None = None,
        compression: str | None = "zstd",
        cluster_size: int | None = None,
    ) -> Path:
        options: dict[str, str] = {}
        if compression:
            options["compression_type"] = compression
        if cluster_size is not None:
            options["cluster_size"] = str(cluster_size)
        return self.qemu_img.create(
            output,
            "qcow2",
            size,
            backing_file=backing_file,
            backing_format=backing_format,
            options=options or None,
        )
