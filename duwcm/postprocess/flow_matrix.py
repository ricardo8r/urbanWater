from typing import Dict, List
import pandas as pd
from duwcm.data_structures import UrbanWaterData

def calculate_flow_matrix(results: Dict[str, pd.DataFrame], nodes: List[str]) -> pd.DataFrame:
    """
    Calculate flow matrix between model components.

    Args:
        results: Dictionary containing simulation results for each component
        nodes: List of node names for the flow matrix

    Returns:
        pd.DataFrame: Matrix of flows between components
    """
    flow_matrix = pd.DataFrame(0, index=nodes, columns=nodes, dtype=float)

    # Process component connections
    for (src_comp, source_flow), (trg_comp, target_flow) in UrbanWaterData.FLOW_CONNECTIONS.items():
        if src_comp in UrbanWaterData.COMPONENTS and trg_comp in UrbanWaterData.COMPONENTS:
            flow_value = results[src_comp][source_flow].sum()
            if flow_value > 0:
                flow_matrix.loc[src_comp, trg_comp] = float(flow_value)

    # Add precipitation flows
    for comp in ['roof', 'impervious', 'pervious', 'raintank', 'stormwater']:
        if comp in results:
            flow_value = results[comp]['precipitation'].sum()
            if flow_value > 0:
                flow_matrix.loc['precipitation', comp] = float(flow_value)

    # Add evaporation flows
    for comp in ['roof', 'impervious', 'pervious', 'raintank', 'stormwater']:
        if comp in results:
            flow_value = results[comp]['evaporation'].sum()
            if flow_value > 0:
                flow_matrix.loc[comp, 'evaporation'] = float(flow_value)

    # Add transpiration
    if 'vadose' in results:
        flow_value = results['vadose']['transpiration'].sum()
        if flow_value > 0:
            flow_matrix.loc['vadose', 'evaporation'] = float(flow_value)

    # Add imported water flows
    if 'demand' in results:
        flow_value = results['demand']['imported_water'].sum()
        if flow_value > 0:
            flow_matrix.loc['imported', 'demand'] = float(flow_value)

    # Add baseflow and seepage
    if 'groundwater' in results:
        flow_value = results['groundwater']['seepage'].sum()
        if flow_value > 0:
            flow_matrix.loc['groundwater', 'seepage'] = float(flow_value)
        elif flow_value < 0:
            flow_matrix.loc['seepage', 'groundwater'] = abs(float(flow_value))

        flow_value = results['groundwater']['baseflow'].sum()
        if flow_value > 0:
            flow_matrix.loc['groundwater', 'baseflow'] = float(flow_value)
        elif flow_value < 0:
            flow_matrix.loc['baseflow', 'groundwater'] = abs(float(flow_value))

    if 'aggregated' in results:
        stormwater_runoff = results['aggregated']['stormwater'].sum()
        sewerage_discharge = results['aggregated']['sewerage'].sum()

        if stormwater_runoff > 0:
            flow_matrix.loc['stormwater', 'runoff'] = float(stormwater_runoff)
        if sewerage_discharge > 0:
            flow_matrix.loc['sewerage', 'discharge'] = float(sewerage_discharge)

    # Remove any non-node columns/rows and NaN values
    valid_cols = [col for col in flow_matrix.columns if col in nodes]
    flow_matrix = flow_matrix.loc[valid_cols, valid_cols]

    # Remove empty rows/columns
    non_zero_mask = (flow_matrix.sum(axis=0) != 0) | (flow_matrix.sum(axis=1) != 0)
    return flow_matrix.loc[non_zero_mask, non_zero_mask]


def calculate_reuse_flow_matrix(results: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Calculate flow matrix for internal demand flows showing water quality transformations."""
    if 'demand' not in results:
        return pd.DataFrame()

    demand = results['demand']
    sources = ['Potable Water', 'Rainwater', 'Treated WW', 'Graywater']
    uses = ['Kitchen', 'Bathroom', 'Laundry', 'Toilet', 'Irrigation', 'Sewerage']

    nodes = sources + uses
    flow_matrix = pd.DataFrame(0, index=nodes, columns=nodes, dtype=float)

    # Get total demand for each use
    total_kitchen = demand['po_to_kitchen'].sum() + demand['rt_to_kitchen'].sum()
    total_bathroom = demand['po_to_bathroom'].sum() + demand['rt_to_bathroom'].sum()
    total_laundry = demand['po_to_laundry'].sum() + demand['rt_to_laundry'].sum()

    # Source to end use flows
    flow_matrix.loc['Potable Water', 'Kitchen'] = demand['po_to_kitchen'].sum()
    flow_matrix.loc['Potable Water', 'Bathroom'] = demand['po_to_bathroom'].sum()
    flow_matrix.loc['Potable Water', 'Laundry'] = demand['po_to_laundry'].sum()
    flow_matrix.loc['Potable Water', 'Toilet'] = demand['po_to_toilet'].sum()
    flow_matrix.loc['Potable Water', 'Irrigation'] = demand['po_to_irrigation'].sum()

    flow_matrix.loc['Rainwater', 'Kitchen'] = demand['rt_to_kitchen'].sum()
    flow_matrix.loc['Rainwater', 'Bathroom'] = demand['rt_to_bathroom'].sum()
    flow_matrix.loc['Rainwater', 'Laundry'] = demand['rt_to_laundry'].sum()
    flow_matrix.loc['Rainwater', 'Toilet'] = demand['rt_to_toilet'].sum()
    flow_matrix.loc['Rainwater', 'Irrigation'] = demand['rt_to_irrigation'].sum()

    flow_matrix.loc['Treated', 'Toilet'] = demand['wws_to_toilet'].sum()
    flow_matrix.loc['Treated', 'Irrigation'] = demand['wws_to_irrigation'].sum()
    flow_matrix.loc['Sewerage', 'Treated'] = (demand['wws_to_irrigation'].sum() +
                                                demand['wws_to_toilet'].sum())

    # Graywater generation and use
    flow_matrix.loc['Kitchen', 'Graywater'] = demand['kitchen_to_graywater'].sum()
    flow_matrix.loc['Bathroom', 'Graywater'] = demand['bathroom_to_graywater'].sum()
    flow_matrix.loc['Laundry', 'Graywater'] = demand['laundry_to_graywater'].sum()

    flow_matrix.loc['Graywater', 'Irrigation'] = demand['graywater_to_irrigation'].sum()
    flow_matrix.loc['Graywater', 'Sewerage'] = demand['graywater_to_sewerage'].sum()

    # Flows to sewerage - everything that doesn't go to graywater
    flow_matrix.loc['Kitchen', 'Sewerage'] = total_kitchen - demand['kitchen_to_graywater'].sum()
    flow_matrix.loc['Bathroom', 'Sewerage'] = total_bathroom - demand['bathroom_to_graywater'].sum()
    flow_matrix.loc['Laundry', 'Sewerage'] = total_laundry - demand['laundry_to_graywater'].sum()
    flow_matrix.loc['Toilet', 'Sewerage'] = (demand['po_to_toilet'].sum() +
                                              demand['rt_to_toilet'].sum() +
                                              demand['wws_to_toilet'].sum())

    # Remove any non-node columns/rows and NaN values
    valid_cols = [col for col in flow_matrix.columns if col in nodes]
    flow_matrix = flow_matrix.loc[valid_cols, valid_cols]

    # Remove empty rows/columns
    non_zero_mask = (flow_matrix.sum(axis=0) != 0) | (flow_matrix.sum(axis=1) != 0)
    return flow_matrix.loc[non_zero_mask, non_zero_mask]