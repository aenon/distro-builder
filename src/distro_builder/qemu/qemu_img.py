from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Literal

DiskFormat = Literal["raw", "qcow2", "vmdk", "vdi", "vhdx", "qed"]


class QemuImgError(Exception):
    def __init__(self, message: str, *, argv: list[str] | None = None, stderr: str | None = None):
        super().__init__(message)
        self.argv = argv or []
        self.stderr = stderr or ""


class QemuImg:
    def __init__(self, binary: str | Path = "qemu-img") -> None:
        self.binary = str(binary)

    def _run(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        argv = [self.binary, *args]
        try:
            proc = subprocess.run(
                argv,
                check=False,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as exc:
            raise QemuImgError(f"qemu-img binary not found: {self.binary}", argv=argv) from exc
        if proc.returncode != 0:
            raise QemuImgError(
                f"qemu-img {args[0] if args else ''} failed (exit {proc.returncode}): "
                f"{proc.stderr.strip()}",
                argv=argv,
                stderr=proc.stderr,
            )
        return proc

    def available(self) -> bool:
        if not shutil.which(self.binary):
            return False
        try:
            self._run(["--version"])
            return True
        except QemuImgError:
            return False

    def create(
        self,
        path: Path,
        image_format: DiskFormat,
        size: str,
        *,
        backing_file: Path | None = None,
        backing_format: DiskFormat | None = None,
        options: dict[str, str] | None = None,
    ) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        args = ["create", "-f", image_format]
        all_opts: dict[str, str] = {}
        if backing_file is not None:
            all_opts["backing_file"] = str(backing_file)
            if backing_format is not None:
                all_opts["backing_fmt"] = backing_format
        if options:
            all_opts.update(options)
        if all_opts:
            args.extend(["-o", ",".join(f"{k}={v}" for k, v in all_opts.items())])
        args.extend([str(path), size])
        self._run(args)
        return path

    def convert(
        self,
        src: Path,
        dst: Path,
        src_format: DiskFormat,
        dst_format: DiskFormat,
        *,
        compressed: bool = False,
    ) -> Path:
        dst = Path(dst)
        dst.parent.mkdir(parents=True, exist_ok=True)
        args = ["convert", "-f", src_format, "-O", dst_format]
        if compressed:
            args.append("-c")
        args.extend([str(src), str(dst)])
        self._run(args)
        return dst

    def info(self, path: Path) -> dict:
        proc = self._run(["info", "--output=json", str(path)])
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise QemuImgError(
                f"qemu-img info returned invalid JSON: {exc}", stderr=proc.stdout
            ) from exc

    def resize(self, path: Path, new_size: str) -> None:
        self._run(["resize", str(path), new_size])

    def snapshot_create(self, path: Path, name: str) -> None:
        self._run(["snapshot", "-c", name, str(path)])

    def snapshot_list(self, path: Path) -> list[str]:
        proc = self._run(["snapshot", "-l", str(path)])
        lines = proc.stdout.strip().splitlines()
        return [line for line in lines if line and not line.startswith(("Snapshot", "ID"))]

    def snapshot_apply(self, path: Path, name: str) -> None:
        self._run(["snapshot", "-a", name, str(path)])

    def snapshot_delete(self, path: Path, name: str) -> None:
        self._run(["snapshot", "-d", name, str(path)])

    def commit(self, path: Path) -> None:
        self._run(["commit", str(path)])

    def rebase(
        self,
        path: Path,
        backing: Path,
        *,
        backing_format: DiskFormat | None = None,
        safe: bool = True,
    ) -> None:
        args = ["rebase"]
        if not safe:
            args.append("-u")
        if backing_format is not None:
            args.extend(["-F", backing_format])
        args.extend(["-b", str(backing), str(path)])
        self._run(args)
