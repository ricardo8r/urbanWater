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

    # Calculate storage changes for each component
    surface_storage_changes = 0.0
    for component in ['roof', 'raintank', 'pavement', 'pervious', 'stormwater', 'wastewater']:
        if component in results:
            if 'storage' in results[component].columns:
                initial_storage = results[component]['storage'].iloc[0]
                final_storage = results[component]['storage'].iloc[-1]
                change = (final_storage - initial_storage) * 0.001  # Convert to m³
                surface_storage_changes += change

    # Calculate vadose storage change with correct area
    vadose_storage_change = 0.0
    if 'vadose' in results:
        initial_moisture = results['vadose']['moisture'].iloc[0]
        final_moisture = results['vadose']['moisture'].iloc[-1]
        vadose_area = results['vadose']['area'].iloc[0]  # Get vadose area
        vadose_storage_change = (final_moisture - initial_moisture) * vadose_area * 0.001

    # Calculate groundwater storage change with correct area
    groundwater_storage_change = 0.0
    if 'groundwater' in results:
        initial_gw = (results['groundwater']['water_level'].iloc[0] +
                     results['groundwater']['surface_water_level'].iloc[0])
        final_gw = (results['groundwater']['water_level'].iloc[-1] +
                   results['groundwater']['surface_water_level'].iloc[-1])
        gw_area = results['groundwater']['area'].iloc[0]  # Get groundwater area
        groundwater_storage_change = (initial_gw - final_gw) * gw_area

    # Total storage change
    storage_changes = surface_storage_changes + vadose_storage_change + groundwater_storage_change

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
        'Wastewater': agg['wastewater'].sum() * 0.001,
        'Storage Change': storage_changes
    })

    # Calculate totals
    total_in = summary[['Precipitation', 'Imported Water', 'Irrigation']].sum()
    total_out = summary[['Evaporation', 'Transpiration', 'Deep Seepage',
                        'Baseflow', 'Stormwater', 'Wastewater']].sum() + storage_changes
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
    print(f"{'Storage Change':20s}: {storage_changes:,.2f}")
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

    # Print breakdown of storage changes
    print("\nStorage Changes Breakdown:")
    print("-" * 20)
    print(f"{'Surface Storage':20s}: {surface_storage_changes:,.2f}")
    for comp in ['roof', 'raintank', 'pavement', 'pervious', 'stormwater', 'wastewater']:
        if comp in results and 'storage' in results[comp].columns:
            initial_storage = results[comp]['storage'].iloc[0]
            final_storage = results[comp]['storage'].iloc[-1]
            change = (final_storage - initial_storage) * 0.001
            print(f"{comp:20s}: {change:,.2f}")
    print(f"{'Vadose Storage':20s}: {vadose_storage_change:,.2f}")
    print(f"{'Groundwater Storage':20s}: {groundwater_storage_change:,.2f}")
    print(f"{'Total Storage Change':20s}: {storage_changes:,.2f}")
