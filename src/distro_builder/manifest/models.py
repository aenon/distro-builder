from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Platform = Literal["x86_64", "arm64", "riscv64"]
StageType = Literal["run", "copy", "install", "kernel", "initramfs", "grub", "iso"]
DistroFormat = Literal["iso", "qcow2", "raw", "oci"]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=False, str_strip_whitespace=True)


class Target(_StrictModel):
    platform: Platform
    output_name: str = Field(min_length=1)


class Stage(_StrictModel):
    name: str = Field(min_length=1)
    type: StageType
    params: dict[str, Any] = Field(default_factory=dict)


class Distribution(_StrictModel):
    name: str = Field(min_length=1)
    family: str = Field(min_length=1)
    description: str = ""
    format: DistroFormat
    base_image: str = Field(min_length=1)
    targets: list[Target] = Field(min_length=1)
    stages: list[Stage] = Field(default_factory=list)

    @field_validator("targets")
    @classmethod
    def _unique_target_platforms(cls, v: list[Target]) -> list[Target]:
        platforms = [t.platform for t in v]
        if len(platforms) != len(set(platforms)):
            raise ValueError("duplicate target platforms are not allowed")
        return v


class Manifest(_StrictModel):
    version: str = Field(min_length=1)
    distributions: list[Distribution] = Field(min_length=1)

    @field_validator("distributions")
    @classmethod
    def _unique_distribution_names(cls, v: list[Distribution]) -> list[Distribution]:
        names = [d.name for d in v]
        if len(names) != len(set(names)):
            raise ValueError("duplicate distribution names are not allowed")
        return v
