from typing import Dict, List, Tuple, Any
import logging
from pathlib import Path
import argparse
import pandas as pd
from dynaconf import Dynaconf

from duwcm.water_model import UrbanWaterModel
from duwcm.read_data import read_data
from duwcm.forcing import read_forcing, distribute_irrigation
from duwcm.water_balance import run_water_balance
from duwcm.functions import (load_config, check_all, check_cell,
                             plot_results, export_gpkg, map_plot)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run(config: Dynaconf) -> Tuple[Dict[str, pd.DataFrame], List[Dict[str, Any]], pd.DataFrame]:
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
    logger.info("Number of grid cells: %d", len(model_params))
    logger.info("Simulation period: %s to %s", forcing_data.index[0], forcing_data.index[-1])

    logger.info("Distributing irrigation")
    distribute_irrigation(forcing_data, model_params)

    # Initialize model
    logger.info("Initializing water balance model")
    model = UrbanWaterModel(model_params, flow_paths, soil_data, et_data, demand_data,
                            reuse_settings, config.grid.direction)

    # Run simulation
    logger.info("Running water balance simulation")
    results = run_water_balance(model, forcing_data)

    logger.info("Simulation completed")
    return results, model_params, forcing_data, flow_paths

def save_results(results: Dict[str, pd.DataFrame], forcing_data: pd.DataFrame,
                 config: Dynaconf) -> None:
    """Save simulation results, model parameters, and forcing data to files."""
    output_dir = Path(config.output.output_directory)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / 'simulation_results.h5'

    with pd.HDFStore(output_file, mode='w') as store:
        # Save results
        for module, df in results.items():
            store.put(module, df, format='table', data_columns=True)

        # Save forcing data
        store.put('forcing', forcing_data, format='table', data_columns=True)

    logger.info("Results and forcing data saved to %s", output_file)

def check_results(results: Dict[str, pd.DataFrame], params: Dict[int, Dict[str, Dict[str, float]]],
                  forcing: pd.DataFrame, config: Dynaconf) -> None:

    overall_balance = check_all(results, params, forcing).infer_objects()
    cell_balance = check_cell(results, params, forcing).infer_objects()
    output_file = Path(config.output.output_directory) / 'check_results.h5'

    with pd.HDFStore(output_file, mode='w') as store:
        store.put('global_water_balance', overall_balance, format='table', data_columns=True)
        store.put('cell_water_balance', cell_balance, format='table', data_columns=True)

    logger.info("Water balance checks saved to %s", output_file)

    # Log some summary statistics
    logger.info("Overall water balance summary:")
    logger.info("Total inflow: %.2f", overall_balance['inflow'].sum())
    logger.info("Total outflow: %.2f", overall_balance['outflow'].sum())
    logger.info("Total storage change: %.2f", overall_balance['storage_change'].sum())
    logger.info("Final water balance: %.2f", overall_balance['water_balance_1'].iloc[-1])


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Urban Water Model")
    parser.add_argument("--config", required=True, help="Path to the configuration file (YAML, TOML, or JSON)")
    parser.add_argument("--env", default="default", help="Environment to use within the config file")
    parser.add_argument("--plot", action="store_true", help="Generate plots of global variables")
    parser.add_argument("--gis", action="store_true", help="Generate map plots")
    parser.add_argument("--check", action="store_true", help="Check water balance")

    args = parser.parse_args()
    config = load_config(args.config, args.env)

    try:
        # Run simulation
        results, model_params, forcing_data, flow_paths = run(config)

        # Save results
        save_results(results, forcing_data, config)

        # Generate plots if requested
        if args.plot:
            logger.info("Generating plots of aggregated results")
            output_dir = Path(config.output.output_directory) / 'figures'
            plot_results(results['aggregated'],
                                    forcing_data,
                                    output_dir)
            logger.info("Plots saved to %s", output_dir)

            output_dir = Path(config.output.output_directory) / 'maps'
            output_dir.mkdir(parents=True, exist_ok=True)
            geo_dir = Path(config.geodata_directory)
            geo_file = Path(config.input_directory) / Path(config.files.geo_file)
            background_shapefile = geo_dir / config.files.background_shapefile
            feature_shapefiles = [geo_dir / shapefile for shapefile in config.files.feature_shapefiles]

            map_plot(
                background_shapefile=background_shapefile,
                feature_shapefiles=feature_shapefiles,
                geometry_geopackage=geo_file,
                results=results,
                params=model_params,
                output_dir=output_dir,
                flow_paths=flow_paths
            )
            logger.info("Maps saved to %s", output_dir)

        if args.gis:
            output_dir = Path(config.output.output_directory) / 'gis'
            output_dir.mkdir(parents=True, exist_ok=True)
            export_gpkg(
                geometry_geopackage=geo_file,
                results=results,
                params=model_params,
                forcing=forcing_data,
                output_dir=output_dir,
                crs=config.output.crs
            )
            logger.info("Geopackage saved to %s", output_dir)


        # Check results and save water balance
        if args.check:
            check_results(results, model_params, forcing_data, config)

    except Exception as e:
        logger.error("Simulation failed: %s", str(e))
        raise

if __name__ == "__main__":
    main()
