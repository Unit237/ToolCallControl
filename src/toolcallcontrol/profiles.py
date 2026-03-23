"""Load and dump profile configs for sharing (JSON files, CI, or a team registry)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .model import ProfileConfig


def profile_to_json(config: ProfileConfig, *, indent: int | None = 2) -> str:
    """Serialize a profile to a JSON string."""
    return json.dumps(config.to_dict(), indent=indent, sort_keys=True)


def profile_from_json(data: str) -> ProfileConfig:
    """Parse a JSON string from :func:`profile_to_json` or an equivalent object."""
    obj = json.loads(data)
    if not isinstance(obj, dict):
        raise TypeError("profile JSON must be an object")
    return ProfileConfig.from_dict(obj)


def load_profile_file(path: str | Path) -> ProfileConfig:
    """Load a single profile from a ``.json`` file."""
    p = Path(path)
    raw = p.read_text(encoding="utf-8")
    return profile_from_json(raw)


def dump_profile_file(config: ProfileConfig, path: str | Path, *, indent: int | None = 2) -> None:
    """Write a profile to a ``.json`` file (UTF-8)."""
    Path(path).write_text(profile_to_json(config, indent=indent) + "\n", encoding="utf-8")


def load_profile_bundle(data: str) -> dict[str, ProfileConfig]:
    """
    Load a bundle: ``{"profiles": { "name": { ... }, ... } }``.

    Useful for one file checked into a repo that defines many named profiles.
    """
    obj: Any = json.loads(data)
    if not isinstance(obj, dict) or "profiles" not in obj:
        raise ValueError('bundle must be a JSON object with a "profiles" key')
    raw_profiles = obj["profiles"]
    if not isinstance(raw_profiles, dict):
        raise TypeError('"profiles" must be an object')
    out: dict[str, ProfileConfig] = {}
    for name, cfg in raw_profiles.items():
        if not isinstance(cfg, dict):
            raise TypeError(f"profile {name!r} must be an object")
        cfg2 = dict(cfg)
        cfg2.setdefault("name", str(name))
        pc = ProfileConfig.from_dict(cfg2)
        out[pc.name] = pc
    return out


def dump_profile_bundle(
    profiles: dict[str, ProfileConfig],
    *,
    indent: int | None = 2,
) -> str:
    """Serialize multiple profiles to ``{"profiles": {...}}`` JSON."""
    return json.dumps(
        {"profiles": {k: v.to_dict() for k, v in sorted(profiles.items())}},
        indent=indent,
        sort_keys=True,
    )
