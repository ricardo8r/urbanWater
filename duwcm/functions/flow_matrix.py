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
            flow_value = results[src_comp][source_flow].sum() * 0.001
            if flow_value > 0:
                flow_matrix.loc[src_comp, trg_comp] = float(flow_value)

    # Add precipitation flows
    for comp in ['roof', 'pavement', 'pervious', 'raintank', 'stormwater']:
        if comp in results:
            flow_value = results[comp]['precipitation'].sum() * 0.001
            if flow_value > 0:
                flow_matrix.loc['precipitation', comp] = float(flow_value)

    # Add evaporation flows
    for comp in ['roof', 'pavement', 'pervious', 'raintank', 'stormwater']:
        if comp in results:
            flow_value = results[comp]['evaporation'].sum() * 0.001
            if flow_value > 0:
                flow_matrix.loc[comp, 'evaporation'] = float(flow_value)

    # Add transpiration
    if 'vadose' in results:
        flow_value = results['vadose']['transpiration'].sum() * 0.001
        if flow_value > 0:
            flow_matrix.loc['vadose', 'evaporation'] = float(flow_value)

    # Add imported water flows
    if 'demand' in results:
        flow_value = results['demand']['imported_water'].sum() * 0.001
        if flow_value > 0:
            flow_matrix.loc['imported', 'demand'] = float(flow_value)

    # Add baseflow and seepage
    if 'groundwater' in results:
        flow_value = results['groundwater']['seepage'].sum() * 0.001
        if flow_value > 0:
            flow_matrix.loc['groundwater', 'seepage'] = float(flow_value)
        elif flow_value < 0:
            flow_matrix.loc['seepage', 'groundwater'] = abs(float(flow_value))

        flow_value = results['groundwater']['baseflow'].sum() * 0.001
        if flow_value > 0:
            flow_matrix.loc['groundwater', 'baseflow'] = float(flow_value)
        elif flow_value < 0:
            flow_matrix.loc['baseflow', 'groundwater'] = abs(float(flow_value))

    # Remove empty rows/columns
    non_zero_mask = (flow_matrix.sum(axis=0) != 0) | (flow_matrix.sum(axis=1) != 0)
    return flow_matrix.loc[non_zero_mask, non_zero_mask]