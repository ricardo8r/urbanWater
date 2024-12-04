from typing import Dict
from pathlib import Path
import pandas as pd
from dynaconf import Dynaconf

def load_results(results_file: Path) -> Dict[str, pd.DataFrame]:
    results_file = Path(results_file)
    if not results_file.is_file():
        raise FileNotFoundError(f"Results file not found: {results_file}")

    results = {}
    with pd.HDFStore(results_file, mode='r') as store:
        for key in store.keys():
            results[key.strip('/')] = store.select(key)
    return results

def load_config(config_path: str, env: str = "default") -> Dynaconf:

    base_dir = Path(config_path)
    settings_files = [
        base_dir / "config.toml",
        base_dir / "water_config.toml"
    ]
    config = Dynaconf(
        settings_files=settings_files,
        environments=True,
        env=env,
        load_dotenv=True,
        merge_enabled=True
    )

    return config