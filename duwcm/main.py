from typing import Dict, List, Tuple, Any
from pathlib import Path
import argparse

import logging
import pandas as pd

from duwcm.read_data import read_data
from duwcm.forcing import read_forcing
from duwcm.scenario_manager import ScenarioManager, run_scenario

from duwcm.initialization import initialize_model
from duwcm.summary import print_summary
from duwcm.functions import load_config, select_cells
from duwcm.checker import generate_report
from duwcm.plots import (export_geodata, generate_plots, generate_maps, generate_system_maps,
                         generate_chord, generate_alluvial, generate_graph)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                    datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)

def main() -> None:
    parser = argparse.ArgumentParser(description="Run Urban Water Model")
    parser.add_argument("--config", required=True, help="Path to the configuration files")
    parser.add_argument("--env", default="default", help="Environment to use within the config file")
    parser.add_argument("--plot", action="store_true", help="Generate plots and map plots")
    parser.add_argument("--gis", action="store_true", help="Generate map plots")
    parser.add_argument("--check", action="store_true", help="Check water balance")
    parser.add_argument("--scenarios", action="store_true", help="Run multiple scenarios")
    parser.add_argument("--save", action="store_true", help="Save results")
    parser.add_argument("--n-jobs", type=int, default=-1, help="Number of parallel jobs")
    args = parser.parse_args()

    logger.info("Distributed Urban Water Balance Model")
    if args.check:
        logger.info("Validation checks enabled")

    # Load base config and data
    base_config = load_config(args.config, args.env, "config.yaml")
    model_params, reuse_settings, demand_data, soil_data, et_data, flow_paths = read_data(base_config)
    forcing_data = read_forcing(base_config)
    logger.info("Number of grid cells: %d", len(model_params))
    logger.info("Simulation period: %s to %s",
             forcing_data.index[0].strftime('%Y-%m-%d'),
             forcing_data.index[-1].strftime('%Y-%m-%d'))

    # Filter selected cells if specified
    selected_cells = getattr(base_config.grid, 'selected_cells', None)
    if selected_cells is not None:
        model_params, flow_paths = select_cells(model_params, flow_paths, selected_cells)
        logger.info("Filtered to %d selected cells", len(model_params))

    if args.scenarios:
        # Load base and scenario configs separately
        scenario_config = load_config(args.config, args.env, "scenarios.yaml")

        scenario_manager = ScenarioManager.from_config(scenario_config)

        # Create shared data dict
        model_data = {
            'flow_paths': flow_paths,
            'soil_data': soil_data,
            'et_data': et_data,
            'demand_data': demand_data,
            'reuse_settings': reuse_settings,
            'direction': base_config.grid.direction
        }

        # Run all cases
        all_results = scenario_manager.run_scenarios(
            model_data=model_data,
            base_params=model_params,
            base_forcing=forcing_data,
            n_jobs=args.n_jobs,
            check=args.check
        )

        for case_name, results in all_results.items():
            out_base = Path(base_config.output.directory) / case_name
            process_outputs(results, flow_paths, out_base, base_config, args)

    else:
        # Single base case
        scenario_data = (args.env, model_params, forcing_data, {
            'flow_paths': flow_paths,
            'soil_data': soil_data,
            'et_data': et_data,
            'demand_data': demand_data,
            'reuse_settings': reuse_settings,
            'direction': base_config.grid.direction
        }, args.check, None, True)
        _, results = run_scenario(scenario_data)

        out_base = Path(base_config.output.directory) / args.env
        process_outputs(results, flow_paths, out_base, base_config, args)

    logger.info("Simulation completed")


def process_outputs(results, flow_paths, output_dir, config, args):
    """Process and save outputs based on arguments"""

    # Generate plots
    if args.plot:
        plot_dir = output_dir / 'figures'
        map_dir = output_dir / 'maps'
        flow_dir = output_dir / 'flows'
        for directory in [plot_dir, map_dir, flow_dir]:
            directory.mkdir(parents=True, exist_ok=True)

        generate_plots(results['aggregated'],
                       results['forcing'],
                       plot_dir)

        geo_dir = Path(config.geodata_directory)
        geo_file = Path(config.input_directory) / Path(config.files.geo)
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

        # Generate chord diagrams
        generate_chord(
            results = results,
            output_dir=flow_dir
        )
        # Generate sankey diagrams
        generate_alluvial(
            results = results,
            output_dir=flow_dir
        )
        generate_graph(
            results = results,
            output_dir=flow_dir
        )
        logger.info("Plots saved to %s", output_dir)

    if args.gis:
        gis_dir = output_dir / 'gis'
        gis_dir.mkdir(parents=True, exist_ok=True)
        export_geodata(
            geometry_geopackage = geo_file,
            results = results,
            forcing = results['forcing'],
            output_dir = gis_dir,
            crs = config.output.crs,
            file_format = 'gpkg'
        )
        logger.info("Geodata saved to %s", gis_dir)

    # Check results and save water balance
    if args.check:
        check_dir = output_dir / 'validation'
        check_dir.mkdir(parents=True, exist_ok=True)
        check_results(results, check_dir)
        logger.info("Validation reports saved to %s", check_dir)
        #print_summary(results)

    if args.save:
        save_dir = output_dir / 'simulation_results.h5'

        with pd.HDFStore(save_dir, mode='w') as store:
            for module, df in results.items():
                store.put(module, df, format='table', data_columns=True)
            store.put('forcing', results['forcing'], format='table', data_columns=True)

        logger.info("Results and forcing data saved to %s", save_dir)

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

if __name__ == "__main__":
    main()
