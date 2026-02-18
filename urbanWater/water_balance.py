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
import numpy as np
from tqdm.auto import trange

from urbanWater.water_model import UrbanWaterModel
from urbanWater.data_structures import UrbanWaterData, Storage
from urbanWater.flow_manager import Flow, MultiSourceFlow
from urbanWater.diagnostics import DiagnosticTracker

def run_water_balance(model: UrbanWaterModel, forcing: pd.DataFrame,
                      tracker: Optional[DiagnosticTracker] = None,
                      process_idx: Optional[int] = None,
                      progress: Optional[bool] = True) -> Dict[str, pd.DataFrame]:
    """
    Run the full simulation for all timesteps with diagnostic tracking.

    Args:
        model: UrbanWaterModel instance
        forcing: DataFrame with forcing data
        check: Enable diagnostic tracking
        process_idx: Process index for parallel runs

    Returns:
        Dict containing:
            - Component results
            - Aggregated results
            - Diagnostic results for balance, flows, and storage
    """

    num_timesteps = len(forcing)

    results_schemas: Dict[str, List[str]] = {}
    results_arrays: Dict[str, np.ndarray] = {}

    cell_ids = list(model.cell_order)
    n_cells = len(cell_ids)
    n_rows = max(0, (num_timesteps - 1) * n_cells)

    results_agg = []
    initial_date = forcing.index[0] - pd.Timedelta(days=1)

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

    desc = f"Water balance (Scenario {process_idx})" if process_idx is not None else "Water balance"
    iterator = trange(1, num_timesteps, desc=desc, position=process_idx, leave=False, disable=not progress)

    for t in iterator:
        current_date = forcing.index[t]
        timestep_forcing = forcing.iloc[t]

        solve_timestep(model, results_schemas, results_arrays, n_rows, t, n_cells, timestep_forcing, current_date)
        model.distribute_sewerage()
        model.distribute_stormwater()
        _aggregate_timestep(model, results_agg, current_date)

        if tracker is not None:
            tracker.track_diagnostic_results(model, current_date)

        model.update_states()

    df_results = results_to_dataframes(results_schemas, results_arrays,
                                     forcing.index[1:], cell_ids,
                                     results_agg, forcing)
    return df_results

def solve_timestep(model: UrbanWaterModel,
                   results_schemas: Dict[str, List[str]],
                   results_arrays: Dict[str, np.ndarray],
                   n_rows: int,
                   timestep_idx: int, # 1-based index from loop
                   n_cells: int,
                   forcing: pd.Series,
                   current_date: pd.Timestamp) -> None:
    """
    Solve the water balance for a single timestep using a dual-pass approach.
    Pass 1: Runoff components (using runoff topology)
    Pass 2: Sewerage components (using sewerage topology)
    """

    # Pass 1: Solve runoff-related components using runoff order
    runoff_components = ['demand', 'roof', 'raintank', 'impervious', 
                        'pervious', 'vadose', 'groundwater', 'stormwater']
    
    for cell_id in model.runoff_order:
        for comp_name in runoff_components:
            if comp_name in model.classes[cell_id]:
                model.classes[cell_id][comp_name].solve(forcing)

    # Pass 2: Solve sewerage components using sewerage order
    for cell_id in model.sewerage_order:
        if 'sewerage' in model.classes[cell_id]:
            model.classes[cell_id]['sewerage'].solve(forcing)

    # Results Collection (iterate over registered cell order)
    base_row_idx = (timestep_idx - 1) * n_cells

    for cell_idx, cell_id in enumerate(model.cell_order):
        cell_data = model.data[cell_id]
        row_idx = base_row_idx + cell_idx

        # Collect results from all components
        for component_name, component in cell_data.iter_components():
            if component_name not in results_schemas:
                schema = _discover_component_schema(component)
                results_schemas[component_name] = schema
                results_arrays[component_name] = np.zeros((n_rows, len(schema)), dtype=np.float64)

            # Write directly to array
            _collect_component_results_into_array(
                component,
                results_arrays[component_name],
                row_idx,
                results_schemas[component_name]
            )

def _discover_component_schema(component: object) -> List[str]:
    """Discover column names from component attributes."""
    schema = []

    # Add attributes
    for attr_name, attr_value in vars(component).items():
        if not attr_name.startswith('_'):
            if attr_name in {'vadose_moisture', 'groundwater_level', 'rt_storage'}:
                continue
            schema.append(attr_name)

    # Explicitly ensure storage_change is present if not already
    if 'storage_change' not in schema:
        schema.append('storage_change')

    if hasattr(component, 'flows'):
        flows = component.flows
        for flow_name, flow in vars(flows).items():
            if isinstance(flow, (Flow, MultiSourceFlow)):
                schema.append(flow_name)

    if hasattr(component, 'internal_flows'):
        internal_flows = component.internal_flows
        for flow_name, flow in vars(internal_flows).items():
            if isinstance(flow, (Flow, MultiSourceFlow)):
                schema.append(flow_name)

    return schema

def _collect_component_results_into_array(component: object,
                                        array: np.ndarray,
                                        row_idx: int,
                                        schema: List[str]) -> None:
    """Collect results directly into pre-allocated array row."""

    current_values = {}
    current_storage_change = 0.0

    # 1. Attributes
    for attr_name, attr_value in vars(component).items():
        if not attr_name.startswith('_'):
            if attr_name in {'vadose_moisture', 'groundwater_level', 'rt_storage'}:
                continue

            if attr_name == 'area':
                current_values[attr_name] = attr_value
            elif attr_name == 'storage_coefficient':
                current_values[attr_name] = attr_value
            elif isinstance(attr_value, Storage):
                if attr_name == 'water_level':
                    current_values[attr_name] = -1 * attr_value.get_amount('m')
                    current_storage_change += -1 * attr_value.get_change('m3')
                elif attr_name == 'surface_water_level':
                    current_values[attr_name] = -1 * attr_value.get_amount('m')
                    current_storage_change += -1 * attr_value.get_change('m3')
                elif attr_name == 'moisture':
                    current_values[attr_name] = attr_value.get_amount('mm')
                    current_storage_change = attr_value.get_change('m3')
                else:
                    current_values[attr_name] = attr_value.get_amount('m3')
                    current_storage_change = attr_value.get_change('m3')

    current_values['storage_change'] = current_storage_change

    # 2. Flows
    if hasattr(component, 'flows'):
        for flow_name, flow in vars(component.flows).items():
            if isinstance(flow, (Flow, MultiSourceFlow)):
                current_values[flow_name] = flow.get_amount('m3')

    # 3. Internal Flows
    if hasattr(component, 'internal_flows'):
        for flow_name, flow in vars(component.internal_flows).items():
            if isinstance(flow, (Flow, MultiSourceFlow)):
                current_values[flow_name] = flow.get_amount('m3')

    # 4. Write to array
    for i, col_name in enumerate(schema):
        array[row_idx, i] = current_values.get(col_name, 0.0)

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
        if model.runoff_path.loc[cell_id, 'down'] == 0:
            aggregated['stormwater'] += data.stormwater.flows.to_downstream.get_amount('m3')
        
        if model.sewerage_path.loc[cell_id, 'down'] == 0:
            aggregated['sewerage'] += data.sewerage.flows.to_downstream.get_amount('m3')

        aggregated['baseflow'] += data.groundwater.flows.baseflow.get_amount('m3')
        aggregated['total_seepage'] += data.groundwater.flows.seepage.get_amount('m3')
        aggregated['imported_water'] += data.demand.flows.imported_water.get_amount('m3')

    total_transpiration_area = sum(data.vadose.area for cell_id, data in model.data.items())

    if total_transpiration_area > 0:
        total_transpiration_m3 = sum(
            data.vadose.flows.get_flow('transpiration', 'L')
            for cell_id, data in model.data.items()
        )
        aggregated['transpiration'] = total_transpiration_m3 / total_transpiration_area
    else:
        aggregated['transpiration'] = 0.0

    total_evap_area = sum(
        data.roof.area + data.impervious.area + data.pervious.area +
        data.raintank.area + data.stormwater.area
        for cell_id, data in model.data.items()
    )

    if total_evap_area > 0:
        total_evap_m3 = sum(
            (data.roof.flows.get_flow('evaporation', 'L') +
             data.impervious.flows.get_flow('evaporation', 'L') +
             data.pervious.flows.get_flow('evaporation', 'L') +
             data.raintank.flows.get_flow('evaporation', 'L') +
             data.stormwater.flows.get_flow('evaporation', 'L'))
            for cell_id, data in model.data.items()
        )
        aggregated['evaporation'] = total_evap_m3 / total_evap_area
    else:
        aggregated['evaporation'] = 0.0

    results_agg.append(aggregated)

def results_to_dataframes(results_schemas: Dict[str, List[str]],
                          results_arrays: Dict[str, np.ndarray],
                          dates: pd.DatetimeIndex,
                          cell_ids: List[int],
                          results_agg: List[Dict],
                          forcing: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """Convert results arrays to DataFrames."""

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
        'storage_change': 'meter^3',
        'storage_coefficient': '',
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

    # Create MultiIndex once for all components
    if len(dates) > 0 and len(cell_ids) > 0:
        multi_index = pd.MultiIndex.from_product([dates, cell_ids], names=['date', 'cell'])
    else:
        multi_index = pd.Index([])

    for key, array in results_arrays.items():
        schema = results_schemas[key]

        # Check if empty
        if array.size == 0:
            # Create empty DF with correct columns
            header_index = pd.MultiIndex.from_product([[], []], names=['cell', 'date'])
            df = pd.DataFrame(columns=schema, index=header_index)
        else:
            df = pd.DataFrame(array, index=multi_index, columns=schema)
            # Reorder levels to (cell, date) and sort to match original output structure
            df = df.swaplevel('date', 'cell').sort_index()

        # Add units to each column using pint-pandas
        for col in df.columns:
            if col == 'area':
                df[col] = df[col].astype(f"pint[{flow_units['area']}]")
            elif any(col.startswith(prefix) for prefix in ['to_', 'from_']):
                df[col] = df[col].astype(f"pint[{flow_units['to_']}]")
            elif col in flow_units:
                df[col] = df[col].astype(f"pint[{flow_units[col]}]")

        dataframe_results[key] = df

    # Create aggregated results DataFrame with units
    df_agg = pd.DataFrame(results_agg)
    if not df_agg.empty and 'date' in df_agg.columns:
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

    # Calculate total area for metadata
    if 'groundwater' in dataframe_results and not dataframe_results['groundwater'].empty:
        try:
             # Just grab area from the first date in the index
            sample_date = dataframe_results['groundwater'].index.get_level_values('date')[0]
            total_area = dataframe_results['groundwater'].xs(sample_date, level='date')['area'].sum()
            df_agg.attrs['total_area'] = total_area
        except (IndexError, KeyError):
            df_agg.attrs['total_area'] = 0.0

    dataframe_results['aggregated'] = df_agg

    return dataframe_results
