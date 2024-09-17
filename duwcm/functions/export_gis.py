from typing import Dict
from pathlib import Path
import warnings

import geopandas as gpd
import pandas as pd

def export_gpkg(geometry_geopackage: Path, results: Dict[str, pd.DataFrame],
                  params: Dict[int, Dict[str, Dict[str, float]]],
                forcing: pd.DataFrame, output_dir: Path, crs: str) -> None:
    """
    Export simulation results to two GeoPackage files: one for statistical data and one for temporal data.

    Args:
        geometry_geopackage (Path): Path to the GeoPackage file containing geometry data
        results (Dict[str, pd.DataFrame]): Dictionary of DataFrames containing results for each module
        params (Dict[int, Dict[str, Dict[str, float]]]): Dictionary of parameter dictionaries for each grid cell
        forcing (pd.DataFrame): Climate forcing data
        output_dir (Path): Directory to save the output files
    """
    gdf_geometry = gpd.read_file(geometry_geopackage)
    if gdf_geometry.crs != crs:
        warnings.warn(f"CRS mismatch: Input geometry CRS ({gdf_geometry.crs}) does not match "
                      f"specified CRS ({crs}). Using geometry CRS.")
        crs = gdf_geometry.crs

    statistical_file = output_dir / 'statistical_results.gpkg'
    temporal_file = output_dir / 'temporal_results.gpkg'

    #cell_ids = list(params.keys())
    #area_dict = {
    #    'roof': pd.Series({cell: params[cell]['roof']['area'] for cell in cell_ids}),
    #    'pavement': pd.Series({cell: params[cell]['pavement']['area'] for cell in cell_ids}),
    #    'pervious': pd.Series({cell: params[cell]['pervious']['area'] for cell in cell_ids}),
    #    'vadose': pd.Series({cell: params[cell]['vadose']['area'] for cell in cell_ids})
    #}
    #et_data = (
    #    results['roof']['evaporation'].mul(area_dict['roof'], level='cell') +
    #    results['pervious']['evaporation'].mul(area_dict['pervious'], level='cell') +
    #    results['pavement']['evaporation'].mul(area_dict['pavement'], level='cell') +
    #    results['vadose']['transpiration'].mul(area_dict['vadose'], level='cell') +
    #    results['raintank']['evaporation'] +
    #    results['stormwater']['evaporation']
    #)

    # Prepare statistical data for each submodel
    statistical_data = {
        'reuse': [],
        'stormwater': [],
        'wastewater': [],
        'groundwater': [],
        'evapotranspiration': []
    }

    for cell_id, cell_params in params.items():
        # Extract relevant data for each submodel
        reuse_data = results['reuse'].xs(cell_id, level='cell')
        stormwater_data = results['stormwater'].xs(cell_id, level='cell')
        wastewater_data = results['wastewater'].xs(cell_id, level='cell')
        groundwater_data = results['groundwater'].xs(cell_id, level='cell')

        # Calculate evapotranspiration
        et_data = (
            results['roof'].xs(cell_id, level='cell')['evaporation'] * cell_params['roof']['area'] +
            results['pavement'].xs(cell_id, level='cell')['evaporation'] * cell_params['pavement']['area'] +
            results['pervious'].xs(cell_id, level='cell')['evaporation'] * cell_params['pervious']['area'] +
            results['raintank'].xs(cell_id, level='cell')['evaporation'] +
            results['stormwater'].xs(cell_id, level='cell')['evaporation'] +
            results['vadose'].xs(cell_id, level='cell')['transpiration'] * cell_params['vadose']['area']
        )

        # Append data for each submodel
        statistical_data['reuse'].append({
            'BlockID': cell_id,
            'total_imported_water': reuse_data['imported_water'].sum(),
            'avg_imported_water': reuse_data['imported_water'].mean(),
            'max_imported_water': reuse_data['imported_water'].max(),
        })

        statistical_data['stormwater'].append({
            'BlockID': cell_id,
            'total_stormwater_sewer_inflow': stormwater_data['sewer_inflow'].sum(),
            'avg_stormwater_sewer_inflow': stormwater_data['sewer_inflow'].mean(),
            'max_stormwater_sewer_inflow': stormwater_data['sewer_inflow'].max(),
        })

        statistical_data['wastewater'].append({
            'BlockID': cell_id,
            'total_wastewater_sewer_inflow': wastewater_data['sewer_inflow'].sum(),
            'avg_wastewater_sewer_inflow': wastewater_data['sewer_inflow'].mean(),
            'max_wastewater_sewer_inflow': wastewater_data['sewer_inflow'].max(),
        })

        statistical_data['groundwater'].append({
            'BlockID': cell_id,
            'total_baseflow': groundwater_data['baseflow'].sum(),
            'avg_baseflow': groundwater_data['baseflow'].mean(),
            'max_baseflow': groundwater_data['baseflow'].max(),
            'total_deep_seepage': groundwater_data['seepage'].sum(),
            'avg_deep_seepage': groundwater_data['seepage'].mean(),
            'max_deep_seepage': groundwater_data['seepage'].max(),
        })

        statistical_data['evapotranspiration'].append({
            'BlockID': cell_id,
            'total_evapotranspiration': et_data.sum(),
            'avg_evapotranspiration': et_data.mean(),
            'max_evapotranspiration': et_data.max(),
        })

    # Export statistical data for each submodel
    for submodel, data in statistical_data.items():
        df_statistical = pd.DataFrame(data)
        gdf_statistical = gdf_geometry[['BlockID', 'geometry']].merge(df_statistical, on='BlockID', how='left')
        gdf_statistical = gpd.GeoDataFrame(gdf_statistical, geometry='geometry', crs=crs)
        gdf_statistical.to_file(statistical_file, driver="GPKG", layer=f"{submodel}_statistics")

    # Export temporal data
    variables_to_export = {
        'reuse': ['imported_water'],
        'stormwater': ['sewer_inflow'],
        'wastewater': ['sewer_inflow'],
        'groundwater': ['baseflow', 'seepage']
    }

    for module, variables in variables_to_export.items():
        df = results[module].reset_index()
        columns_to_keep = ['timestep', 'cell'] + variables
        df_subset = df[columns_to_keep].copy()
        df_subset['date'] = forcing.index[df_subset['timestep']]
        df_subset.drop('timestep', axis=1, inplace=True)
        df_subset['cell'] = df_subset['cell'].astype(int)

        # Merge with spatial data
        gdf_temporal = gdf_geometry[['BlockID', 'geometry']].merge(df_subset, left_on='BlockID', right_on='cell')
        gdf_temporal = gpd.GeoDataFrame(gdf_temporal, geometry='geometry', crs=crs)
        gdf_temporal.to_file(temporal_file, driver="GPKG", layer=f"{module}")

    # Export evapotranspiration data
    et_df = pd.DataFrame(statistical_data['evapotranspiration'])
    et_df['date'] = forcing.index[-1]  # Use the last date as we're working with aggregated data
    gdf_et = gdf_geometry[['BlockID', 'geometry']].merge(et_df, on='BlockID', how='left')
    gdf_et = gpd.GeoDataFrame(gdf_et, geometry='geometry', crs=crs)
    gdf_et.to_file(temporal_file, driver="GPKG", layer="evapotranspiration")
