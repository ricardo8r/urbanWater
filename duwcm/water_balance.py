"""
Urban Water Balance Module

This module provides functions to run urban water balance simulations using the
UrbanWaterModel.

The simulation process includes:
1. Initialization of result storage
2. Time-stepping through the simulation period
3. Solving water balance for each cell at each timestep
4. Distributing water between cells (cluster water and stormwater)
5. Aggregating results for each timestep
6. Updating model states
"""

from typing import Dict, List, Optional
from dataclasses import fields

import pandas as pd
import pint
import pint_pandas
from pint import UnitRegistry
from tqdm.auto import trange

from duwcm.water_model import UrbanWaterModel
from duwcm.data_structures import UrbanWaterData, Storage
from duwcm.flow_manager import Flow, MultiSourceFlow
from duwcm.checker import track_validation_results

ureg = pint.UnitRegistry()
pint_pandas.PintType.ureg = ureg

def run_water_balance(model: UrbanWaterModel, forcing: pd.DataFrame, 
                      check: bool = False, process_idx: Optional[int] = None,
                      progress: Optional[bool] = True) -> Dict[str, pd.DataFrame]:
    """
    Run the full simulation for all timesteps with validation tracking.

    Args:
        model: UrbanWaterModel instance
        forcing: DataFrame with forcing data
        check: Enable validation tracking
        process_idx: Process index for parallel runs

    Returns:
        Dict containing:
            - Component results
            - Aggregated results
            - Validation results for balance, flows, and storage
    """


    num_timesteps = len(forcing)

    # Initialize results as dictionaries of lists
    results = {field.name: [] for field in fields(UrbanWaterData)}
    results_agg = []

    # Add initial conditions to results at t=0
    initial_date = forcing.index[0] - pd.Timedelta(days=1)

    # Initialize aggregated results for t=0
    results_agg.append({
        'date': initial_date,
        'stormwater': 0,
        'sewerage': 0,
        'baseflow': 0,
        'total_seepage': 0,
        'imported_water': 0,
        'transpiration': 0,
        'evaporation': 0
    })

    # Initialize validation tracking if check is enabled
    validation_tracking = None
    if check:
        validation_tracking = {
            'balance': [],
            'flows': [],
            'storage': []
        }

    desc = f"Water balance (Scenario {process_idx})" if process_idx is not None else "Water balance"
    iterator = trange(1, num_timesteps, desc=desc, position=process_idx, leave=progress)
    for t in iterator:
        current_date = forcing.index[t]
        timestep_forcing = forcing.iloc[t]

        # Solve timestep
        solve_timestep(model, results, timestep_forcing, current_date)
        model.distribute_sewerage()
        model.distribute_stormwater()
        _aggregate_timestep(model, results_agg, current_date)

        # Track validation for current timestep if enabled
        if check:
            timestep_validation = track_validation_results(model, current_date)
            for key, value in timestep_validation.items():
                validation_tracking[key].append(value)

        model.update_states()

    df_results = results_to_dataframes(results, results_agg, forcing)

    # Process validation results if validation was enabled
    if check and validation_tracking:
        for key, checks in validation_tracking.items():
            df_results[f'validation_{key}'] = pd.concat(checks)

    return df_results

def solve_timestep(model: UrbanWaterModel, results_var: Dict[str, List[Dict]], forcing: pd.Series,
                    current_date: pd.Timestamp) -> None:
    """Solve the water balance for a single timestep for all cells in the specified order."""
    for cell_id in model.cell_order:
        cell_data = model.data[cell_id]

        for component_name, component in cell_data.iter_components():
            component_class = model.classes[cell_id][component_name]
            component_class.solve(forcing)

        for component_name, component in cell_data.iter_components():
            results = _collect_component_results(cell_id, current_date, component)
            results_var[component_name].append(results)

def _collect_component_results(cell_id: int, date: pd.Timestamp, component: object) -> dict:
    """Collect flattened results from a component."""
    results = {
        'cell': cell_id,
        'date': date
    }

    # Add attributes
    for attr_name, attr_value in vars(component).items():
        if not attr_name.startswith('_'):
            if attr_name == 'area':
                results['area'] = attr_value
            elif isinstance(attr_value, Storage):
                # Special handling for groundwater levels and vadose moisture
                if attr_name in ['water_level', 'surface_water_level']:
                    results[attr_name] = attr_value.get_amount('m')
                elif attr_name == 'moisture':
                    results[attr_name] = attr_value.get_amount('mm')
                else:
                    results[attr_name] = attr_value.get_amount('m3')
            #elif isinstance(attr_value, (int, float, bool, str)):
            #    results[attr_name] = attr_value

    if hasattr(component, 'flows'):
        flows = component.flows
        for flow_name, flow in vars(flows).items():
            if isinstance(flow, (Flow, MultiSourceFlow)):
                results[flow_name] = flow.get_amount('m3')

    if hasattr(component, 'internal_flows'):
        internal_flows = component.internal_flows
        for flow_name, flow in vars(internal_flows).items():
            if isinstance(flow, (Flow, MultiSourceFlow)):
                results[flow_name] = flow.get_amount('m3')

    return results

def _aggregate_timestep(model: UrbanWaterModel, results_agg: List[Dict], current_date: pd.Timestamp) -> None:
    """Aggregate results across all cells for the current timestep."""
    aggregated = {
        'date': current_date,
        'stormwater': 0,
        'sewerage': 0,
        'baseflow': 0,
        'total_seepage': 0,
        'imported_water': 0,
        'transpiration': 0,
        'evaporation': 0
    }

    for cell_id, data in model.data.items():
        # Aggregate end-point flows
        if model.path.loc[cell_id, 'down'] == 0:
            aggregated['stormwater'] += data.stormwater.flows.to_downstream.get_amount('m3')
            aggregated['sewerage'] += data.sewerage.flows.to_downstream.get_amount('m3')

        aggregated['baseflow'] += data.groundwater.flows.baseflow.get_amount('m3')
        aggregated['total_seepage'] += data.groundwater.flows.seepage.get_amount('m3')
        aggregated['imported_water'] += data.demand.flows.imported_water.get_amount('m3')

    total_transpiration_area = sum(data.vadose.area for cell_id, data in model.data.items())

    total_transpiration_m3 = sum(
        data.vadose.flows.get_flow('transpiration', 'L')
        for cell_id, data in model.data.items()
    )
    aggregated['transpiration'] = total_transpiration_m3 / total_transpiration_area

    total_evap_area = sum(
        data.roof.area + data.impervious.area + data.pervious.area +
        data.raintank.area + data.stormwater.area
        for cell_id, data in model.data.items()
    )

    total_evap_m3 = sum(
        (data.roof.flows.get_flow('evaporation', 'L') +
         data.impervious.flows.get_flow('evaporation', 'L') +
         data.pervious.flows.get_flow('evaporation', 'L') +
         data.raintank.flows.get_flow('evaporation', 'L') +
         data.stormwater.flows.get_flow('evaporation', 'L'))
        for cell_id, data in model.data.items()
    )

    aggregated['evaporation'] = total_evap_m3 / total_evap_area

    #aggregated['imported_water'] -= sum(model.current[w].sewerage.use for w in model.sewerage_cells)
    #aggregated['imported_water'] -= sum(model.current[s].stormwater.use for s in model.stormwater_cells)

    results_agg.append(aggregated)

def results_to_dataframes(results_var: Dict[str, List[Dict]],
                          results_agg: List[Dict],
                          forcing: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """Convert results dictionaries to DataFrames."""

    dataframe_results = {}

    forcing_units = {
        'precipitation': 'millimeter',
        'potential_evaporation': 'millimeter',
        'open_water_level': 'meter',
        'pervious_irrigation': 'millimeter',
        'impervious_irrigation': 'millimeter',
        'roof_irrigation': 'millimeter'
    }

    # Add this after handling aggregated results but before returning
    forcing_df = forcing.copy()
    for col, unit in forcing_units.items():
        if col in forcing_df.columns:
            forcing_df[col] = forcing_df[col].astype(f"pint[{unit}]")
    dataframe_results['forcing'] = forcing_df

    flow_units = {
        'water_level': 'meter',
        'surface_water_level': 'meter', 
        'moisture': 'millimeter',
        'area': 'meter^2',
        'storage': 'meter^3',
        'imported_water': 'meter^3',
        'seepage': 'meter^3',
        'baseflow': 'meter^3',
        'to_': 'meter^3',
        'from_': 'meter^3',
        'precipitation': 'meter^3',
        'evaporation': 'meter^3',
        'transpiration': 'meter^3',
        'irrigation': 'meter^3',
    }

    for key, values in results_var.items():
        df = pd.DataFrame(values)
        if not df.empty:
            df = df.set_index(['cell', 'date'])

            # Add units to each column using pint-pandas
            for col in df.columns:
                if col == 'area':
                    df[col] = df[col].astype(f"pint[{flow_units['area']}]")
                elif 'storage' in col:
                    df[col] = df[col].astype(f"pint[{flow_units['storage']}]")
                elif any(col.startswith(prefix) for prefix in ['to_', 'from_']):
                    df[col] = df[col].astype(f"pint[{flow_units['to_']}]")
                elif col in flow_units:
                    df[col] = df[col].astype(f"pint[{flow_units[col]}]")

            dataframe_results[key] = df

    # Create aggregated results DataFrame with units
    df_agg = pd.DataFrame(results_agg)
    df_agg = df_agg.set_index('date')

    agg_units = {
        'stormwater': 'meter^3',
        'sewerage': 'meter^3',
        'baseflow': 'meter^3',
        'total_seepage': 'meter^3',
        'imported_water': 'meter^3',
        'transpiration': 'millimeter',
        'evaporation': 'millimeter'
    }

    for col, unit in agg_units.items():
        if col in df_agg.columns:
            df_agg[col] = df_agg[col].astype(f"pint[{unit}]")

    df_agg.attrs['total_area'] = dataframe_results['groundwater']['area'].iloc[0].sum()
    dataframe_results['aggregated'] = df_agg

    return dataframe_results
