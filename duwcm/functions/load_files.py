from typing import Dict
from pathlib import Path
import pandas as pd
from dynaconf import Dynaconf
import yaml

def load_results(results_file: Path) -> Dict[str, pd.DataFrame]:
    results_file = Path(results_file)
    if not results_file.is_file():
        raise FileNotFoundError(f"Results file not found: {results_file}")

    results = {}
    with pd.HDFStore(results_file, mode='r') as store:
        for key in store.keys():
            results[key.strip('/')] = store.select(key)
    return results

def load_config(config_path: str | Path, env: str = "default", base_config: str = "config.yaml") -> Dynaconf:
    """
    Load configuration from YAML file with optional environment selection.

    Args:
        config_path: Path to configuration directory
        env: Environment name in the YAML file
        base_config: Name of base config file

    Returns:
        Dynaconf: Configuration object with loaded settings
    """
    base_dir = Path(config_path)

    with open(base_dir / base_config, 'r', encoding='utf-8') as f:
        yaml_config = yaml.safe_load(f)

    # If the env exists in the base config, use it
    if env in yaml_config:
        base_settings = yaml_config.get("default", {})
        env_settings = yaml_config.get(env, {})
        _deep_merge(base_settings, env_settings)
        yaml_config = base_settings

    return Dynaconf(settings_files=False, env=env, **yaml_config)

def _deep_merge(base: dict, update: dict) -> None:
    """
    Recursively merge two dictionaries, modifying the base dictionary.

    Args:
        base: Base dictionary to update
        update: Dictionary with values to merge
    """
    for key, value in update.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value