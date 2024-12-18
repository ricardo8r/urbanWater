import os
from typing import Dict
from dynaconf import Dynaconf
import pandas as pd

def read_forcing(config: Dynaconf) -> pd.DataFrame:
    """
    Read and process daily precipitation, potential evaporation, and open water level data for multiple years.

    Args:
        config (Dynaconf): Configuration object containing file paths and settings

    Returns:
        pd.DataFrame: Processed forcing data
    """
    input_dir = config.input_directory
    files = config.files

    climate_data = pd.read_csv(os.path.join(input_dir, files.climate_file), header=0)
    climate_data['Date'] = pd.to_datetime(climate_data['Date'], format='%Y-%m-%d', errors='coerce')
    climate_data.set_index('Date', inplace=True)
    water_data = pd.read_csv(os.path.join(input_dir, files.open_water_file), header=0)
    water_data['Date'] = pd.to_datetime(water_data['Date'], format='%Y-%m-%d', errors='coerce')
    water_data.set_index('Date', inplace=True)

    start_date = pd.Timestamp(f"{config.simulation.start_year}-01-01")
    end_date = pd.Timestamp(f"{config.simulation.end_year}-12-31")
    date_mask = (climate_data.index >= start_date) & (climate_data.index <= end_date)

    if not date_mask.any():
        raise ValueError(f"No data available for the specified period: {config.simulation.start_year} to {config.simulation.end_year}")

    forcing = pd.DataFrame(index=climate_data.index[date_mask])
    forcing['precipitation'] = climate_data['P'][date_mask]
    forcing['potential_evaporation'] = climate_data['Ep'][date_mask]
    forcing['open_water_level'] = water_data['OWt'][date_mask]

    forcing['irrigation_index'] = forcing['potential_evaporation']
    yearly_sum = forcing['irrigation_index'].groupby(forcing.index.year).sum()
    forcing['pervious_irrigation'] = forcing['irrigation_index'] / yearly_sum[forcing.index.year].values
    forcing['roof_irrigation'] = forcing['impervious_irrigation'] = 0.0

    return forcing

def distribute_irrigation(forcing: pd.DataFrame, params: Dict[int, Dict[str, float]]) -> pd.DataFrame:
    """
    Distribute yearly irrigation amounts to daily values based on the irrigation index.sns.set_palette(palette)

    Args:
        forcing (pd.DataFrame): Forcing data including the irrigation index
        params (Dict[int, Dict[str, float]]): Model parameters
    """

    for _, cell_data in params.items():
        if cell_data['pervious']['area'] != 0:
            cell_data['irrigation']['pervious'] = (cell_data['irrigation']['block_water_demand'] *
                                                   1000 / cell_data['pervious']['area'])
