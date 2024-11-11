from typing import Dict
from pathlib import Path
import argparse
import pandas as pd

from duwcm.read_data import read_data
from duwcm.functions import load_results, load_config, plot_results, check_cell, check_all

def plot_global():
    parser = argparse.ArgumentParser(description="Generate aggregated plots from simulation results")
    parser.add_argument("--config", required=True, help="Path to the configuration file")
    parser.add_argument("--env", default="default", help="Environment to use within the config file")
    parser.add_argument("--results", required=True, help="Path to the simulation results file")
    args = parser.parse_args()

    config = load_config(args.config, args.env)
    results = load_results(args.results)
    output_dir = Path(config.output.output_directory) / 'figures'

    plot_results(results['aggregated'], results['forcing'], output_dir)

    print('Aggregated plots saved in %s', output_dir)


def check_water_balance():
    parser = argparse.ArgumentParser(description="Run water balance checks on simulation results")
    parser.add_argument("--config", required=True, help="Path to the configuration file")
    parser.add_argument("--env", default="default", help="Environment to use within the config file")
    parser.add_argument("--results", required=True, help="Path to the simulation results file")
    args = parser.parse_args()

    config = load_config(args.config, args.env)
    results = load_results(args.results)

    # Load parameters
    model_params, _, _, _, _, _ = read_data(config)

    # Load forcing data
    forcing = results.get('forcing')
    if forcing is None:
        raise ValueError("Forcing data not found in the results file. Make sure to save it during simulation.")

    # Run checkers
    global_balance = check_all(results, model_params, forcing)
    cell_balance = check_cell(results, model_params, forcing)

    # Save results to the same HDF5 file
    output_file = Path(config.output.output_directory) / 'simulation_results.h5'

    with pd.HDFStore(output_file, mode='a') as store:
        # Save overall water balance
        store.put('global_water_balance', global_balance, format='table', data_columns=True)

        # Save cell-wise water balance
        store.put('cell_water_balance', cell_balance, format='table', data_columns=True)

    print(f"Water balance checks completed and saved to {output_file}")

    # Log some summary statistics
    print("\nOverall water balance summary:")
    print(f"Total inflow: {global_balance['inflow'].sum():.2f}")
    print(f"Total outflow: {global_balance['outflow'].sum():.2f}")
    print(f"Total storage change: {global_balance['storage_change'].sum():.2f}")
    print(f"Final water balance: {global_balance['water_balance_1'].iloc[-1]:.2f}")

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
