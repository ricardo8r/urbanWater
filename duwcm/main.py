from typing import Dict, List, Tuple, Any
from pathlib import Path
import argparse
import logging
from joblib import Parallel, delayed
import pandas as pd

from duwcm.read_data import read_data
from duwcm.forcing import read_forcing
from duwcm.scenario_manager import ScenarioManager, run_scenario

from duwcm.initialization import initialize_model
from duwcm.summary import write_summary
from duwcm.utils import load_config
from duwcm.functions import select_cells
from duwcm.diagnostics import DiagnosticTracker, alert, generate_alluvial_cells
from duwcm.plots import (export_geodata, generate_plots, generate_maps,
                         generate_system_maps, generate_chord, generate_graph,
                         generate_alluvial_total, generate_alluvial_reuse
                         )

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

    if args.check and not args.scenarios:
        logger.info("Diagnostic checks enabled")
        tracker = DiagnosticTracker()
    else:
        if args.check:
            logger.warning("Diagnostic checks not available when running scenarios")
            args.check = False
        tracker = None

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
            n_jobs=args.n_jobs
        )

        Parallel(n_jobs=args.n_jobs, backend='loky', verbose=0)(
            delayed(process_outputs)(
                results,
                tracker,
                flow_paths,
                Path(base_config.output.directory) / case_name,
                base_config,
                args
            )
            for case_name, results in all_results.items()
        )

    else:
        # Single base case
        scenario_data = (args.env, model_params, forcing_data, {
            'flow_paths': flow_paths,
            'soil_data': soil_data,
            'et_data': et_data,
            'demand_data': demand_data,
            'reuse_settings': reuse_settings,
            'direction': base_config.grid.direction
        }, tracker, None, True)
        _, results = run_scenario(scenario_data)

        out_base = Path(base_config.output.directory) / args.env
        process_outputs(results, tracker, flow_paths, out_base, base_config, args)

    logger.info("Simulation completed")


def process_outputs(results, tracker, flow_paths, output_dir, config, args):
    """Process and save outputs based on arguments"""

    output_dir.mkdir(parents=True, exist_ok=True)
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

        # Generate flow diagrams
        generate_chord(
            results = results,
            flow_paths = flow_paths,
            output_dir=flow_dir
        )
        generate_graph(
            results = results,
            flow_paths = flow_paths,
            output_dir=flow_dir
        )
        generate_alluvial_total(
            results = results,
            flow_paths = flow_paths,
            output_dir=flow_dir
        )
        generate_alluvial_reuse(
            results = results,
            output_dir=flow_dir
        )
        logger.info("Plots saved to %s", output_dir)

    if args.gis:
        gis_dir = output_dir / 'gis'
        gis_dir.mkdir(parents=True, exist_ok=True)
        geo_file = Path(config.input_directory) / Path(config.files.geo)
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
        check_dir = output_dir / 'diagnostic'
        check_dir.mkdir(parents=True, exist_ok=True)
        tracker.generate_report(check_dir)
        alert(tracker)

        selected_cells = getattr(config.grid, 'selected_cells', None)
        if selected_cells is not None:
            generate_alluvial_cells(
                flow_paths = flow_paths,
                selected_cells = selected_cells,
                output_dir=check_dir,
                tracker=tracker
            )

        logger.info("Diagnostic reports saved to %s", check_dir)
        #print_summary(results)

    if args.save:
        save_dir = output_dir / 'simulation_results.h5'

        with pd.HDFStore(save_dir, mode='w') as store:
            for module, df in results.items():
                units_dict = {col: str(df[col].pint.units) for col in df.columns if hasattr(df[col], "pint")}

                # Convert Pint DataFrame to a regular Pandas DataFrame
                df_regular = df.copy()
                for col in units_dict.keys():
                    df_regular[col] = df[col].pint.magnitude

                # Save DataFrame to HDF5
                store.put(module, df_regular, format='table', data_columns=True)
                if units_dict:
                    store.get_storer(module).attrs.units = units_dict

        logger.info("Results and forcing data saved to %s", save_dir)

    summary_dir = output_dir / 'summary.txt'
    write_summary(results, flow_paths, summary_dir)

if __name__ == "__main__":
    main()
