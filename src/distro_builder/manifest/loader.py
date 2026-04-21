from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from distro_builder.manifest.models import Manifest


class ManifestLoadError(Exception):
    pass


_YAML_SUFFIXES = frozenset({".yaml", ".yml"})
_JSON_SUFFIXES = frozenset({".json"})


def _parse(path: Path) -> Any:
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8")
    if suffix in _YAML_SUFFIXES:
        try:
            return yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise ManifestLoadError(f"invalid YAML in {path}: {exc}") from exc
    if suffix in _JSON_SUFFIXES:
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ManifestLoadError(f"invalid JSON in {path}: {exc}") from exc
    raise ManifestLoadError(
        f"unsupported manifest extension {suffix!r}; expected one of "
        f"{sorted(_YAML_SUFFIXES | _JSON_SUFFIXES)}"
    )


def load_manifest(path: Path | str) -> Manifest:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"manifest not found: {p}")
    data = _parse(p)
    if not isinstance(data, dict):
        raise ManifestLoadError(f"manifest root must be a mapping, got {type(data).__name__}")
    try:
        return Manifest.model_validate(data)
    except ValidationError as exc:
        raise ManifestLoadError(f"manifest validation failed for {p}:\n{exc}") from exc
