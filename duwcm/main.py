from typing import Dict, List, Tuple, Any
import logging
from pathlib import Path
import argparse
import pandas as pd
from dynaconf import Dynaconf

from duwcm.water_model import UrbanWaterModel
from duwcm.read_data import read_data
from duwcm.forcing import read_forcing, distribute_irrigation
from duwcm.water_balance import run_simulation

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_urban_water_balance(config: Dynaconf) -> Tuple[Dict[str, pd.DataFrame], List[Dict[str, Any]], pd.DataFrame]:
    """
    Run the urban water balance simulation.

    Args:
        config (Dynaconf): Configuration object

    Returns:
        Tuple[Dict[str, pd.DataFrame], List[Dict[str, Any]], pd.DataFrame]: 
            - Dictionary of DataFrames with results for each module
            - List of parameter dictionaries for each grid cell
            - DataFrame of forcing data
    """
    logger.info("Starting urban water balance simulation")

    # Read and process input data
    logger.info("Preparing model parameters")
    model_params, reuse_settings, demand_data, soil_data, et_data, flow_paths = read_data(config)

    logger.info("Reading forcing data")
    forcing_data = read_forcing(config)

    logger.info("Distributing irrigation")
    distribute_irrigation(forcing_data, model_params)

    # Initialize model
    logger.info("Initializing water balance model")
    model = UrbanWaterModel(model_params, flow_paths, soil_data, et_data, demand_data,
                            reuse_settings, config.grid.direction)

    # Run simulation
    logger.info("Running water balance simulation")
    results = run_simulation(model, forcing_data)

    logger.info("Simulation completed successfully")
    return results, model_params, forcing_data

def save_results(results: Dict[str, pd.DataFrame], config: Dynaconf) -> None:
    """Save simulation results to files."""
    output_dir = Path(config.output.output_directory)
    output_dir.mkdir(parents=True, exist_ok=True)

    for module, df in results.items():
        df.to_csv(output_dir / f"{module}_results.csv")

    logger.info("Results saved to %s", output_dir)

def main() -> None:
    parser = argparse.ArgumentParser(description="Run Urban Water Model")
    parser.add_argument("--config", required=True, help="Path to the configuration file (YAML, TOML, or JSON)")
    parser.add_argument("--env", default="default", help="Environment to use within the config file")

    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.is_file():
        raise FileNotFoundError(f"Config file not found: {args.config}")

    # Load configuration
    config = Dynaconf(
        settings_files=[config_path],
        environments=True,
        env=args.env,
        load_dotenv=True,
    )

    try:
        # Run simulation
        results, model_params, forcing_data = run_urban_water_balance(config)

        # Save results
        save_results(results, config)

        logger.info("Simulation and result saving completed successfully")
        logger.info("Number of grid cells: %d", len(model_params))
        logger.info("Simulation period: %s to %s", forcing_data.index[0], forcing_data.index[-1])

    except Exception as e:
        logger.error("Simulation failed: %s", str(e))
        raise

if __name__ == "__main__":
    main()
