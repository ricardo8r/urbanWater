from typing import List, Dict
import pandas as pd

def et_selector(et_matrix: pd.DataFrame, soil_type: int, crop_type: int) -> pd.DataFrame:
    """
    Defines moisture content-related parameters based on given soil type and crop type.

    Args:
        et_matrix (pd.DataFrame): Evapotranspiration parameters
        soil_type (int): Soil type identifier
        crop_type (int): Crop type identifier

    Returns:
        pd.DataFrame: Selected row from et_matrix based on soil and crop type
    """
    return et_matrix.loc[(et_matrix.soil_type == soil_type) & (et_matrix.crop_type == crop_type)]

def soil_selector(soil_matrix: pd.DataFrame, et_matrix: pd.DataFrame, soil_type: int, crop_type: int) -> List[Dict]:
    """
    Returns a database of soil parameters based on given soil type and crop type.

    Parameters include:
    - Equilibrium moisture content
    - Maximum capillary rise
    - Storage coefficient
    - Saturated permeability
    - Unsaturated permeability

    Args:
        soil_matrix (pd.DataFrame): Soil parameters
        et_matrix (pd.DataFrame): Evapotranspiration parameters
        soil_type (int): Soil type identifier
        crop_type (int): Crop type identifier

    Returns:
        List[Dict]: List of dictionaries containing soil parameters
    """
    rootzone_thickness = 100 * et_selector(et_matrix, soil_type, crop_type)["th_rz_m"].values[0]
    soil_params = soil_matrix.loc[(soil_matrix.soil_type == soil_type) & 
                                  (soil_matrix.th_rz == int(rootzone_thickness))]
    return soil_params.to_dict(orient="Records")
