from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from distro_builder.iso.grub2 import GrubConfig, MenuEntry, render_grub_cfg, write_grub_cfg


class TestMenuEntry:
    def test_valid_entry(self):
        e = MenuEntry(title="Linux", kernel_path="/boot/vmlinuz", initrd_path="/boot/initrd.img")
        assert e.title == "Linux"
        assert e.kernel_cmdline == ""

    def test_empty_title_rejected(self):
        with pytest.raises(ValidationError):
            MenuEntry(title="", kernel_path="/k", initrd_path="/i")

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            MenuEntry(title="t", kernel_path="/k", initrd_path="/i", bogus=1)


class TestGrubConfig:
    def test_valid_single_entry(self):
        c = GrubConfig(
            timeout=10,
            default=0,
            menuentries=[MenuEntry(title="L", kernel_path="/k", initrd_path="/i")],
        )
        assert c.timeout == 10

    def test_empty_menuentries_rejected(self):
        with pytest.raises(ValidationError):
            GrubConfig(menuentries=[])

    def test_negative_timeout_rejected(self):
        with pytest.raises(ValidationError):
            GrubConfig(
                timeout=-1,
                menuentries=[MenuEntry(title="L", kernel_path="/k", initrd_path="/i")],
            )


class TestRenderGrubCfg:
    def _cfg(self) -> GrubConfig:
        return GrubConfig(
            timeout=5,
            default=0,
            menuentries=[
                MenuEntry(
                    title="Alpine Linux",
                    kernel_path="/boot/vmlinuz-lts",
                    initrd_path="/boot/initramfs-lts",
                    kernel_cmdline="root=/dev/sda1 ro quiet",
                ),
            ],
        )

    def test_contains_required_keywords(self):
        output = render_grub_cfg(self._cfg())
        assert "menuentry" in output
        assert "linux " in output
        assert "initrd " in output
        assert "set timeout=5" in output
        assert "set default=0" in output

    def test_kernel_cmdline_appended(self):
        output = render_grub_cfg(self._cfg())
        assert "/boot/vmlinuz-lts root=/dev/sda1 ro quiet" in output

    def test_no_cmdline_omits_trailing_space(self):
        cfg = GrubConfig(
            menuentries=[MenuEntry(title="t", kernel_path="/k", initrd_path="/i")],
        )
        output = render_grub_cfg(cfg)
        assert "    linux /k\n" in output

    def test_multi_entry_render(self):
        cfg = GrubConfig(
            default=1,
            menuentries=[
                MenuEntry(title="First", kernel_path="/k1", initrd_path="/i1"),
                MenuEntry(title="Second", kernel_path="/k2", initrd_path="/i2"),
            ],
        )
        output = render_grub_cfg(cfg)
        assert output.count("menuentry ") == 2
        assert "First" in output
        assert "Second" in output
        assert "set default=1" in output

    def test_default_out_of_range_raises(self):
        cfg = GrubConfig(
            default=5,
            menuentries=[MenuEntry(title="only", kernel_path="/k", initrd_path="/i")],
        )
        with pytest.raises(ValueError, match="default index"):
            render_grub_cfg(cfg)

    def test_special_characters_escaped(self):
        cfg = GrubConfig(
            menuentries=[
                MenuEntry(title="It's complex", kernel_path="/k", initrd_path="/i"),
            ],
        )
        output = render_grub_cfg(cfg)
        assert "It" in output
        assert "complex" in output


class TestWriteGrubCfg:
    def test_writes_to_file(self, tmp_path: Path):
        cfg = GrubConfig(
            menuentries=[MenuEntry(title="t", kernel_path="/k", initrd_path="/i")],
        )
        out = tmp_path / "grub" / "grub.cfg"
        result = write_grub_cfg(cfg, out)
        assert result == out
        assert out.exists()
        assert "menuentry" in out.read_text()

    def test_creates_parent_dirs(self, tmp_path: Path):
        cfg = GrubConfig(
            menuentries=[MenuEntry(title="t", kernel_path="/k", initrd_path="/i")],
        )
        out = tmp_path / "deep" / "nested" / "grub.cfg"
        write_grub_cfg(cfg, out)
        assert out.exists()
