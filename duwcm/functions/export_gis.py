from typing import Dict
from pathlib import Path
import warnings

import geopandas as gpd
import pandas as pd

def export_gpkg(geometry_geopackage: Path, local_results: pd.DataFrame,
                params: Dict[int, Dict[str, Dict[str, float]]],
                forcing: pd.DataFrame, output_dir: Path, crs: str) -> None:
    """
    Export simulation results to two GeoPackage files: one for statistical data and one for temporal data.

    Args:
        geometry_geopackage (Path): Path to the GeoPackage file containing geometry data
        local_results (pd.DataFrame): DataFrame containing results for plot
        params (Dict[int, Dict[str, Dict[str, float]]]): Dictionary of parameter dictionaries for each grid cell
        forcing (pd.DataFrame): Climate forcing data
        output_dir (Path): Directory to save the output files
        crs (str): Coordinate Reference System for the spatial data
    """
    gdf_geometry = gpd.read_file(geometry_geopackage)
    if gdf_geometry.crs != crs:
        warnings.warn(f"CRS mismatch: Input geometry CRS ({gdf_geometry.crs}) does not match "
                      f"specified CRS ({crs}). Using geometry CRS.")
        crs = gdf_geometry.crs

    statistical_file = output_dir / 'statistical_results.gpkg'
    temporal_file = output_dir / 'temporal_results.gpkg'

    # Calculate statistical data
    statistical_data = local_results.groupby(level='cell').agg({
        'imported_water': ['sum', 'mean', 'max'],
        'stormwater_runoff': ['sum', 'mean', 'max'],
        'wastewater_runoff': ['sum', 'mean', 'max'],
        'evapotranspiration': ['sum', 'mean', 'max'],
        'baseflow': ['sum', 'mean', 'max'],
        'deep_seepage': ['sum', 'mean', 'max']
    })
    statistical_data.columns = ['_'.join(col).strip() for col in statistical_data.columns.values]
    statistical_data = statistical_data.reset_index()

    # Merge with geometry and export statistical data
    gdf_statistical = gdf_geometry[['BlockID', 'geometry']].merge(statistical_data, left_on='BlockID', right_on='cell', how='left')
    gdf_statistical = gpd.GeoDataFrame(gdf_statistical, geometry='geometry', crs=crs)
    gdf_statistical.to_file(statistical_file, driver="GPKG", layer="statistics")

    # Prepare and export temporal data
    local_results_reset = local_results.reset_index()
    local_results_reset['date'] = forcing.index[local_results_reset['timestep']]
    local_results_reset = local_results_reset.drop('timestep', axis=1)

    gdf_temporal = gdf_geometry[['BlockID', 'geometry']].merge(local_results_reset, left_on='BlockID', right_on='cell', how='left')
    gdf_temporal = gpd.GeoDataFrame(gdf_temporal, geometry='geometry', crs=crs)
    gdf_temporal.to_file(temporal_file, driver="GPKG", layer="temporal_data")
