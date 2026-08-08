from __future__ import annotations

from pathlib import Path

from distro_builder.iso.grub2 import generate_grub_boot_image
from distro_builder.iso.initramfs import (
    InitramfsSpec,
    render_dracut_command,
    render_dracut_conf,
)


class TestInitramfsWiring:
    def test_render_dracut_command_basic(self, tmp_path: Path):
        spec = InitramfsSpec(
            kernel_version="6.1.0",
            modules=["virtio_blk", "ext4"],
            compress="zstd",
        )
        cmd = render_dracut_command(spec, tmp_path / "initrd.img")
        assert cmd[0] == "dracut"
        assert "--force" in cmd
        assert "--kver" in cmd
        assert "6.1.0" in cmd
        assert "--add-drivers" in cmd
        assert "virtio_blk" in cmd
        assert "ext4" in cmd
        assert "--compress" in cmd
        assert "zstd" in cmd

    def test_render_dracut_conf_includes_modules(self):
        spec = InitramfsSpec(
            kernel_version="5.15.0",
            modules=["xfs", "dm_mod"],
        )
        conf = render_dracut_conf(spec)
        assert "add_drivers" in conf
        assert "xfs" in conf
        assert "dm_mod" in conf

    def test_render_dracut_command_hostonly(self, tmp_path: Path):
        spec = InitramfsSpec(
            kernel_version="6.1.0",
            hostonly=True,
        )
        cmd = render_dracut_command(spec, tmp_path / "initrd.img")
        assert "--hostonly" in cmd


class TestGrubBootImage:
    def test_returns_none_when_grub_mkimage_missing(self, mocker, tmp_path: Path):
        mocker.patch("shutil.which", return_value=None)
        result = generate_grub_boot_image(tmp_path / "boot.img")
        assert result is None

    def test_returns_none_when_grub_mkimage_fails(self, mocker, tmp_path: Path):
        mocker.patch("shutil.which", return_value="/usr/bin/grub-mkimage")
        mocker.patch(
            "subprocess.run",
            return_value=__import__("subprocess").CompletedProcess(
                args=[], returncode=1, stdout="", stderr="failed"
            ),
        )
        result = generate_grub_boot_image(tmp_path / "boot.img")
        assert result is None

    def test_returns_path_on_success(self, mocker, tmp_path: Path):
        fake_path = tmp_path / "grub-mkimage"
        fake_path.write_text("#!/bin/sh\nexit 0")
        fake_path.chmod(0o755)

        mocker.patch("shutil.which", side_effect=lambda x: str(fake_path) if "grub" in x else None)

        result = generate_grub_boot_image(tmp_path / "boot.img")
        assert result is not None
        assert result == tmp_path / "boot.img"

    def test_custom_modules_passed(self, mocker, tmp_path: Path):
        fake_path = tmp_path / "grub-mkimage"
        fake_path.write_text("#!/bin/sh\nexit 0")
        fake_path.chmod(0o755)

        mocker.patch("shutil.which", side_effect=lambda x: str(fake_path) if "grub" in x else None)

        result = generate_grub_boot_image(tmp_path / "boot.img", modules=["biosdisk", "linux"])
        assert result is not None
        assert result == tmp_path / "boot.img"
