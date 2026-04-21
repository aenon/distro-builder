from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from distro_builder.iso.initramfs import (
    InitramfsSpec,
    render_dracut_command,
    render_dracut_conf,
    write_dracut_conf,
)


class TestInitramfsSpec:
    def test_valid_minimal(self):
        s = InitramfsSpec(kernel_version="6.6.0-lts")
        assert s.modules == []
        assert s.extra_files == []
        assert s.compress == "zstd"

    def test_empty_kernel_version_rejected(self):
        with pytest.raises(ValidationError):
            InitramfsSpec(kernel_version="")

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            InitramfsSpec(kernel_version="x", bogus=1)


class TestRenderDracutConf:
    def test_basic_config(self):
        spec = InitramfsSpec(kernel_version="6.6.0", modules=["virtio", "ext4"])
        output = render_dracut_conf(spec)
        assert "virtio" in output
        assert "ext4" in output
        assert "compress" in output
        assert 'compress="zstd"' in output

    def test_includes_all_modules(self):
        spec = InitramfsSpec(
            kernel_version="6.6.0", modules=["virtio_blk", "virtio_net", "ext4", "squashfs"]
        )
        output = render_dracut_conf(spec)
        for mod in ("virtio_blk", "virtio_net", "ext4", "squashfs"):
            assert mod in output

    def test_extra_files_rendered(self):
        spec = InitramfsSpec(
            kernel_version="6.6.0",
            extra_files=[Path("/usr/bin/custom-init")],
        )
        output = render_dracut_conf(spec)
        assert "/usr/bin/custom-init" in output
        assert "install_items" in output

    def test_hostonly_flag(self):
        yes = render_dracut_conf(InitramfsSpec(kernel_version="6.6.0", hostonly=True))
        no = render_dracut_conf(InitramfsSpec(kernel_version="6.6.0", hostonly=False))
        assert 'hostonly="yes"' in yes
        assert 'hostonly="no"' in no


class TestRenderDracutCommand:
    def test_basic_command(self):
        spec = InitramfsSpec(kernel_version="6.6.0")
        argv = render_dracut_command(spec, Path("/out/initrd.img"))
        assert argv[0] == "dracut"
        assert "--force" in argv
        assert "--kver" in argv
        assert "6.6.0" in argv
        assert "/out/initrd.img" in argv

    def test_modules_passed_as_add_drivers(self):
        spec = InitramfsSpec(kernel_version="6.6.0", modules=["virtio", "ext4"])
        argv = render_dracut_command(spec, Path("/out/initrd.img"))
        assert argv.count("--add-drivers") == 2
        assert "virtio" in argv
        assert "ext4" in argv

    def test_extra_files_use_install_flag(self):
        spec = InitramfsSpec(kernel_version="6.6.0", extra_files=[Path("/bin/tool")])
        argv = render_dracut_command(spec, Path("/out/initrd.img"))
        assert "--install" in argv
        assert "/bin/tool" in argv

    def test_hostonly_adds_flag(self):
        yes = render_dracut_command(InitramfsSpec(kernel_version="x", hostonly=True), Path("/o"))
        no = render_dracut_command(InitramfsSpec(kernel_version="x", hostonly=False), Path("/o"))
        assert "--hostonly" in yes
        assert "--no-hostonly" in no

    def test_compression_passed(self):
        spec = InitramfsSpec(kernel_version="6.6.0", compress="xz")
        argv = render_dracut_command(spec, Path("/o"))
        idx = argv.index("--compress")
        assert argv[idx + 1] == "xz"


class TestWriteDracutConf:
    def test_writes_file(self, tmp_path: Path):
        spec = InitramfsSpec(kernel_version="6.6.0", modules=["virtio"])
        out = tmp_path / "dracut.conf"
        result = write_dracut_conf(spec, out)
        assert result == out
        assert out.exists()
        assert "virtio" in out.read_text()

    def test_creates_parent_dirs(self, tmp_path: Path):
        spec = InitramfsSpec(kernel_version="6.6.0")
        out = tmp_path / "a" / "b" / "dracut.conf"
        write_dracut_conf(spec, out)
        assert out.exists()
