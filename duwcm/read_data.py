import os
from typing import Dict, Tuple
import pandas as pd
import numpy as np
from simpledbf import Dbf5
from dynaconf import Dynaconf

from duwcm.functions import (
    soil_selector, gw_levels, find_nearest_downstream
)

# Constants
HYDRAULIC_CONDUCTIVITY = 1.5
AQUIFER_THICKNESS = 0.2

def prepare_model_parameters(urban_data: pd.DataFrame, calibration_params: Dict,
                             altwater_data: pd.DataFrame, groundwater_data: pd.DataFrame,
                             soil_data: pd.DataFrame, et_data: pd.DataFrame,
                             grid_size: float, direction: int) -> Dict[int, Dict[str, Dict[str, float]]]:
    """
    Prepare model parameters for each grid cell.

    Args:
        urban_data (pd.DataFrame): UrbanBEATS output data
        calibration_params (Dict): Calibration parameters
        altwater_data (pd.DataFrame): Alternative water data
        groundwater_data (pd.DataFrame): Groundwater data
        soil_data (pd.DataFrame): Soil data
        et_data (pd.DataFrame): Evapotranspiration data
        grid_size (float): Size of each grid cell
        direction (int): Number of neighbors considered (4, 6, or 8)

    Returns:sww-wiki.eawag.ch
        Dict[int, Dict[str, Dict[str, float]]]: Model parameters for each cell
    """
    _, downstream_distances = find_nearest_downstream(urban_data, direction, grid_size)
    params: Dict[int, Dict[str, Dict]] = {}

    for i, cell_id in enumerate(urban_data.index):
        #param_index = 1 if calibration_params.shape[1] == 1 else cell_id FOR CELL BY CELL DATA

        if direction == 6:
            total_area = urban_data.Active[cell_id] * (1.5 * np.sqrt(3) * (grid_size**2))
        else:
            total_area = urban_data.Active[cell_id] * (grid_size**2)

        roof_area = urban_data.Blk_RoofsA[cell_id]
        impervious_area = urban_data.Blk_TIA[cell_id] - roof_area #Block Total Impervious Area
        pervious_area = total_area - roof_area - impervious_area
        num_houses = urban_data.ResHouses[cell_id] + urban_data.HDRFlats[cell_id]
        indoor_water_use = urban_data.WD_In[cell_id] * 1000.0  # kL/d/block --> L/day/block

        if np.isnan(num_houses):
            num_houses = 0
        average_occupancy = ((urban_data.HouseOccup[cell_id] * urban_data.ResHouses[cell_id] +
                              urban_data.HDROccup[cell_id] * urban_data.HDRFlats[cell_id]) / max(num_houses, 1.0))
        if np.isnan(average_occupancy):
            average_occupancy = 0

        if groundwater_data.loc[cell_id, 'gw0mSL'] > 20:
            downward_seepage = 0
            initial_level = max(groundwater_data.loc[cell_id, 'gw0mSL'], 0)
            hydraulic_head = max(groundwater_data.loc[cell_id, 'gwmmSL'], 0)
        else:
            downward_seepage = calibration_params.downward_seepage
            initial_level = max(groundwater_data.loc[cell_id, 'gw0mSL'], 0)
            hydraulic_head = max(groundwater_data.loc[cell_id, 'gwmmSL'], 0)

        if urban_data.pLU_WAT[cell_id] > 0.0001: #Fraction water land
            drainage_resistance = calibration_params.drainage_resistance
        else:
            drainage_resistance = downstream_distances[i]**2 / (8 * HYDRAULIC_CONDUCTIVITY * AQUIFER_THICKNESS)

        if drainage_resistance == 0:
            drainage_resistance = 1

        soil_type = calibration_params.soil_type
        crop_type = calibration_params.crop_type
        soil_params = soil_selector(soil_matrix=soil_data, et_matrix=et_data, soil_type=soil_type, crop_type=crop_type)
        initial_moisture = soil_params[gw_levels(groundwater_data.loc[cell_id, 'gw0mSL'])[2]]['moist_cont_eq_rz[mm]']

        if cell_id in altwater_data.index:
            altwater_params = altwater_data.loc[cell_id, :]
        else:
            altwater_params = altwater_data.iloc[-1, :]

        if urban_data.Blk_TIF[cell_id] < 0.05 * 0.01: #Total impervious fraction
            runoff_to_wastewater = 5
        else:
            runoff_to_wastewater = calibration_params.wastewater_inflow

        # Create parameter dictionary for each cell
        params[cell_id] = {
            'general': {
                'cell_id': cell_id,
                'x': urban_data.CentreX[cell_id],
                'y': urban_data.CentreY[cell_id],
                'time_step': calibration_params.timestep,
                'number_houses': num_houses,
                'average_occupancy': average_occupancy,
                'indoor_water_use': indoor_water_use,
                'elevation': urban_data.AvgElev[cell_id],
                'population': urban_data.Population[cell_id],
                'direction': direction
            },
            'irrigation': {
                'roof': 0,
                'impervious': 0,
                'pervious': 0,
                'block_water_demand': urban_data.WD_Out[cell_id] * 365.0
            },
            'soil': {
                'soil_type': soil_type,
                'crop_type': crop_type
            },
            'roof': {
                'area': roof_area,
                'effective_area': calibration_params.effective_roof_area,
                'max_storage': calibration_params.roof_storage
            },
            'raintank': {
                'is_open': altwater_params.RTop,
                'area': altwater_params.ART,
                'capacity': altwater_params.RTc,
                'first_flush': altwater_params.RTff,
                'initial_storage': altwater_params.RT0,
                'effective_area': calibration_params.effective_raintank_area,
                'install_ratio': altwater_params.pRT
            },
            'impervious': {
                'area': impervious_area,
                'effective_area': calibration_params.effective_impervious_area,
                'max_storage': calibration_params.impervious_storage,
                'infiltration_capacity': calibration_params.impervious_infiltration
            },
            'pervious': {
                'area': pervious_area,
                'max_storage': calibration_params.pervious_storage,
                'infiltration_capacity': calibration_params.pervious_infiltration
            },
            'vadose': {
                'area': pervious_area,
                'initial_moisture': initial_moisture
            },
            'groundwater': {
                'area': total_area,
                'leakage_rate': calibration_params.leakage_rate,
                'infiltration_recession': calibration_params.infiltration_coef,
                'initial_level': initial_level,
                'seepage_model': calibration_params.seepage_model,
                'drainage_resistance': drainage_resistance,
                'seepage_resistance': calibration_params.seepage_resistance,
                'hydraulic_head': hydraulic_head,
                'downward_seepage': downward_seepage
            },
            'stormwater': {
                'is_open': altwater_params.SWSop,
                'area': altwater_params.ASWS,
                'capacity': altwater_params.SWSc,
                'initial_storage': altwater_params.SWS0,
                'first_flush': altwater_params.SWSff,
                'wastewater_runoff_per': runoff_to_wastewater
            },
            'reuse': {
                'area': altwater_params.AWWS,
                'capacity': altwater_params.WWSc,
                'initial_storage': altwater_params.WWS0
            },
            'sewerage': {
                'area': altwater_params.AcWWS,
                'capacity': altwater_params.cWWSc,
                'initial_storage': altwater_params.cWWS0,
                'max_pipe_flow': calibration_params.wastewater_pipe_capacity
            }
        }

    return params

def create_flow_paths(urban_data: pd.DataFrame, direction: int) -> pd.DataFrame:
    """
    Create flow paths for each cell based on UrbanBEATS output.

    Args:
        urban_data (pd.DataFrame): UrbanBEATS output data
        direction (int): Direction that is considered for neighborhoods (4, 6, or 8)

    Returns:
        pd.DataFrame: Flow paths for each cell
    """
    flow_paths = []
    for cell_id in urban_data.index:
        neighbors = urban_data.Neighbours[cell_id].split(',')
        downstream_id = urban_data.downID[cell_id] if urban_data.downID[cell_id] > 0.0 else 0.0
        cell_path = [cell_id, downstream_id]
        upstream_cells = [int(neighbor) * (urban_data.downID[int(neighbor)] == cell_id) for neighbor in neighbors]
        upstream_cells.sort(reverse=True)
        cell_path.extend(upstream_cells)
        flow_paths.append(cell_path)

    flow_paths_df = pd.DataFrame(flow_paths)
    flow_paths_df = flow_paths_df.fillna(0)
    flow_paths_df.set_index(0, inplace=True)

    if direction == 8:
        flow_paths_df.columns = ['down', 'u1', 'u2', 'u3', 'u4', 'u5', 'u6', 'u7', 'u8']
    elif direction == 6:
        flow_paths_df.columns = ['down', 'u1', 'u2', 'u3', 'u4', 'u5', 'u6']
    else:
        flow_paths_df.columns = ['down', 'u1', 'u2', 'u3', 'u4']

    return flow_paths_df

def read_data(config: Dynaconf) -> Tuple[Dict[int, Dict[str, Dict[str, float]]], pd.DataFrame, pd.DataFrame]:
    """Read and process required data files."""
    input_dir = config.input_directory
    files = config.files

    # Read data files 
    dbf = Dbf5(os.path.join(input_dir, files.urban_beats_file), codec='utf-8')
    urban_data = dbf.to_dataframe()
    urban_data.set_index('BlockID', inplace=True)

    altwater_data = pd.read_csv(os.path.join(input_dir, files.alternative_water_file))
    altwater_data.loc[len(altwater_data)] = np.zeros(len(altwater_data.columns))
    altwater_data.set_index('id', inplace=True)

    groundwater_data = pd.read_csv(os.path.join(input_dir, files.groundwater_file)).set_index('BlockID')
    soil_data = pd.read_csv(os.path.join(input_dir, files.soil_file), header=0)
    et_data = pd.read_csv(os.path.join(input_dir, files.et_file), header=0)

    # Process data and prepare model parameters
    model_params = prepare_model_parameters(urban_data, config.calibration,
                                         altwater_data, groundwater_data, soil_data, et_data,
                                         config.grid.cell_size, config.grid.direction)

    # Create flow paths
    flow_paths = create_flow_paths(urban_data, config.grid.direction)

    return model_params, config.reuse, config.demand, soil_data, et_data, flow_paths
