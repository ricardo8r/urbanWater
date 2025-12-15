import argparse
from pathlib import Path
import pandas as pd
from duwcm.utils import load_results, load_config

def save_cell():
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
