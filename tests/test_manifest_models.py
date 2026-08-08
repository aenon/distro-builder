from __future__ import annotations

import pytest
from pydantic import ValidationError

from distro_builder.manifest.models import (
    Distribution,
    Manifest,
    Stage,
    Target,
)


def _valid_target() -> Target:
    return Target(platform="x86_64", output_name="alpine-minimal-x86_64.iso")


def _valid_distribution(**overrides) -> Distribution:
    data = {
        "name": "alpine-minimal",
        "family": "alpine",
        "description": "minimal alpine",
        "format": "oci",
        "base_image": "alpine:3.19",
        "targets": [_valid_target()],
        "stages": [Stage(name="install-curl", type="install", params={"packages": ["curl"]})],
    }
    data.update(overrides)
    return Distribution(**data)


def _valid_manifest(**overrides) -> Manifest:
    data = {"version": "1", "distributions": [_valid_distribution()]}
    data.update(overrides)
    return Manifest(**data)


class TestTarget:
    def test_valid_target(self):
        t = Target(platform="arm64", output_name="foo.iso")
        assert t.platform == "arm64"
        assert t.output_name == "foo.iso"

    def test_invalid_platform_rejected(self):
        with pytest.raises(ValidationError):
            Target(platform="sparc", output_name="foo.iso")

    def test_empty_output_name_rejected(self):
        with pytest.raises(ValidationError):
            Target(platform="x86_64", output_name="")

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            Target(platform="x86_64", output_name="f.iso", bogus=1)


class TestStage:
    def test_valid_stage(self):
        s = Stage(name="install", type="install", params={"packages": ["vim"]})
        assert s.params["packages"] == ["vim"]

    def test_default_params(self):
        s = Stage(name="x", type="run")
        assert s.params == {}

    def test_invalid_type_rejected(self):
        with pytest.raises(ValidationError):
            Stage(name="x", type="nope")

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            Stage(name="x", type="run", params={}, bogus=1)


class TestDistribution:
    def test_valid_distribution(self):
        d = _valid_distribution()
        assert d.name == "alpine-minimal"
        assert d.format == "oci"
        assert len(d.targets) == 1

    def test_invalid_format_rejected(self):
        with pytest.raises(ValidationError):
            _valid_distribution(format="cpio")

    def test_missing_required_field_rejected(self):
        with pytest.raises(ValidationError):
            Distribution(
                name="x",
                family="alpine",
                base_image="alpine",
                targets=[_valid_target()],
            )

    def test_empty_targets_rejected(self):
        with pytest.raises(ValidationError):
            _valid_distribution(targets=[])

    def test_duplicate_target_platforms_rejected(self):
        t1 = Target(platform="x86_64", output_name="a.iso")
        t2 = Target(platform="x86_64", output_name="b.iso")
        with pytest.raises(ValidationError, match="duplicate target platforms"):
            _valid_distribution(targets=[t1, t2])

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            Distribution(
                name="x",
                family="alpine",
                format="oci",
                base_image="alpine",
                targets=[_valid_target()],
                bogus=1,
            )


class TestManifest:
    def test_valid_manifest(self):
        m = _valid_manifest()
        assert m.version == "1"
        assert len(m.distributions) == 1

    def test_empty_distributions_rejected(self):
        with pytest.raises(ValidationError):
            Manifest(version="1", distributions=[])

    def test_duplicate_distribution_names_rejected(self):
        d1 = _valid_distribution(name="dup")
        d2 = _valid_distribution(name="dup")
        with pytest.raises(ValidationError, match="duplicate distribution names"):
            Manifest(version="1", distributions=[d1, d2])

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            Manifest(version="1", distributions=[_valid_distribution()], bogus=1)
