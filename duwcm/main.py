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
from duwcm.initialization import initialize_model
from duwcm.summary import print_summary
from duwcm.functions import load_config
from duwcm.checker import generate_report
from duwcm.plots import (export_geodata, generate_plots, generate_maps, generate_system_maps,
                         generate_chord, generate_alluvial, generate_graph)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                    datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)

def run(config: Dynaconf, check: bool = False) -> Tuple[Dict[str, pd.DataFrame], List[Dict[str, Any]], pd.DataFrame]:
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
    if check:
        logger.info("Validation checks enabled")


    # Read and process input data
    logger.info("Preparing model parameters")
    model_params, reuse_settings, demand_data, soil_data, et_data, flow_paths = read_data(config)

    # Filter for selected cells if specified
    selected_cells = getattr(config.grid, 'selected_cells', None)
    if selected_cells is not None:
        # Filter model parameters
        model_params = {k: v for k, v in model_params.items() if k in selected_cells}

        # Filter flow paths and reset upstream connections for non-selected cells
        flow_paths = flow_paths.loc[flow_paths.index.isin(selected_cells)].copy()
        # Reset upstream connections that aren't in selected cells
        for col in flow_paths.columns:
            if col != 'down':  # Don't modify downstream connections
                flow_paths[col] = flow_paths[col].apply(lambda x: x if x in selected_cells else 0)

        # Ensure downstream connections are valid
        flow_paths['down'] = flow_paths['down'].apply(lambda x: x if x in selected_cells else 0)


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

    #logger.info("Initializing groundwater using %s method", config.simulation.init_method)
    #initialize_model(model, forcing_data, config)

    # Run simulation
    logger.info("Running water balance simulation")
    results = run_water_balance(model, forcing_data, check=check)

    logger.info("Simulation completed")
    return results, forcing_data, flow_paths

def check_results(results: Dict[str, pd.DataFrame], check_dir: Path) -> None:
    """Process and report validation results."""
    validation_keys = ['validation_balance', 'validation_flows', 'validation_storage']

    if not any(key in results for key in validation_keys):
        logger.warning("No validation results found")
        return

    validation_results = {
        'balance': results.get('validation_balance', pd.DataFrame()),
        'flows': results.get('validation_flows', pd.DataFrame()),
        'storage': results.get('validation_storage', pd.DataFrame())
    }

    if all(df.empty for df in validation_results.values()):
        logger.warning("All validation DataFrames are empty")
        return

    # Log warnings for each type of issue
    balance_df = validation_results['balance']
    if not balance_df.empty:
        significant_mask = abs(balance_df['balance_error_percent']) > 1.0
        if significant_mask.any():
            logger.warning("Found %d significant balance errors", len(balance_df[significant_mask]))

    flows_df = validation_results['flows']
    if not flows_df.empty:
        logger.warning("Found %d flow validation issues", len(flows_df))
        by_type = flows_df.groupby('issue_type').size()
        for issue_type, count in by_type.items():
            logger.warning("  %s: %d issues", issue_type, count)

    storage_df = validation_results['storage']
    if not storage_df.empty:
        logger.warning("Found %d storage validation issues", len(storage_df))
        by_component = storage_df.groupby(['component', 'issue_type']).size()
        for (comp, issue_type), count in by_component.items():
            logger.warning("  %s - %s: %d issues", comp, issue_type, count)

    # Generate validation reports
    generate_report(validation_results, check_dir)

def main() -> None:
    parser = argparse.ArgumentParser(description="Run Urban Water Model")
    parser.add_argument("--config", required=True, help="Path to the configuration files (YAML, TOML, or JSON)")
    parser.add_argument("--env", default="default", help="Environment to use within the config file")
    parser.add_argument("--plot", action="store_true", help="Generate plots and map plots")
    parser.add_argument("--gis", action="store_true", help="Generate map plots")
    parser.add_argument("--check", action="store_true", help="Check water balance")
    parser.add_argument("--scenarios", action="store_true", help="Run multiple scenarios defined in config")
    parser.add_argument("--save", action="store_true", help="Save results")

    args = parser.parse_args()
    base_config = load_config(args.config, args.env)
    scenarios = base_config.get('simulation', {}).get('scenarios', ['default']) if args.scenarios else ['default']

    for scenario in scenarios:
        logger.info("Running %s scenario...", scenario)
        config = load_config(args.config, env=scenario)
        out_base = Path(config.output.output_directory) / scenario
        results, forcing_data, flow_paths = run(config, check=args.check)

        # Generate plots
        if args.plot:
            plot_dir = out_base / 'figures'
            map_dir = out_base / 'maps'
            flow_dir = out_base / 'flows'
            for directory in [plot_dir, map_dir, flow_dir]:
                directory.mkdir(parents=True, exist_ok=True)

            generate_plots(results['aggregated'],
                           forcing_data,
                           plot_dir)
            logger.info("Plots saved to %s", plot_dir)

            geo_dir = Path(config.geodata_directory)
            geo_file = Path(config.input_directory) / Path(config.files.geo_file)
            background_shapefile = geo_dir / config.files.background_shapefile
            feature_shapefiles = [geo_dir / shapefile for shapefile in config.files.feature_shapefiles]

            generate_system_maps(
                background_shapefile = background_shapefile,
                feature_shapefiles = feature_shapefiles,
                geometry_geopackage = geo_file,
                output_dir = map_dir,
                flow_paths = flow_paths,
                config = config
                )
            generate_maps(
                background_shapefile = background_shapefile,
                feature_shapefiles = feature_shapefiles,
                geometry_geopackage = geo_file,
                results = results,
                output_dir = map_dir,
                flow_paths = flow_paths
            )

            logger.info("Maps saved to %s", map_dir)

            # Generate chord diagrams
            generate_chord(
                results=results,
                output_dir=flow_dir
            )
            # Generate sankey diagrams
            generate_alluvial(
                results=results,
                output_dir=flow_dir
            )
            generate_graph(
                results=results,
                output_dir=flow_dir
            )
            logger.info("Flow diagrams saved to %s", flow_dir)

        if args.gis:
            gis_dir = out_base / 'gis'
            gis_dir.mkdir(parents=True, exist_ok=True)
            export_geodata(
                geometry_geopackage = geo_file,
                results = results,
                forcing = forcing_data,
                output_dir = gis_dir,
                crs = config.output.crs,
                file_format = 'gpkg'
            )
            logger.info("Geodata saved to %s", gis_dir)

        # Check results and save water balance
        if args.check:
            check_dir = out_base / 'validation'
            check_dir.mkdir(parents=True, exist_ok=True)
            check_results(results, check_dir)
            logger.info("Validation reports saved to %s", check_dir)
            #print_summary(results)

        if args.save:
            save_dir = out_base / 'simulation_results.h5'

            with pd.HDFStore(save_dir, mode='w') as store:
                for module, df in results.items():
                    store.put(module, df, format='table', data_columns=True)
                store.put('forcing', forcing_data, format='table', data_columns=True)

            logger.info("Results and forcing data saved to %s", save_dir)

if __name__ == "__main__":
    main()
