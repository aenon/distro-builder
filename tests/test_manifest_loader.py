from __future__ import annotations

from pathlib import Path

import pytest

from distro_builder.manifest import Manifest, ManifestLoadError, load_manifest

FIXTURES = Path(__file__).parent / "fixtures"


class TestLoadManifest:
    def test_loads_yaml(self):
        m = load_manifest(FIXTURES / "valid_manifest.yaml")
        assert isinstance(m, Manifest)
        assert m.version == "1"
        assert len(m.distributions) == 1
        assert m.distributions[0].name == "alpine-minimal"
        assert m.distributions[0].format == "oci"
        assert len(m.distributions[0].targets) == 2
        assert {t.platform for t in m.distributions[0].targets} == {"x86_64", "arm64"}

    def test_loads_json(self):
        m = load_manifest(FIXTURES / "valid_manifest.json")
        assert isinstance(m, Manifest)
        assert m.version == "1"
        assert m.distributions[0].name == "alpine-minimal"

    def test_yaml_and_json_produce_equivalent_manifests(self):
        y = load_manifest(FIXTURES / "valid_manifest.yaml")
        j = load_manifest(FIXTURES / "valid_manifest.json")
        assert y.version == j.version
        assert y.distributions[0].name == j.distributions[0].name
        assert y.distributions[0].format == j.distributions[0].format

    def test_invalid_manifest_raises_load_error(self):
        with pytest.raises(ManifestLoadError):
            load_manifest(FIXTURES / "invalid_manifest.yaml")

    def test_missing_file_raises_filenotfound(self):
        with pytest.raises(FileNotFoundError):
            load_manifest(FIXTURES / "does_not_exist.yaml")

    def test_unsupported_extension_raises_load_error(self, tmp_path: Path):
        p = tmp_path / "manifest.toml"
        p.write_text("version = '1'")
        with pytest.raises(ManifestLoadError, match="unsupported manifest extension"):
            load_manifest(p)

    def test_malformed_yaml_raises_load_error(self, tmp_path: Path):
        p = tmp_path / "bad.yaml"
        p.write_text("version: [unclosed\n")
        with pytest.raises(ManifestLoadError, match="invalid YAML"):
            load_manifest(p)

    def test_malformed_json_raises_load_error(self, tmp_path: Path):
        p = tmp_path / "bad.json"
        p.write_text("{ not valid json")
        with pytest.raises(ManifestLoadError, match="invalid JSON"):
            load_manifest(p)

    def test_non_mapping_root_raises_load_error(self, tmp_path: Path):
        p = tmp_path / "list.yaml"
        p.write_text("- just\n- a\n- list\n")
        with pytest.raises(ManifestLoadError, match="root must be a mapping"):
            load_manifest(p)

    def test_accepts_string_path(self):
        m = load_manifest(str(FIXTURES / "valid_manifest.yaml"))
        assert isinstance(m, Manifest)
