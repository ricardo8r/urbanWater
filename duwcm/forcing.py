from typing import Dict
from dynaconf import Dynaconf
import pandas as pd

def read_forcing(config: Dynaconf) -> pd.DataFrame:
    """
    Read and process daily precipitation, potential evaporation, and open water level data.

    Args:
        config (Dynaconf): Configuration object containing file paths and settings

    Returns:
        pd.DataFrame: Processed forcing data
    """
    climate_data = pd.read_csv(config.file_paths.climate_file, header=0)
    climate_data['Date'] = pd.to_datetime(climate_data['Date'], format='%Y-%m-%d', errors='coerce')
    climate_data.set_index('Date', inplace=True)
    water_data = pd.read_csv(config.file_paths.open_water_file, header=0)
    water_data['Date'] = pd.to_datetime(water_data['Date'], format='%Y-%m-%d', errors='coerce')
    water_data.set_index('Date', inplace=True)

    year_mask = climate_data.index.year == config.simulation.year
    if not year_mask.any():
        raise ValueError(f"No data available for the specified year: {config.simulation.year}")

    forcing = pd.DataFrame(index=climate_data.index[year_mask])
    forcing['precipitation'] = climate_data['P'][year_mask] * config.simulation.time_step
    forcing['potential_evaporation'] = climate_data['Ep'][year_mask] * config.simulation.time_step
    forcing['open_water_level'] = water_data['OWt'][year_mask]
    forcing['irrigation_index'] = forcing['potential_evaporation']
    forcing['normalized_irrigation_index'] = forcing['irrigation_index'] / forcing['irrigation_index'].sum()
    forcing['roof_irrigation'] = forcing['pavement_irrigation'] = 0.0
    forcing['pervious_irrigation'] = 1.0

    return forcing

def distribute_irrigation(forcing: pd.DataFrame, params: Dict[int, Dict[str, float]]) -> pd.DataFrame:
    """
    Distribute yearly irrigation amounts to daily values based on the irrigation index.

    Args:
        forcing (pd.DataFrame): Forcing data including the irrigation index
        params (Dict[int, Dict[str, float]]): Model parameters
    """

    for _, cell_data in params.items():
        if cell_data['pervious']['area'] != 0:
            cell_data['irrigation']['pervious'] = (forcing['normalized_irrigation_index'] * 1000 *
                                                   cell_data['irrigation']['block_water_demand'] /
                                                   cell_data['pervious']['area'])
