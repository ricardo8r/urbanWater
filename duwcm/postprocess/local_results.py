from typing import Dict
import pandas as pd

def extract_local_results(dataframe_results: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Create DataFrame of selected local results."""
    selected = {
        'imported_water': ('demand', 'imported_water'),
        'stormwater_runoff': ('stormwater', 'to_downstream'),
        'sewerage_discharge': ('sewerage', 'to_downstream'),
        'baseflow': ('groundwater', 'baseflow'),
        'deep_seepage': ('groundwater', 'seepage'),
        'vadose_moisture': ('vadose', 'moisture')
    }

    level_components = [
        ('groundwater', 'water_level', -1),
        ('groundwater', 'surface_water_level', 1)
    ]

    evaporation_components = [
        ('roof', 'evaporation'),
        ('impervious', 'evaporation'),
        ('pervious', 'evaporation'),
        ('raintank', 'evaporation'),
        ('stormwater', 'evaporation'),
        ('vadose', 'transpiration')
    ]

    results_dict = {}
    unit_dict = {}  # Track units separately

    # Process regular flows
    for col_name, (component, flow) in selected.items():
        if component in dataframe_results and flow in dataframe_results[component].columns:
            results_dict[col_name] = dataframe_results[component][flow]
            unit_dict[col_name] = dataframe_results[component][flow].attrs.get('unit', 'm3')

    # Calculate groundwater
    level_sum = None
    for component, flow, factor in level_components:
        if component in dataframe_results and flow in dataframe_results[component].columns:
            current = factor * dataframe_results[component][flow]
            if level_sum is None:
                level_sum = current
            else:
                level_sum += current

    if level_sum is not None:
        results_dict['groundwater'] = level_sum
        unit_dict['groundwater'] = 'm'

    # Calculate evapotranspiration
    evap_sum = None
    for component, flow in evaporation_components:
        if component in dataframe_results and flow in dataframe_results[component].columns:
            if evap_sum is None:
                evap_sum = dataframe_results[component][flow].copy()
            else:
                evap_sum += dataframe_results[component][flow]

    if evap_sum is not None:
        results_dict['evapotranspiration'] = evap_sum
        unit_dict['evapotranspiration'] = 'm3'

    df = pd.DataFrame(results_dict)
    df.attrs['units'] = unit_dict
    return df