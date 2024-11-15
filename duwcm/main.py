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
from duwcm.summary import print_summary
from duwcm.functions import (load_config, check_all, generate_report, export_geodata,
                             generate_plots, generate_maps, generate_chord, generate_sankey, generate_flow_network)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                    datefmt='%H:%M:%S')
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
    logger.info("Simulation period: %s to %s",
            forcing_data.index[0].strftime('%Y-%m-%d'),
            forcing_data.index[-1].strftime('%Y-%m-%d'))

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
    return results, model, forcing_data, flow_paths

def save_results(results: Dict[str, pd.DataFrame], forcing_data: pd.DataFrame,
                 config: Dynaconf) -> None:
    """Save simulation results, model parameters, and forcing data to files."""
    output_dir = Path(config.output.output_directory)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / 'simulation_results.h5'

    with pd.HDFStore(output_file, mode='w') as store:
        for module, df in results.items():
            if module != 'local':
                store.put(module, df, format='table', data_columns=True)

        # Save forcing data
        store.put('forcing', forcing_data, format='table', data_columns=True)

    logger.info("Results and forcing data saved to %s", output_file)

def check_results(model: UrbanWaterModel, config: Dynaconf) -> None:
    """
    Run comprehensive water balance checks and generate reports.

    Args:
        model (UrbanWaterModel): The model instance containing cell data
        config (Dynaconf): Configuration object
    """
    logger.info("Running water balance checks...")

    # Run checks on all cells
    check_balance, critical_issues = check_all(model.data)

    # Generate report
    output_dir = Path(config.output.output_directory) / 'checks'
    generate_report(check_balance, output_dir)

    # Log critical issues
    if critical_issues:
        logger.warning("Critical issues found during water balance checks:")
        for issue in critical_issues:
            logger.warning(issue)
    else:
        logger.info("No critical issues found in water balance checks.")

def main() -> None:
    parser = argparse.ArgumentParser(description="Run Urban Water Model")
    parser.add_argument("--config", required=True, help="Path to the configuration file (YAML, TOML, or JSON)")
    parser.add_argument("--env", default="default", help="Environment to use within the config file")
    parser.add_argument("--plot", action="store_true", help="Generate plots and map plots")
    parser.add_argument("--gis", action="store_true", help="Generate map plots")
    parser.add_argument("--check", action="store_true", help="Check water balance")

    args = parser.parse_args()
    config = load_config(args.config, args.env)

    try:
        # Run simulation
        results, model, forcing_data, flow_paths = run(config)

        # Generate plots
        if args.plot:
            output_dir = Path(config.output.output_directory) / 'figures'
            generate_plots(results['aggregated'],
                           forcing_data,
                           output_dir)
            logger.info("Plots saved to %s", output_dir)

            geo_dir = Path(config.geodata_directory)
            geo_file = Path(config.input_directory) / Path(config.files.geo_file)
            background_shapefile = geo_dir / config.files.background_shapefile
            feature_shapefiles = [geo_dir / shapefile for shapefile in config.files.feature_shapefiles]

            output_dir = Path(config.output.output_directory) / 'maps'
            output_dir.mkdir(parents=True, exist_ok=True)
            generate_maps(
                background_shapefile=background_shapefile,
                feature_shapefiles=feature_shapefiles,
                geometry_geopackage=geo_file,
                local_results=results['local'],
                output_dir=output_dir,
                flow_paths=flow_paths
            )
            logger.info("Maps saved to %s", output_dir)

            # Generate chord diagrams
            output_dir = Path(config.output.output_directory) / 'flows'
            generate_chord(
                results=results,
                output_dir=output_dir
            )
            logger.info("Chord diagrams saved to %s", output_dir)

            # Generate sankey diagrams
            output_dir = Path(config.output.output_directory) / 'flows'
            #generate_sankey(
            #    results=results,
            #    output_dir=output_dir
            #)
            generate_flow_network(results, output_dir)
            logger.info("Sankey diagrams saved to %s", output_dir)

        if args.gis:
            output_dir = Path(config.output.output_directory) / 'gis'
            output_dir.mkdir(parents=True, exist_ok=True)
            export_geodata(
                geometry_geopackage=geo_file,
                local_results=results['local'],
                forcing=forcing_data,
                output_dir=output_dir,
                crs=config.output.crs,
                file_format='gpkg'
            )
            logger.info("Geodata saved to %s", output_dir)

        # Save results
        save_results(results, forcing_data, config)

        # Check results and save water balance
        if args.check:
            check_results(model, config)
            #print_summary(results)


    except Exception as e:
        logger.error("Simulation failed: %s", str(e))
        raise

if __name__ == "__main__":
    main()
