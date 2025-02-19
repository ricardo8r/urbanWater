import argparse
from pathlib import Path
from duwcm.read_data import read_data
from duwcm.utils import load_results, load_config
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
    generate_maps(background_shapefile, feature_shapefiles, 
                  geo_file, results, map_dir, flow_paths)

    # Generate flow visualizations
    generate_chord(results, flow_dir)
    generate_alluvial(results, flow_dir)
    generate_graph(results, flow_dir)

    print(f'All visualization outputs saved in {out_base}')