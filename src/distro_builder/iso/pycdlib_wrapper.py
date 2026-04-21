from __future__ import annotations

import contextlib
import re
from pathlib import Path
from typing import Literal

import pycdlib

BootType = Literal["el_torito_bios", "el_torito_uefi", "hybrid"]


class IsoBuilderError(Exception):
    pass


_VALID_D_CHARS = re.compile(r"[^A-Z0-9_]")


def _to_iso9660_component(name: str, is_file: bool) -> str:
    upper = name.upper().replace("-", "_").replace(".", "_" if not is_file else ".")
    if is_file and "." in upper:
        stem, _, ext = upper.rpartition(".")
        stem = _VALID_D_CHARS.sub("_", stem)[:8]
        ext = _VALID_D_CHARS.sub("_", ext)[:3]
        return f"{stem}.{ext};1" if ext else f"{stem}.;1"
    if is_file:
        stem = _VALID_D_CHARS.sub("_", upper)[:8]
        return f"{stem}.;1"
    return _VALID_D_CHARS.sub("_", upper)[:8]


def _to_iso9660_path(path: str, is_file: bool) -> str:
    parts = path.strip("/").split("/")
    if not parts or parts == [""]:
        return "/"
    iso_parts = [_to_iso9660_component(p, is_file=False) for p in parts[:-1]]
    iso_parts.append(_to_iso9660_component(parts[-1], is_file=is_file))
    return "/" + "/".join(iso_parts)


def _normalize_iso_path(path: str) -> str:
    if not path.startswith("/"):
        raise IsoBuilderError(f"iso_path must be absolute (start with '/'): {path!r}")
    return path


class IsoBuilder:
    def __init__(
        self,
        output_path: Path,
        *,
        vol_ident: str = "DISTROBUILDER",
        sys_ident: str = "",
        interchange_level: int = 3,
        joliet: int | None = 3,
        rock_ridge: str | None = "1.09",
    ) -> None:
        self.output_path = Path(output_path)
        self._iso = pycdlib.PyCdlib()
        self._iso.new(
            interchange_level=interchange_level,
            vol_ident=vol_ident,
            sys_ident=sys_ident,
            joliet=joliet,
            rock_ridge=rock_ridge,
        )
        self._created_dirs: set[str] = {"/"}
        self._written = False
        self._boot_file: str | None = None
        self._boot_type: BootType | None = None

    def _ensure_parent_dirs(self, joliet_path: str) -> None:
        parts = joliet_path.strip("/").split("/")[:-1]
        current_joliet = ""
        for part in parts:
            current_joliet = f"{current_joliet}/{part}" if current_joliet else f"/{part}"
            if current_joliet in self._created_dirs:
                continue
            iso9660 = _to_iso9660_path(current_joliet, is_file=False)
            self._iso.add_directory(
                iso_path=iso9660,
                rr_name=part,
                joliet_path=current_joliet,
            )
            self._created_dirs.add(current_joliet)

    def add_file(self, src: Path, iso_path: str) -> None:
        if self._written:
            raise IsoBuilderError("cannot modify ISO after write()")
        src = Path(src)
        if not src.is_file():
            raise IsoBuilderError(f"source file does not exist: {src}")
        iso_path = _normalize_iso_path(iso_path)
        self._ensure_parent_dirs(iso_path)
        name = iso_path.rsplit("/", 1)[-1]
        iso9660 = _to_iso9660_path(iso_path, is_file=True)
        self._iso.add_file(
            str(src),
            iso_path=iso9660,
            rr_name=name,
            joliet_path=iso_path,
        )

    def add_directory(self, src: Path, iso_path: str) -> None:
        if self._written:
            raise IsoBuilderError("cannot modify ISO after write()")
        src = Path(src)
        if not src.is_dir():
            raise IsoBuilderError(f"source directory does not exist: {src}")
        iso_path = _normalize_iso_path(iso_path)
        if iso_path != "/" and iso_path not in self._created_dirs:
            parts = iso_path.strip("/").split("/")
            current = ""
            for part in parts:
                current = f"{current}/{part}" if current else f"/{part}"
                if current not in self._created_dirs:
                    iso9660 = _to_iso9660_path(current, is_file=False)
                    self._iso.add_directory(
                        iso_path=iso9660,
                        rr_name=part,
                        joliet_path=current,
                    )
                    self._created_dirs.add(current)
        for entry in sorted(src.iterdir()):
            rel = entry.name
            dst = f"{iso_path.rstrip('/')}/{rel}" if iso_path != "/" else f"/{rel}"
            if entry.is_dir():
                self.add_directory(entry, dst)
            elif entry.is_file():
                self.add_file(entry, dst)

    def set_boot_record(self, boot_file: str, boot_type: BootType) -> None:
        if self._written:
            raise IsoBuilderError("cannot modify ISO after write()")
        if boot_type not in ("el_torito_bios", "el_torito_uefi", "hybrid"):
            raise IsoBuilderError(f"unsupported boot_type: {boot_type!r}")
        boot_file = _normalize_iso_path(boot_file)
        boot_file_iso = _to_iso9660_path(boot_file, is_file=True)
        kwargs = {"bootfile_path": boot_file_iso, "bootcatfile": "/BOOT.CAT;1"}
        if boot_type == "el_torito_uefi" or boot_type == "hybrid":
            kwargs["efi"] = True
        self._iso.add_eltorito(**kwargs)
        self._boot_file = boot_file
        self._boot_type = boot_type

    def write(self) -> Path:
        if self._written:
            raise IsoBuilderError("ISO already written")
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self._iso.write(str(self.output_path))
        self._iso.close()
        self._written = True
        return self.output_path

    def __enter__(self) -> IsoBuilder:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if not self._written:
            with contextlib.suppress(Exception):
                self._iso.close()
