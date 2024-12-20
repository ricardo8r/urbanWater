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
from duwcm.plots import (export_geodata, generate_plots, generate_maps,
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
    return results, model, forcing_data, flow_paths

def save_results(results: Dict[str, pd.DataFrame], forcing_data: pd.DataFrame,
                 config: Dynaconf) -> None:
    """Save simulation results, model parameters, and forcing data to files."""
    output_dir = Path(config.output.output_directory)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / 'simulation_results.h5'

    with pd.HDFStore(output_file, mode='w') as store:
        for module, df in results.items():
            store.put(module, df, format='table', data_columns=True)

        # Save forcing data
        store.put('forcing', forcing_data, format='table', data_columns=True)

    logger.info("Results and forcing data saved to %s", output_file)

def check_results(results: Dict[str, pd.DataFrame], config: Dynaconf) -> None:
    """
    Process and report validation results.

    Args:
        results: Dictionary containing simulation results including validation
        config: Configuration object with output settings
    """

    logger.info("Processing validation results...")

    # These keys match exactly what we create in water_balance.py
    validation_keys = ['validation_balance', 'validation_flows', 'validation_storage']

    # Check if we have validation results
    if not any(key in results for key in validation_keys):
        logger.warning("No validation results found in simulation output")
        return

    # Extract validation results using the exact keys
    validation_results = {
        'balance': results.get('validation_balance', pd.DataFrame()),
        'flows': results.get('validation_flows', pd.DataFrame()),
        'storage': results.get('validation_storage', pd.DataFrame())
    }

    # Only proceed if we have actual validation data
    if all(df.empty for df in validation_results.values()):
        logger.warning("All validation DataFrames are empty")
        return

    # Log validation summary
    balance_df = validation_results['balance']
    if not balance_df.empty:
        # Create a view with significant issues and absolute error
        significant_mask = abs(balance_df['balance_error_percent']) > 1.0
        if significant_mask.any():
            significant_issues = balance_df[significant_mask].copy()  # Create explicit copy
            logger.warning("Found %d significant balance errors", len(significant_issues))

            # Get worst issues by absolute error
            worst_indices = abs(significant_issues['balance_error_percent']).nlargest(15).index
            worst_issues = significant_issues.loc[worst_indices]

            for _, issue in worst_issues.iterrows():
                logger.warning(
                    "Cell %d at %s, Component %s: Error %.2f%% (Balance: %.2f, Inflow: %.2f, "
                    "Outflow: %.2f, Storage Change: %.2f)",
                    issue['cell'],
                    issue['timestep'].strftime('%Y-%m-%d'),
                    issue['component'],
                    issue['balance_error_percent'],
                    issue['balance'],
                    issue['inflow'],
                    issue['outflow'],
                    issue['storage_change']
                )

            # Log statistics about the balance errors
            logger.warning(
                "Balance error stats - Mean: %.2f%%, Max: %.2f%%, Min: %.2f%%",
                significant_issues['balance_error_percent'].mean(),
                significant_issues['balance_error_percent'].max(),
                significant_issues['balance_error_percent'].min()
            )

    flows_df = validation_results['flows']
    if not flows_df.empty:
        flow_issues = len(flows_df)
        if flow_issues > 0:
            logger.warning("Found %d flow validation issues", flow_issues)
            # Group issues by type
            by_type = flows_df.groupby('issue_type').size()
            for issue_type, count in by_type.items():
                logger.warning("  %s: %d issues", issue_type, count)
            # Show some example issues
            for _, issue in flows_df.head(3).iterrows():
                logger.warning(
                    "  %s->%s: %s",
                    issue['source_component'],
                    issue['target_component'],
                    issue['description']
                )

    storage_df = validation_results['storage']
    if not storage_df.empty:
        storage_issues = len(storage_df)
        if storage_issues > 0:
            logger.warning("Found %d storage validation issues", storage_issues)
            # Group issues by component and type
            by_component = storage_df.groupby(['component', 'issue_type']).size()
            for (comp, issue_type), count in by_component.items():
                logger.warning("  %s - %s: %d issues", comp, issue_type, count)
            # Show some example violations
            for _, issue in storage_df.head(3).iterrows():
                logger.warning(
                    "  %s %s: Current value: %.2f, Limit: %.2f",
                    issue['component'],
                    issue['storage_name'],
                    issue['current_value'],
                    issue['limit_value']
                )

    # Generate validation reports
    output_dir = Path(config.output.output_directory) / 'validation'
    output_dir.mkdir(parents=True, exist_ok=True)

    generate_report(validation_results, output_dir)
    logger.info("Validation reports generated in %s", output_dir)

    # Calculate total issues
    total_issues = (
        len(significant_issues) if 'significant_issues' in locals() else 0 +
        flow_issues if 'flow_issues' in locals() else 0 +
        storage_issues if 'storage_issues' in locals() else 0
    )

    if total_issues > 0:
        logger.warning(
            "Total validation issues found: %d. "
            "Check the validation reports in %s for detailed information.",
            total_issues,
            output_dir
        )

def main() -> None:
    parser = argparse.ArgumentParser(description="Run Urban Water Model")
    parser.add_argument("--config", required=True, help="Path to the configuration files (YAML, TOML, or JSON)")
    parser.add_argument("--env", default="default", help="Environment to use within the config file")
    parser.add_argument("--plot", action="store_true", help="Generate plots and map plots")
    parser.add_argument("--gis", action="store_true", help="Generate map plots")
    parser.add_argument("--check", action="store_true", help="Check water balance")

    args = parser.parse_args()
    config = load_config(args.config, args.env)

    try:
        # Run simulation
        results, model, forcing_data, flow_paths = run(config, check=args.check)

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
                results=results,
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
            generate_alluvial(
                results=results,
                output_dir=output_dir
            )
            logger.info("Alluvial diagrams saved to %s", output_dir)
            generate_graph(
                results=results,
                output_dir=output_dir
            )
            logger.info("Network diagrams saved to %s", output_dir)

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

        # Check results and save water balance
        if args.check:
            check_results(results, config)
            #print_summary(results)

        # Save results
        save_results(results, forcing_data, config)


    except Exception as e:
        logger.error("Simulation failed: %s", str(e))
        raise

if __name__ == "__main__":
    main()
