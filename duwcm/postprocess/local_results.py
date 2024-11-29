from typing import Dict
import pandas as pd

def extract_local_results(dataframe_results: Dict[str, pd.DataFrame]) -> pd.DataFrame:
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