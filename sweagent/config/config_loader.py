from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from sweagent import CONFIG_DIR
from sweagent.config.schema import validate_config_schema


class ConfigLoader:
    """Load YAML configs with inheritance and list append semantics."""

    def __init__(self, base_dir: Path | None = None):
        self.base_dir = Path(base_dir) if base_dir else CONFIG_DIR

    def load_config(self, config_path: str | Path) -> dict[str, Any]:
        """Load a config file, applying inheritance and validation."""
        resolved_path = self._resolve_path(config_path)
        merged = self._load_with_inheritance(resolved_path, stack=set())
        self._validate_config(merged)
        return merged

    def load_from_dict(self, config: dict[str, Any]) -> dict[str, Any]:
        """Load a config from an in-memory mapping, applying inheritance rules."""
        if not isinstance(config, dict):
            msg = "config must be a mapping"
            raise ValueError(msg)
        sentinel_path = (self.base_dir / "__generated__.yaml").resolve()
        merged = self._load_dict_with_inheritance(config, sentinel_path, stack=set())
        self._validate_config(merged)
        return merged

    def _load_with_inheritance(self, path: Path, stack: set[Path]) -> dict[str, Any]:
        normalized_path = path.resolve()
        if normalized_path in stack:
            msg = f"Circular config inheritance detected: {normalized_path}"
            raise ValueError(msg)
        stack.add(normalized_path)

        config = self._load_yaml(normalized_path)
        local_config = deepcopy(config)
        extends_value = local_config.pop("extends", None)

        if extends_value is None:
            stack.remove(normalized_path)
            return local_config

        base_configs = self._resolve_extends(extends_value, normalized_path, stack)
        merged_base = {}
        for parent_config in base_configs:
            merged_base = self._deep_merge(merged_base, parent_config)
        merged = self._deep_merge(merged_base, local_config)
        stack.remove(normalized_path)
        return merged

    def _load_dict_with_inheritance(
        self,
        config: dict[str, Any],
        current_path: Path,
        stack: set[Path],
    ) -> dict[str, Any]:
        normalized_path = current_path.resolve()
        if normalized_path in stack:
            msg = f"Circular config inheritance detected for generated config: {normalized_path}"
            raise ValueError(msg)
        stack.add(normalized_path)

        local_config = deepcopy(config)
        extends_value = local_config.pop("extends", None)

        if extends_value is None:
            stack.remove(normalized_path)
            return local_config

        base_configs = self._resolve_extends(extends_value, current_path, stack)
        merged_base = {}
        for parent_config in base_configs:
            merged_base = self._deep_merge(merged_base, parent_config)
        merged = self._deep_merge(merged_base, local_config)
        stack.remove(normalized_path)
        return merged

    def _resolve_extends(
        self, extends_value: Any, current_path: Path, stack: set[Path]
    ) -> list[dict[str, Any]]:
        if isinstance(extends_value, (str, Path)):
            extends_list = [extends_value]
        elif isinstance(extends_value, list):
            extends_list = extends_value
        else:
            msg = "extends must be a string, Path, or list of those"
            raise ValueError(msg)

        resolved_configs: list[dict[str, Any]] = []
        for entry in extends_list:
            if not isinstance(entry, (str, Path)):
                msg = "extends list entries must be strings or Paths"
                raise ValueError(msg)
            base_path = self._resolve_path(entry, relative_to=current_path)
            resolved_configs.append(self._load_with_inheritance(base_path, stack))
        return resolved_configs

    def _resolve_path(self, config_path: str | Path, *, relative_to: Path | None = None) -> Path:
        candidate = Path(config_path)
        if candidate.is_absolute():
            return candidate
        if relative_to is not None:
            return (relative_to.parent / candidate).resolve()

        cwd_candidate = (Path.cwd() / candidate)
        if cwd_candidate.exists():
            return cwd_candidate.resolve()
        base_candidate = (self.base_dir / candidate)
        if base_candidate.exists():
            return base_candidate.resolve()
        return candidate.resolve()

    def _load_yaml(self, path: Path) -> dict[str, Any]:
        text = path.read_text()
        if not text.strip():
            return {}
        data = yaml.safe_load(text)
        if data is None:
            return {}
        if not isinstance(data, dict):
            msg = f"Config file must contain a mapping at the top level: {path}"
            raise ValueError(msg)
        return data

    def _deep_merge(self, base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        merged = deepcopy(base)
        for key, value in override.items():
            if key not in merged:
                merged[key] = deepcopy(value)
                continue
            if isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = self._deep_merge(merged[key], value)
            elif isinstance(merged[key], list) and isinstance(value, list):
                merged[key] = self._merge_lists(merged[key], value)
            else:
                merged[key] = deepcopy(value)
        return merged

    def _merge_lists(self, base: list[Any], override: list[Any]) -> list[Any]:
        base_copy = deepcopy(base)
        replacements: list[Any] = []
        append_items: list[Any] = []

        for item in override:
            normalized, should_append = self._normalize_list_item(item)
            if should_append:
                append_items.append(normalized)
            else:
                replacements.append(normalized)

        if replacements:
            result = replacements
        else:
            result = base_copy
        result.extend(append_items)
        return result

    def _normalize_list_item(self, item: Any) -> tuple[Any, bool]:
        if isinstance(item, str) and item.startswith("+"):
            return item[1:], True
        if isinstance(item, dict):
            append_detected = False
            normalized = {}
            for key, value in item.items():
                if isinstance(key, str) and key.startswith("+"):
                    append_detected = True
                    normalized[key[1:]] = value
                else:
                    normalized[key] = value
            return normalized, append_detected
        return item, False

    def _validate_config(self, config: dict[str, Any]) -> None:
        if not isinstance(config, dict):
            msg = "Merged config must be a mapping"
            raise ValueError(msg)
        if "extends" in config:
            msg = "extends directive must not remain after merging"
            raise ValueError(msg)
        validate_config_schema(config)
