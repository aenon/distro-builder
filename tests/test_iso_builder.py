from __future__ import annotations

from pathlib import Path

import pycdlib
import pytest

from distro_builder.iso import IsoBuilder, IsoBuilderError


def _read_iso_file(iso_path: Path, member: str) -> bytes:
    iso = pycdlib.PyCdlib()
    iso.open(str(iso_path))
    try:
        extracted = bytearray()
        iso.get_file_from_iso_fp(outfp=_BytesIOLike(extracted), joliet_path=member)
        return bytes(extracted)
    finally:
        iso.close()


class _BytesIOLike:
    def __init__(self, buf: bytearray):
        self._buf = buf

    def write(self, data):
        self._buf.extend(data)
        return len(data)


def _iso_contains(iso_path: Path, member: str) -> bool:
    iso = pycdlib.PyCdlib()
    iso.open(str(iso_path))
    try:
        try:
            iso.get_record(joliet_path=member)
            return True
        except pycdlib.pycdlibexception.PyCdlibInvalidInput:
            return False
    finally:
        iso.close()


class TestIsoBuilderBasics:
    def test_add_file_and_write(self, tmp_path: Path):
        src = tmp_path / "hello.txt"
        src.write_bytes(b"hello world")
        out = tmp_path / "test.iso"

        with IsoBuilder(out) as b:
            b.add_file(src, "/hello.txt")
            b.write()

        assert out.exists()
        assert out.stat().st_size > 0
        assert _iso_contains(out, "/hello.txt")
        assert _read_iso_file(out, "/hello.txt") == b"hello world"

    def test_add_file_under_subdirectory_creates_parents(self, tmp_path: Path):
        src = tmp_path / "data.bin"
        src.write_bytes(b"payload")
        out = tmp_path / "nested.iso"

        b = IsoBuilder(out)
        b.add_file(src, "/boot/grub/data.bin")
        b.write()

        assert _iso_contains(out, "/boot/grub/data.bin")

    def test_add_directory_recursive(self, tmp_path: Path):
        root = tmp_path / "src"
        (root / "sub").mkdir(parents=True)
        (root / "top.txt").write_bytes(b"T")
        (root / "sub" / "inner.txt").write_bytes(b"I")
        out = tmp_path / "dir.iso"

        b = IsoBuilder(out)
        b.add_directory(root, "/payload")
        b.write()

        assert _iso_contains(out, "/payload/top.txt")
        assert _iso_contains(out, "/payload/sub/inner.txt")


class TestIsoBuilderBoot:
    def test_set_boot_record_bios(self, tmp_path: Path):
        boot = tmp_path / "isolinux.bin"
        boot.write_bytes(b"\x00" * 2048)
        out = tmp_path / "boot.iso"

        b = IsoBuilder(out)
        b.add_file(boot, "/ISOLINUX.BIN")
        b.set_boot_record("/ISOLINUX.BIN", "el_torito_bios")
        b.write()

        iso = pycdlib.PyCdlib()
        iso.open(str(out))
        try:
            assert iso.eltorito_boot_catalog is not None
        finally:
            iso.close()

    def test_invalid_boot_type_rejected(self, tmp_path: Path):
        out = tmp_path / "x.iso"
        b = IsoBuilder(out)
        with pytest.raises(IsoBuilderError, match="unsupported boot_type"):
            b.set_boot_record("/BOOT.IMG", "not_a_type")  # type: ignore[arg-type]


class TestIsoBuilderErrors:
    def test_relative_iso_path_rejected(self, tmp_path: Path):
        src = tmp_path / "f.txt"
        src.write_bytes(b"x")
        out = tmp_path / "e.iso"
        b = IsoBuilder(out)
        with pytest.raises(IsoBuilderError, match="must be absolute"):
            b.add_file(src, "relative/path")

    def test_missing_source_file_rejected(self, tmp_path: Path):
        out = tmp_path / "e.iso"
        b = IsoBuilder(out)
        with pytest.raises(IsoBuilderError, match="does not exist"):
            b.add_file(tmp_path / "nope", "/x.txt")

    def test_missing_source_directory_rejected(self, tmp_path: Path):
        out = tmp_path / "e.iso"
        b = IsoBuilder(out)
        with pytest.raises(IsoBuilderError, match="does not exist"):
            b.add_directory(tmp_path / "no-dir", "/x")

    def test_cannot_modify_after_write(self, tmp_path: Path):
        src = tmp_path / "f.txt"
        src.write_bytes(b"x")
        out = tmp_path / "e.iso"
        b = IsoBuilder(out)
        b.add_file(src, "/f.txt")
        b.write()
        with pytest.raises(IsoBuilderError, match="after write"):
            b.add_file(src, "/g.txt")

    def test_cannot_write_twice(self, tmp_path: Path):
        src = tmp_path / "f.txt"
        src.write_bytes(b"x")
        out = tmp_path / "e.iso"
        b = IsoBuilder(out)
        b.add_file(src, "/f.txt")
        b.write()
        with pytest.raises(IsoBuilderError, match="already written"):
            b.write()

    def test_creates_parent_directory_of_output(self, tmp_path: Path):
        src = tmp_path / "f.txt"
        src.write_bytes(b"x")
        out = tmp_path / "deep" / "nested" / "output.iso"
        b = IsoBuilder(out)
        b.add_file(src, "/f.txt")
        b.write()
        assert out.exists()
