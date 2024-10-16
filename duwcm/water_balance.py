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
from collections import defaultdict
import logging


import pandas as pd
from tqdm import tqdm

from duwcm.water_model import UrbanWaterModel
from duwcm.data_structures import UrbanWaterData, UrbanWaterFlowsData, ComponentFlows, FlowType

def run_water_balance(model: UrbanWaterModel, forcing: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """Run the full simulation for all timesteps."""
    num_timesteps = len(forcing)

    # Initialize results as dictionaries of lists
    results_var = {field.name: [] for field in fields(UrbanWaterData)}
    results_flow = {field.name: [] for field in fields(UrbanWaterFlowsData)}
    results_agg = []
    flow_tracker = defaultdict(lambda: defaultdict(float))

    # Add initial conditions to results at t=0
    initial_date = forcing.index[0] - pd.Timedelta(days=1)
    for cell_id, initial_state in model.previous.items():
        for module_name, module_data in initial_state.__dict__.items():
            results_var[module_name].append({
                'cell': cell_id,
                'date': initial_date,
                **module_data.__dict__
            })

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

    logger = logging.getLogger(__name__)
    is_debug = logger.getEffectiveLevel() == logging.DEBUG

    for t in tqdm(range(1, num_timesteps), desc="Water balance"):
        current_date = forcing.index[t]
        timestep_forcing = forcing.iloc[t]
        _solve_timestep(model, results_var, results_flow, timestep_forcing, current_date, flow_tracker)
        model.distribute_wastewater()
        model.distribute_stormwater()

        if is_debug:
            logger.debug(f"Checking flow consistency for timestep {t}, date {current_date}")
            _check_flow_consistency(flow_tracker)
            # Clear flow tracker after each timestep in debug mode
            flow_tracker.clear()

        _aggregate_timestep(model, results_agg, current_date)
        model.update_states()

    df_results = results_to_dataframes(results_var, results_flow, results_agg, model)

    total_area = sum(params['groundwater']['area'] for params in model.params.values())
    df_results['aggregated'].attrs['total_area'] = total_area
    df_results['aggregated'].attrs['units'] = 'L'

    return df_results

def _solve_timestep(model: UrbanWaterModel, results_var: Dict[str, List[Dict]],
                    results_flow: Dict[str, List[Dict]], forcing: pd.Series,
                    current_date: pd.Timestamp, flow_tracker: Dict[str, Dict[str, float]]) -> None:
    """Solve the water balance for a single timestep for all cells in the specified order."""
    for cell_id in model.cell_order:
        upstream_cells = [int(up) for up in model.path.loc[cell_id][1:] if up != 0]

        # Calculate upstream inflows for the current timestep
        model.current[cell_id].stormwater.upstream_inflow = 0
        model.current[cell_id].wastewater.upstream_inflow = 0
        for up in upstream_cells:
            model.current[cell_id].stormwater.upstream_inflow += model.current[up].stormwater.runoff_sewer
            model.current[cell_id].wastewater.upstream_inflow += model.current[up].wastewater.discharge

        # Solve for each submodel
        for submodel_name, submodel in model.submodels[cell_id].items():
            state_data, flow_data = submodel.solve(forcing, model.previous[cell_id], model.current[cell_id])
            setattr(model.current[cell_id], submodel_name, state_data)
            setattr(model.flows[cell_id], submodel_name, flow_data)

        # Append results for this cell and timestep
        for module_name, module_data in model.current[cell_id].__dict__.items():
            results_var[module_name].append({
                'cell': cell_id,
                'date': current_date,
                **module_data.__dict__
            })

        # Append flows for this cell and timestep
        for module_name, module_flows in model.flows[cell_id].__dict__.items():
            for flow in module_flows.flows:
                results_flow[module_name].append({
                    'cell': cell_id,
                    'date': current_date,
                    'source': flow.source,
                    'destination': flow.destination,
                    'flow_type': flow.flow_type.name,
                    'amount': flow.amount,
                    'unit': flow.unit
                })
                # Track the flow
                flow_key = f"{flow.source}->{flow.destination}"
                if flow_key not in flow_tracker:
                    flow_tracker[flow_key] = defaultdict(float)
                flow_tracker[flow_key][flow.flow_type.name] += flow.amount

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

    for cell_id in model.params:
        current = model.current[cell_id]
        params = model.params[cell_id]

        if model.path.loc[cell_id, 'down'] == 0:
            aggregated['stormwater'] += current.stormwater.runoff_sewer
            aggregated['wastewater'] += current.wastewater.discharge

        aggregated['baseflow'] += current.groundwater.baseflow
        aggregated['total_seepage'] += current.groundwater.seepage
        aggregated['imported_water'] += current.reuse.imported_water
        aggregated['transpiration'] += current.vadose.transpiration * params['vadose']['area']
        aggregated['evaporation'] += (
            current.roof.evaporation +
            current.pavement.evaporation +
            current.pervious.evaporation +
            current.raintank.evaporation +
            current.stormwater.evaporation
        )
    aggregated['imported_water'] -= sum(model.current[w].wastewater.use for w in model.wastewater_cells)
    aggregated['imported_water'] -= sum(model.current[s].stormwater.use for s in model.stormwater_cells)

    results_agg.append(aggregated)

def selected_results(flow_dataframes: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    selected_flows = {
        'reuse': {'imported_water': (FlowType.IMPORTED_WATER, 'input', 'reuse')},
        'stormwater': {'stormwater_runoff': (FlowType.RUNOFF, 'stormwater', 'output')},
        'wastewater': {'wastewater_runoff': (FlowType.WASTEWATER, 'wastewater', 'output')},
        'groundwater': {
            'baseflow': (FlowType.BASEFLOW, 'groundwater', 'output'),
            'deep_seepage': (FlowType.SEEPAGE, 'groundwater', 'output')
        }
    }

    dataframe_results = {}
    for module, flows in selected_flows.items():
        df = flow_dataframes[f"{module}_flows"]
        for new_name, (flow_type, source, destination) in flows.items():
            dataframe_results[new_name] = df.xs((source, destination, flow_type.name),
                                                level=['source', 'destination', 'flow_type'])['amount']

    # Compute evapotranspiration
    et_components = [
        ('roof', 'output', FlowType.EVAPORATION),
        ('pavement', 'output', FlowType.EVAPORATION),
        ('pervious', 'output', FlowType.EVAPORATION),
        ('raintank', 'output', FlowType.EVAPORATION),
        ('stormwater', 'output', FlowType.EVAPORATION),
        ('vadose', 'output', FlowType.TRANSPIRATION)
    ]
    et_data = []
    for module, destination, flow_type in et_components:
        df = flow_dataframes[f"{module}_flows"]
        component_data = df.xs((module, destination, flow_type.name),
                               level=['source', 'destination', 'flow_type'])['amount']
        et_data.append(component_data)

    dataframe_results['evapotranspiration'] = pd.concat(et_data, axis=1).sum(axis=1)

    combined_results = pd.DataFrame(dataframe_results)

    return combined_results

def results_to_dataframes(results_var: Dict[str, List[Dict]],
                          results_flow: Dict[str, List[Dict]],
                          results_agg: List[Dict],
                          model: UrbanWaterModel) -> Dict[str, pd.DataFrame]:
    dataframe_results = {}

    # Process variables
    for module, data in results_var.items():
        df = pd.DataFrame(data).set_index(['cell', 'date'])
        module_data = getattr(model.current[next(iter(model.current))], module)
        module_fields = fields(type(module_data))
        for column in df.columns:
            field = next(f for f in module_fields if f.name == column)
            df[column].attrs['unit'] = field.metadata['unit']
        dataframe_results[module] = df

    # Process flows
    flow_dataframes = {}
    for module, data in results_flow.items():
        df = pd.DataFrame(data)
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index(['cell', 'date', 'source', 'destination', 'flow_type'])
        flow_dataframes[f"{module}_flows"] = df

    # Process aggregated results
    dataframe_results['aggregated'] = pd.DataFrame(results_agg).set_index('date')

    # Create local results using the modified selected_results function
    dataframe_results['local'] = selected_results(flow_dataframes)

    # Add flow dataframes to the results
    dataframe_results.update(flow_dataframes)

    return dataframe_results

def _check_flow_consistency(flow_tracker: Dict[str, Dict[str, float]]) -> None:
    inconsistencies = []

    for flow_key, flow_data in flow_tracker.items():
        source, destination = flow_key.split("->")

        if source == 'input' or destination == 'output':
            continue

        reverse_key = f"{destination}->{source}"

        if reverse_key in flow_tracker:
            for flow_type, amount in flow_data.items():
                reverse_amount = flow_tracker[reverse_key].get(flow_type, 0)

                if abs(amount - reverse_amount) > 1e-6:
                    inconsistencies.append(
                        f"Inconsistency in {flow_type} flow between {source} and {destination}:\n"
                        f"  {source} reports outflow of {amount}\n"
                        f"  {destination} reports inflow of {reverse_amount}"
                    )

    logger = logging.getLogger(__name__)
    if inconsistencies:
        logger.debug("Flow inconsistencies detected:")
        for inconsistency in inconsistencies:
            logger.debug(inconsistency)
    else:
        logger.debug("All flows are consistent.")

    logger.debug("Full flow tracker contents:")
    for key, value in flow_tracker.items():
        logger.debug("%s: %s", key, value)
