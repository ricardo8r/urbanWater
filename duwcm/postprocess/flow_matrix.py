from typing import Dict, List
import numpy as np
import pandas as pd
from duwcm.data_structures import UrbanWaterData

def calculate_flow_matrix(results: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Calculate flow matrix between model components.

    Args:
        results: Dictionary containing simulation results for each component
        nodes: List of node names for the flow matrix

    Returns:
        pd.DataFrame: Matrix of flows between components
    """
    nodes = (['imported', 'precipitation', 'irrigation'] +
             UrbanWaterData.COMPONENTS +
             ['seepage', 'baseflow', 'evaporation', 'runoff'])

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

def calculate_cell_flow_matrix(results: Dict[str, pd.DataFrame], cell_id: int, flow_paths: pd.DataFrame) -> pd.DataFrame:
    """Track flows between cells and external inputs/outputs."""
    # Get connected cells
    upstream_cells = [col for col in flow_paths.columns if col.startswith('u')]
    upstream_ids = flow_paths.loc[cell_id, upstream_cells]
    upstream_ids = upstream_ids[upstream_ids != 0]
    downstream_id = flow_paths.loc[cell_id, 'down'] if flow_paths.loc[cell_id, 'down'] != 0 else None

    # Create list of cells and external terms
    cells = [cell_id]
    if len(upstream_ids) > 0:
        cells.extend(upstream_ids)
    if downstream_id:
        cells.append(downstream_id)

    # Create terms for the matrix
    # Create terms for the matrix
    # Create terms for the matrix
    flow_terms = []
    for c in cells:
        if c != cell_id:  # Only add flow terms for other cells
            flow_terms.extend([f'sewerage_cell_{c}', f'runoff_cell_{c}'])
    
    terms = ([f'cell_{c}' for c in cells] + 
             ['precipitation', 'evaporation', 'imported'] +
             ['roof_storage', 'raintank_storage', 'impervious_storage', 
              'pervious_storage', 'stormwater_storage', 'sewerage_storage',
              'vadose_moisture', 'groundwater_level'] +
             flow_terms)
    
    flow_matrix = pd.DataFrame(0.0, index=terms, columns=terms, dtype=np.float64)

    # Track flows between cells
    downstream_id = flow_paths.loc[cell_id, 'down']
    # Track upstream inflows
    for up_id in upstream_ids:
        # Track sewerage flows from upstream cells
        if 'sewerage' in results:
            sewerage_data = results['sewerage']
            upstream_flow = sewerage_data[
                (sewerage_data.index.get_level_values('cell') == up_id) &
                (sewerage_data['to_downstream'] > 0)
            ]['to_downstream'].sum()
            if upstream_flow > 0:
                flow_matrix.loc[f'cell_{up_id}', f'cell_{cell_id}'] = upstream_flow
                flow_matrix.loc[f'cell_{cell_id}', f'cell_{up_id}'] = -upstream_flow
            
        # Track stormwater (runoff) flows from upstream cells
        if 'stormwater' in results:
            stormwater_data = results['stormwater']
            upstream_flow = stormwater_data[
                (stormwater_data.index.get_level_values('cell') == up_id) &
                (stormwater_data['to_downstream'] > 0)
            ]['to_downstream'].sum()
            if upstream_flow > 0:
                flow_matrix.loc[f'cell_{up_id}', f'cell_{cell_id}'] = upstream_flow
                flow_matrix.loc[f'cell_{cell_id}', f'cell_{up_id}'] = -upstream_flow

    # Track downstream outflows
    if downstream_id != 0:
        # Track sewerage flows to downstream
        if 'sewerage' in results:
            sewerage_data = results['sewerage']
            cell_data = sewerage_data[sewerage_data.index.get_level_values('cell') == cell_id]
            if 'to_downstream' in cell_data.columns:
                flow_value = cell_data['to_downstream'].sum()
                if flow_value > 0:
                    flow_matrix.loc[f'cell_{cell_id}', f'cell_{downstream_id}'] = flow_value
                    flow_matrix.loc[f'cell_{downstream_id}', f'cell_{cell_id}'] = -flow_value
                
        # Track stormwater (runoff) flows to downstream
        if 'stormwater' in results:
            stormwater_data = results['stormwater']
            cell_data = stormwater_data[stormwater_data.index.get_level_values('cell') == cell_id]
            if 'to_downstream' in cell_data.columns:
                flow_value = cell_data['to_downstream'].sum()
                if flow_value > 0:
                    flow_matrix.loc[f'cell_{cell_id}', f'cell_{downstream_id}'] = flow_value
                    flow_matrix.loc[f'cell_{downstream_id}', f'cell_{cell_id}'] = -flow_value

    # Track precipitation
    total_precip = 0
    for comp in ['roof', 'raintank', 'impervious', 'pervious', 'stormwater']:
        if comp in results:
            comp_data = results[comp]
            cell_data = comp_data[comp_data.index.get_level_values('cell') == cell_id]
            if 'precipitation' in cell_data.columns:
                total_precip += cell_data['precipitation'].sum()
    
    flow_matrix.loc['precipitation', f'cell_{cell_id}'] = total_precip
    flow_matrix.loc[f'cell_{cell_id}', 'precipitation'] = -total_precip

    # Track evaporation
    total_evap = 0
    for comp in ['roof', 'raintank', 'impervious', 'pervious', 'stormwater']:
        if comp in results:
            comp_data = results[comp]
            cell_data = comp_data[comp_data.index.get_level_values('cell') == cell_id]
            if 'evaporation' in cell_data.columns:
                total_evap += cell_data['evaporation'].sum()
    
    # Add transpiration to evaporation
    if 'vadose' in results:
        vadose_data = results['vadose']
        cell_data = vadose_data[vadose_data.index.get_level_values('cell') == cell_id]
        if 'transpiration' in cell_data.columns:
            total_evap += cell_data['transpiration'].sum()

    flow_matrix.loc[f'cell_{cell_id}', 'evaporation'] = total_evap
    flow_matrix.loc['evaporation', f'cell_{cell_id}'] = -total_evap

    # Track imported water
    if 'demand' in results:
        demand_data = results['demand']
        cell_data = demand_data[demand_data.index.get_level_values('cell') == cell_id]
        if 'imported_water' in cell_data.columns:
            imported = cell_data['imported_water'].sum()
            flow_matrix.loc['imported', f'cell_{cell_id}'] = imported
            flow_matrix.loc[f'cell_{cell_id}', 'imported'] = -imported

    # Track storage changes by component
    storage_components = {
        'roof_storage': ('roof', 'storage', 'm3'),
        'raintank_storage': ('raintank', 'storage', 'm3'),
        'impervious_storage': ('impervious', 'storage', 'm3'),
        'pervious_storage': ('pervious', 'storage', 'm3'),
        'stormwater_storage': ('stormwater', 'storage', 'm3'),
        'sewerage_storage': ('sewerage', 'storage', 'm3'),
        'vadose_moisture': ('vadose', 'moisture', 'mm'),
        'groundwater_level': ('groundwater', 'water_level', 'm')
    }

    for storage_name, (comp, col_name, unit) in storage_components.items():
        if comp in results:
            comp_data = results[comp]
            cell_data = comp_data[comp_data.index.get_level_values('cell') == cell_id]
            if col_name in cell_data.columns:
                # Get unit from the data attributes if available
                data_unit = cell_data[col_name].attrs.get('unit', unit)
                storage_change = cell_data[col_name].iloc[-1] - cell_data[col_name].iloc[0]
                # Convert all changes to m3 for consistency
                if data_unit == 'mm':
                    cell_area = cell_data['area'].iloc[0]  # Get area for conversion
                    storage_change = storage_change * cell_area * 0.001  # mm to m3
                elif data_unit == 'm' and col_name == 'water_level':
                    cell_area = cell_data['area'].iloc[0]  # Get area for conversion
                    storage_change = storage_change * cell_area  # m to m3

                flow_matrix.loc[f'cell_{cell_id}', storage_name] = storage_change
                flow_matrix.loc[storage_name, f'cell_{cell_id}'] = -storage_change

    # Remove empty rows and columns
    non_zero_mask = (flow_matrix.sum(axis=0) != 0) | (flow_matrix.sum(axis=1) != 0)
    return flow_matrix.loc[non_zero_mask, non_zero_mask]