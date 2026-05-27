import os
import re
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class ProviderConfig:
    type: str
    api_key: str = ""
    base_url: str = ""


@dataclass
class AIConfig:
    default_provider: str
    providers: dict[str, ProviderConfig]
    models: dict[str, list[str]]
    defaults: dict[str, dict]


def _resolve_env_vars(obj):
    """Recursively resolve ${VAR_NAME} in all string values within nested dicts/lists."""
    if isinstance(obj, str):
        return re.sub(r'\$\{(\w+)\}', lambda m: os.environ.get(m.group(1), ''), obj)
    if isinstance(obj, dict):
        return {k: _resolve_env_vars(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_env_vars(item) for item in obj]
    return obj


def load_config(path: str) -> AIConfig:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    raw_text = p.read_text(encoding='utf-8')
    raw = yaml.safe_load(raw_text)
    raw = _resolve_env_vars(raw)

    providers = {k: ProviderConfig(**v) for k, v in raw.get('providers', {}).items()}
    return AIConfig(
        default_provider=raw.get('default_provider', ''),
        providers=providers,
        models=raw.get('models', {}),
        defaults=raw.get('defaults', {}),
    )
