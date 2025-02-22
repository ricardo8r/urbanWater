from pathlib import Path
from typing import Dict
import pandas as pd

from duwcm.postprocess.flow_matrix import calculate_flow_matrix

def write_summary(results: Dict[str, pd.DataFrame], flow_paths: pd.DataFrame,
                  output_file: Path) -> None:
    """
    Generate a summary of total water balance components using results data.

    Args:
        results (Dict[str, pd.DataFrame]): Dictionary containing simulation results
        output_file (Path): Path to save the summary file

    Returns:
        None
    """

    flow_matrix = calculate_flow_matrix(results, flow_paths)

    # Write summary to file
    with open(output_file, 'w', encoding="utf8") as f:
        f.write("=" * 50 + "\n\n")
        f.write("Water Balance Summary\n")
        f.write("=" * 50 + "\n\n")

        if 'precipitation' in flow_matrix.index:
            total_precip = flow_matrix.loc['precipitation'].sum()
            f.write(f"{'Total Precipitation':22s}: {total_precip:,.2f} m³\n")

        if 'imported' in flow_matrix.index:
            total_imported = flow_matrix.loc['imported'].sum()
            f.write(f"{'Total Imported Water':22s}: {total_imported:,.2f} m³\n")

        if 'evaporation' in flow_matrix.columns:
            total_evap = flow_matrix[['evaporation']].sum().sum()
            f.write(f"{'Total Evaporation':22s}: {total_evap:,.2f} m³\n")

        if 'seepage' in flow_matrix.columns:
            total_seep = flow_matrix[['seepage']].sum().sum()
            f.write(f"{'Total Seepage':22s}: {total_seep:,.2f} m³\n")

        if 'baseflow' in flow_matrix.columns:
            total_base = flow_matrix[['baseflow']].sum().sum()
            f.write(f"{'Total Baseflow':22s}: {total_base:,.2f} m³\n")

        # Add after previous totals
        if 'runoff' in flow_matrix.columns:
            total_runoff = flow_matrix[['runoff']].sum().sum()
            f.write(f"{'Total Runoff':22s}: {total_runoff:,.2f} m³\n")

        if 'discharge' in flow_matrix.columns:
            total_discharge = flow_matrix[['discharge']].sum().sum()
            f.write(f"{'Total Discharge':22s}: {total_discharge:,.2f} m³\n")


        f.write("\nWater Balance Check\n")
        f.write("-" * 25 + "\n")
        total_in = 0
        if 'precipitation' in flow_matrix.index:
            total_in += flow_matrix.loc['precipitation'].sum()
        if 'imported' in flow_matrix.index:
            total_in += flow_matrix.loc['imported'].sum()
        f.write(f"{'Total Input':22s}: {total_in:,.2f} m³\n")

        total_out = 0
        for col in ['evaporation', 'seepage', 'baseflow', 'runoff', 'discharge']:
            if col in flow_matrix.columns:
                total_out += flow_matrix[[col]].sum().sum()
        f.write(f"{'Total Output':22s}: {total_out:,.2f} m³\n")


        f.write("\n\n\n")
        f.write("=" * 50 + "\n\n")
        f.write("Water Balance Details\n")
        f.write("=" * 50 + "\n\n")

        # Write precipitation breakdown
        f.write("\nPrecipitation Breakdown\n")
        f.write("-" * 25 + "\n")
        for comp in ['roof', 'impervious', 'pervious', 'raintank', 'stormwater']:
            if 'precipitation' in results[comp].columns:
                precip = results[comp]['precipitation'].pint.to('meter^3')
                f.write(f"{comp:22s}: {precip.sum():,.2f~P}\n")

        # Write evaporation breakdown
        f.write("\nEvaporation Breakdown\n")
        f.write("-" * 25 + "\n")
        for comp in ['roof', 'impervious', 'pervious', 'raintank', 'stormwater']:
            if 'evaporation' in results[comp].columns:
                evap = results[comp]['evaporation'].pint.to('meter^3')
                f.write(f"{comp:22s}: {evap.sum():,.2f~P}\n")

        # Write irrigation breakdown
        f.write("\nIrrigation Breakdown\n")
        f.write("-" * 25 + "\n")
        for comp in ['roof', 'impervious', 'pervious']:
            if 'from_demand' in results[comp].columns:
                irrig = results[comp]['from_demand'].pint.to('meter^3')
                f.write(f"{comp:22s}: {irrig.sum():,.2f~P}\n")

        # Write storage changes breakdown
        f.write("\nStorage Changes Breakdown\n")
        f.write("-" * 25 + "\n")
        for comp in ['roof', 'raintank', 'impervious', 'pervious',
                     'stormwater', 'sewerage', 'vadose']:
            change = results[comp]['storage_change'].sum()
            f.write(f"{comp:22s}: {change:,.2f~P}\n")

        storage = (results['groundwater']['storage_change'] *
                   results['groundwater']['storage_coefficient']).sum()
        f.write(f"{'groundwater':22s}: {storage:,.2f~P}\n")


        f.write("\n")
        level = results['vadose'].groupby('cell')['moisture'].agg(lambda x: x.iloc[-1] - x.iloc[0]).mean()
        f.write(f"{'Vadose avg moisture':22s}: {level:,.2f~P}\n")

        level = results['groundwater'].groupby('cell')['water_level'].agg(lambda x: x.iloc[-1] - x.iloc[0]).mean()
        f.write(f"{'Groundwater avg level':22s}: {level:,.2f~P}\n")
