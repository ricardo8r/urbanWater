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

def load_config(config_file: str, env: str = "default") -> Dynaconf:
    config_file = Path(config_file)
    if not config_file.is_file():
        raise FileNotFoundError(f"Config file not found: {config_file}")

    config = Dynaconf(
        settings_files=[config_file],
        environments=True,
        env=env,
        load_dotenv=True,
    )

    return config