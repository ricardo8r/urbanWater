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

from typing import Dict, List
from dataclasses import fields
import pandas as pd
from tqdm import tqdm

from duwcm.water_model import UrbanWaterModel
from duwcm.data_structures import UrbanWaterData, Storage
from duwcm.flow_manager import Flow, MultiSourceFlow
from duwcm.checker import track_validation_results

def run_water_balance(model: UrbanWaterModel, forcing: pd.DataFrame, check: bool = False) -> Dict[str, pd.DataFrame]:
    """
    Run the full simulation for all timesteps with validation tracking.

    Args:
        model: UrbanWaterModel instance
        forcing: DataFrame with forcing data

    Returns:
        Dict containing:
            - Component results
            - Aggregated results
            - Local results
            - Validation results for balance, flows, and storage
    """
    num_timesteps = len(forcing)

    # Initialize results as dictionaries of lists
    results = {field.name: [] for field in fields(UrbanWaterData)}
    results_agg = []

    # Add initial conditions to results at t=0
    initial_date = forcing.index[0] - pd.Timedelta(days=1)
    for cell_id, data in model.data.items():
        for component_name, component in data.iter_components():
            results[component_name].append(
                _collect_component_results(cell_id, initial_date, component)
            )

    # Initialize aggregated results for t=0
    results_agg.append({
        'date': initial_date,
        'stormwater': 0,
        'wastewater': 0,
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

    for t in tqdm(range(1, num_timesteps), desc="Water balance"):
        current_date = forcing.index[t]
        timestep_forcing = forcing.iloc[t]

        # Solve timestep
        _solve_timestep(model, results, timestep_forcing, current_date)
        model.distribute_wastewater()
        model.distribute_stormwater()
        _aggregate_timestep(model, results_agg, current_date)

        # Track validation for current timestep if enabled
        if check:
            timestep_validation = track_validation_results(model, current_date)
            for key, value in timestep_validation.items():
                validation_tracking[key].append(value)

        model.update_states()

    df_results = results_to_dataframes(results, results_agg)

    # Process validation results if validation was enabled
    if check and validation_tracking:
        for key, checks in validation_tracking.items():
            df_results[f'validation_{key}'] = pd.concat(checks)

    return df_results

def _solve_timestep(model: UrbanWaterModel, results_var: Dict[str, List[Dict]], forcing: pd.Series,
                    current_date: pd.Timestamp) -> None:
    """Solve the water balance for a single timestep for all cells in the specified order."""
    for cell_id in model.cell_order:
        cell_data = model.data[cell_id]
        for component_name, component in cell_data.iter_components():
            component_class = model.classes[cell_id][component_name]
            component_class.solve(forcing)
            results = _collect_component_results(cell_id, current_date, component)
            results_var[component_name].append(results)

#        if cell_id == 33:  # Debug for specific cell
#            groundwater = cell_data.groundwater
#            print("\nAfter solving:")
#            flows = groundwater.flows
#            for attr_name, attr_value in vars(flows).items():
#                if isinstance(attr_value, (Flow, MultiSourceFlow)):
#                    print(f"  {attr_name}: {flows.get_flow(attr_name):.6f}")
#
#            # Print balance validation just for wastewater
#            validation = cell_data.validate_water_balance(include_components = {'groundwater'})
#            if 'groundwater' in validation:
#                print("\nDemand Balance Validation:")
#                values = validation['groundwater']
#                print(f"  Inflow: {values['inflow']:.6f}")
#                print(f"  Outflow: {values['outflow']:.6f}")
#                print(f"  Storage change: {values['total_storage_change']:.6f}")
#                print(f"  Balance: {values['balance']:.6f}")
#                input('*')

def _aggregate_timestep(model: UrbanWaterModel, results_agg: List[Dict], current_date: pd.Timestamp) -> None:
    """Aggregate results across all cells for the current timestep."""
    aggregated = {
        'date': current_date,
        'stormwater': 0,
        'wastewater': 0,
        'baseflow': 0,
        'total_seepage': 0,
        'imported_water': 0,
        'transpiration': 0,
        'evaporation': 0
    }

    for cell_id, data in model.data.items():
        # Aggregate end-point flows
        if model.path.loc[cell_id, 'down'] == 0:
            aggregated['stormwater'] += data.stormwater.flows.to_downstream.amount
            aggregated['wastewater'] += data.wastewater.flows.to_downstream.amount

        aggregated['baseflow'] += data.groundwater.flows.baseflow.amount
        aggregated['total_seepage'] += data.groundwater.flows.seepage.amount
        aggregated['imported_water'] += data.demand.flows.imported_water.amount
        aggregated['transpiration'] += data.vadose.flows.transpiration.amount
        aggregated['evaporation'] += (
            data.roof.flows.evaporation.amount +
            data.pavement.flows.evaporation.amount +
            data.pervious.flows.evaporation.amount +
            data.raintank.flows.evaporation.amount +
            data.stormwater.flows.evaporation.amount
        )

    #aggregated['imported_water'] -= sum(model.current[w].wastewater.use for w in model.wastewater_cells)
    #aggregated['imported_water'] -= sum(model.current[s].stormwater.use for s in model.stormwater_cells)

    results_agg.append(aggregated)

def results_to_dataframes(results_var: Dict[str, List[Dict]],
                         results_agg: List[Dict]) -> Dict[str, pd.DataFrame]:
    """Convert results dictionaries to DataFrames."""
    dataframe_results = {}

    # Convert component results to DataFrames
    for key, values in results_var.items():
        df = pd.DataFrame(values)
        if not df.empty:
            df = df.set_index(['cell', 'date'])
            dataframe_results[key] = df

    # Create aggregated results DataFrame
    df_agg = pd.DataFrame(results_agg)
    df_agg = df_agg.set_index('date')
    dataframe_results['aggregated'] = df_agg

    total_area = dataframe_results['groundwater']['area'].iloc[0].sum()
    dataframe_results['aggregated'].attrs['total_area'] = total_area

    # Create local results
    local_results = _create_local_results(dataframe_results)
    dataframe_results['local'] = local_results

    return dataframe_results

def _collect_component_results(cell_id: int, date: pd.Timestamp, component: object) -> dict:
    """Collect flattened results from a component."""
    results = {
        'cell': cell_id,
        'date': date
    }

    # Add attributes
    for attr_name, attr_value in vars(component).items():
        if not attr_name.startswith('_'):
            if isinstance(attr_value, (int, float, bool, str)):
                results[attr_name] = attr_value
            elif isinstance(attr_value, Storage):
                results[attr_name] = attr_value.get_amount('m3')

    if hasattr(component, 'flows'):
        flows = component.flows
        for flow_name, flow in vars(flows).items():
            results[flow_name] = flow.get_amount('m3')

    return results

def _create_local_results(dataframe_results: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Create DataFrame of selected local results."""
    selected = {
        'imported_water': ('demand', 'imported_water'),
        'stormwater_runoff': ('stormwater', 'to_downstream'),
        'wastewater_discharge': ('wastewater', 'to_downstream'),
        'baseflow': ('groundwater', 'baseflow'),
        'deep_seepage': ('groundwater', 'seepage')
    }

    evaporation_components = [
        ('roof', 'evaporation'),
        ('pavement', 'evaporation'),
        ('pervious', 'evaporation'),
        ('raintank', 'evaporation'),
        ('stormwater', 'evaporation'),
        ('vadose', 'transpiration')
    ]

    results_dict = {}

    # Process regular flows
    for col_name, (component, flow) in selected.items():
        if component in dataframe_results and flow in dataframe_results[component].columns:
            results_dict[col_name] = dataframe_results[component][flow]

    # Calculate evapotranspiration by summing all components
    evap_sum = None
    for component, flow in evaporation_components:
        if component in dataframe_results and flow in dataframe_results[component].columns:
            if evap_sum is None:
                evap_sum = dataframe_results[component][flow].copy()
            else:
                evap_sum += dataframe_results[component][flow]

    if evap_sum is not None:
        results_dict['evapotranspiration'] = evap_sum

    return pd.DataFrame(results_dict)
