import argparse
from pathlib import Path
import pandas as pd
from duwcm.read_data import read_data
from duwcm.functions import load_results, load_config
from duwcm.plots import (generate_plots, generate_maps, generate_chord,
                        generate_alluvial, generate_graph)

def plot_all():
    parser = argparse.ArgumentParser(description="Generate plots from simulation results")
    parser.add_argument("--config", required=True, help="Path to the configuration file")
    parser.add_argument("--env", default="default", help="Environment to use within the config file")
    parser.add_argument("--results", required=True, help="Path to the simulation results file")
    args = parser.parse_args()

    config = load_config(args.config, args.env)
    results = load_results(args.results)
    total_area = results['groundwater']['area'].iloc[0].sum()
    results['aggregated'].attrs['total_area'] = total_area

    # Prepare output directories
    out_base = Path(config.output.output_directory)
    plot_dir = out_base / 'figures'
    map_dir = out_base / 'maps'
    flow_dir = out_base / 'flows'
    for directory in [plot_dir, map_dir, flow_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    # Generate time series plots
    generate_plots(results['aggregated'], results['forcing'], plot_dir)

    # Generate maps
    geo_dir = Path(config.geodata_directory)
    geo_file = Path(config.input_directory) / Path(config.files.geo_file)
    background_shapefile = geo_dir / config.files.background_shapefile
    feature_shapefiles = [geo_dir / shapefile for shapefile in config.files.feature_shapefiles]

    _, _, _, _, _, flow_paths = read_data(config)
    generate_maps(background_shapefile, feature_shapefiles, geo_file,
                 results['local'], map_dir, flow_paths)

    # Generate flow visualizations
    generate_chord(results, flow_dir)
    generate_alluvial(results, flow_dir)
    generate_graph(results, flow_dir)

    print(f'All visualization outputs saved in {out_base}')

def save_specific_cell_results():
    parser = argparse.ArgumentParser(description="Save results for a specific cell ID")
    parser.add_argument("--config", required=True, help="Path to the configuration file")
    parser.add_argument("--env", default="default", help="Environment to use within the config file")
    parser.add_argument("--results", required=True, help="Path to the simulation results file")
    parser.add_argument("--cell_id", type=int, required=True, help="ID of the cell to extract results for")
    args = parser.parse_args()

    config = load_config(args.config, args.env)
    results = load_results(args.results)
    output_dir = Path(config.output.output_directory) / 'point'

    cell_data = {}

    for module, df in results.items():
        if module == 'forcing':
            continue
        if module == 'aggregated':
            continue

        if isinstance(df.index, pd.MultiIndex):
            try:
                cell_df = df.xs(args.cell_id, level='cell')
                for column in cell_df.columns:
                    cell_data[f"{module}_{column}"] = cell_df[column]
            except KeyError:
                print(f"Warning: Cell ID {args.cell_id} not found in module '{module}'. Skipping.")
        else:
            print(f"Warning: Module '{module}' does not have a MultiIndex structure. Skipping.")

    if not cell_data:
        print(f"No data found for cell ID {args.cell_id}")
        return

    cell_results = pd.DataFrame(cell_data)

    # Ensure the output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save to CSV
    output_file = output_dir / f"cell_{args.cell_id}_results.csv"
    cell_results.to_csv(output_file)
    print(f"Results for cell {args.cell_id} saved in {output_file}")
