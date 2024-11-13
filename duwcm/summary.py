from pathlib import Path
from typing import Dict
import pandas as pd

def print_summary(results: Dict[str, pd.DataFrame]) -> None:
    """
    Generate a summary of total water balance components using only results data.

    Args:
        results (Dict[str, pd.DataFrame]): Dictionary containing simulation results

    Returns:
        pd.DataFrame: Summary of water balance components
    """
    total_area = results['aggregated'].attrs['total_area']
    agg = results['aggregated']

    # Calculate total volumes in m³
    summary = pd.Series({
        # Inputs
        'Precipitation': sum(results[comp]['precipitation'].sum() 
                           for comp in ['roof', 'pavement', 'pervious', 'raintank', 'stormwater']
                           if 'precipitation' in results[comp].columns) * 0.001,
        'Imported Water': agg['imported_water'].sum() * 0.001,
        'Irrigation': sum(results[comp]['irrigation'].sum()
                          for comp in ['roof', 'pavement', 'pervious']
                          if 'irrigation' in results[comp].columns) * 0.001,

        # Outputs
        'Evaporation': agg['evaporation'].sum() * 0.001,
        'Transpiration': agg['transpiration'].sum() * 0.001,
        'Deep Seepage': agg['total_seepage'].sum() * 0.001,
        'Baseflow': agg['baseflow'].sum() * 0.001,
        'Stormwater': agg['stormwater'].sum() * 0.001,
        'Wastewater': agg['wastewater'].sum() * 0.001
    })

    # Calculate totals
    total_in = summary[['Precipitation', 'Imported Water', 'Irrigation']].sum()
    total_out = summary[['Evaporation', 'Transpiration', 'Deep Seepage',
                        'Baseflow', 'Stormwater', 'Wastewater']].sum()
    balance = total_in - total_out

    # Add totals to summary
    summary['Total Input'] = total_in
    summary['Total Output'] = total_out
    summary['Balance'] = balance

    # Create nicely formatted output
    print("\nWater Balance Summary (m³):")
    print("=" * 50)
    print("\nInputs:")
    print("-" * 20)
    for comp in ['Precipitation', 'Imported Water', 'Irrigation']:
        print(f"{comp:20s}: {summary[comp]:,.2f}")
    print(f"{'Total Input':20s}: {total_in:,.2f}")

    print("\nOutputs:")
    print("-" * 20)
    for comp in ['Evaporation', 'Transpiration', 'Deep Seepage',
                 'Baseflow', 'Stormwater', 'Wastewater']:
        print(f"{comp:20s}: {summary[comp]:,.2f}")
    print(f"{'Total Output':20s}: {total_out:,.2f}")

    print("\nBalance:")
    print("-" * 20)
    print(f"{'Water Balance':20s}: {balance:,.2f}")
    print(f"{'Balance Error %':20s}: {(balance/total_in)*100:,.2f}")

    # Print breakdown of precipitation by component
    print("\nPrecipitation Breakdown:")
    print("-" * 20)
    for comp in ['roof', 'pavement', 'pervious', 'raintank', 'stormwater']:
        if 'precipitation' in results[comp].columns:
            precip = results[comp]['precipitation'].sum() * 0.001
            print(f"{comp:20s}: {precip:,.2f}")

    # Print breakdown of evaporation by component
    print("\nEvaporation Breakdown:")
    print("-" * 20)
    for comp in ['roof', 'pavement', 'pervious', 'raintank', 'stormwater']:
        if 'evaporation' in results[comp].columns:
            evap = results[comp]['evaporation'].sum() * 0.001
            print(f"{comp:20s}: {evap:,.2f}")

    # Print breakdown of irrigation by component
    print("\nIrrigation Breakdown:")
    print("-" * 20)
    for comp in ['roof', 'pavement', 'pervious']:
        if 'irrigation' in results[comp].columns:
            irrig = results[comp]['irrigation'].sum() * 0.001
            print(f"{comp:20s}: {irrig:,.2f}")
