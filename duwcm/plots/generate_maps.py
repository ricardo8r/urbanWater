from typing import Dict, List, Any, Optional
from pathlib import Path
import numpy as np
import pandas as pd

import geopandas as gpd
import matplotlib.pyplot as plt

from mpl_toolkits.axes_grid1 import make_axes_locatable
from shapely.geometry import LineString

from duwcm.postprocess import extract_local_results

def plot_linear(ax: plt.Axes, gdf_geometry: gpd.GeoDataFrame, flow_paths: pd.DataFrame,
                variable_name: str, cmap: str) -> Optional[plt.cm.ScalarMappable]:
    runoff_data = gdf_geometry[variable_name].dropna()
    if runoff_data.empty:
        return None

    # Determine colormap direction based on data
    if runoff_data.mean() < 0:
        cmap = cmap + "_r"

    vmin, vmax = runoff_data.min(), runoff_data.max()
    norm = plt.Normalize(vmin=vmin, vmax=vmax)
    cmap_obj = plt.get_cmap(cmap)

    def get_line_width(value):
        # Scale line width between 0.5 and 3 based on absolute value
        abs_min, abs_max = min(abs(vmin), abs(vmax)), max(abs(vmin), abs(vmax))
        return np.interp(abs(value), [abs_min, abs_max], [1.5, 5])

    cell_data = {row['BlockID']: row for _, row in gdf_geometry.iterrows()}

    # Only plot flows for cells that have data
    for cell_id, row in cell_data.items():
        if pd.notna(row[variable_name]):  # Only process cells with data
            downstream_id = flow_paths.loc[cell_id, 'down']
            if downstream_id in cell_data:
                start_point = row.geometry.centroid
                end_point = cell_data[downstream_id].geometry.centroid
                line = LineString([start_point, end_point])

                value = row[variable_name]
                color = cmap_obj(norm(value))
                linewidth = get_line_width(value)
                ax.plot(*line.xy, color=color, linewidth=linewidth, solid_capstyle='round')

    sm = plt.cm.ScalarMappable(cmap=cmap_obj, norm=norm)
    sm.set_array([])
    return sm

def plot_variable(background_shapefile: Path, feature_shapefiles: List[Path],
                  geometry_geopackage: Path, data: pd.Series, variable_name: str,
                  output_path: Path, cmap: str, flow_paths: Optional[pd.DataFrame] = None) -> None:
    gdf_geometry = gpd.read_file(geometry_geopackage)

    # Remove 0 values and add data to the geometry GeoDataFrame
    data = data[abs(data) > 0]
    gdf_geometry[variable_name] = gdf_geometry['BlockID'].map(data)

    _, ax = plt.subplots(figsize=(12, 10))

    # Plot background shapefile
    gdf_background = gpd.read_file(background_shapefile)
    if gdf_background.crs != gdf_geometry.crs:
        gdf_background = gdf_background.to_crs(gdf_geometry.crs)

    gdf_geometry.plot(ax=ax, color='lightgray', edgecolor='none', alpha=0.8)
    gdf_background.plot(ax=ax, color='none', edgecolor='gray', alpha=0.8)

    # Plot feature shapefiles
    for shapefile in feature_shapefiles:
        gdf_feature = gpd.read_file(shapefile)
        if gdf_feature.crs != gdf_geometry.crs:
            gdf_feature = gdf_feature.to_crs(gdf_geometry.crs)

        # Determine color based on the feature type
        if 'Rivers' in shapefile.name:
            edgecolor = 'dodgerblue'
            color = 'dodgerblue'
        else:
            edgecolor = 'gray'
            color = 'none'

        gdf_feature.plot(ax=ax, color=color, edgecolor=edgecolor, alpha=0.8, linewidth=1)

    # Get unit from data attributes if available
    unit = data.attrs.get('unit', 'm3')
    unit_label = {
        'm3': r'm³',
        'mm': 'mm',
        'm': 'm',
        'L': 'L'
    }.get(unit, unit)

    # Plot data
    if variable_name in ['stormwater_runoff', 'sewerage_discharge']:
        sm = plot_linear(ax, gdf_geometry, flow_paths, variable_name, cmap)
    else:
        values = gdf_geometry[variable_name].dropna()
        if not values.empty:
            # Determine if we should reverse the colormap based on data
            mean_value = values.mean()
            if mean_value < 0:
                cmap = cmap + "_r"

            vmin = values.min()
            vmax = values.max()
            sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=vmin, vmax=vmax))
            sm.set_array([])

            # Plot only cells with data
            gdf_geometry[gdf_geometry[variable_name].notnull()].plot(
                column=variable_name,
                ax=ax,
                cmap=cmap,
                alpha=0.5,
                vmin=vmin,
                vmax=vmax
            )

    ax.set_title(f'{variable_name.replace("_", " ").capitalize()}')
    ax.axis('off')

    divider = make_axes_locatable(ax)
    cax = divider.append_axes("right", size="3%", pad=0.1)
    cbar = plt.colorbar(sm, cax=cax)

    # Format with scientific notation
    cbar.formatter.set_powerlimits((0, 0))
    cbar.ax.yaxis.set_offset_position('right')
    cbar.ax.yaxis.offsetText.set_fontsize(8)
    cbar.ax.yaxis.offsetText.set_position((0, 1.05))
    cbar.update_ticks()

    # Set label with proper unit
    if unit in ['m3', 'L']:
        cbar.set_label(fr'{variable_name.replace("_", " ").capitalize()} [{unit_label}/yr]',
                       rotation=270, labelpad=15)
    else:
        cbar.set_label(fr'{variable_name.replace("_", " ").capitalize()} [{unit_label}]',
                       rotation=270, labelpad=15)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()

def generate_maps(background_shapefile: Path, feature_shapefiles: List[Path], geometry_geopackage: Path,
                  results: Dict[str, pd.DataFrame], output_dir: Path, flow_paths: pd.DataFrame) -> None:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    variables_to_plot = {
        'evapotranspiration': ('Greens', None),
        'imported_water': ('YlOrRd', None),
        'baseflow': ('Blues', None),
        'deep_seepage': ('PuBuGn', None),
        'stormwater_runoff': ('BuPu', flow_paths),
        'sewerage_discharge': ('PuRd', flow_paths),
        'groundwater': ('YlOrBr', None),
        'vadose_moisture': ('YlGnBu', None)
    }

    # Get local results with units
    local_results = extract_local_results(results)
    units = local_results.attrs.get('units', {})

    for variable_name, (cmap, paths) in variables_to_plot.items():
        if variable_name == 'vadose_moisture':
            data = local_results['vadose_moisture'].groupby(level='cell').last()
        elif variable_name == 'groundwater':
            data = local_results['groundwater'].groupby(level='cell').last()
        else:
            data = local_results[variable_name].groupby(level='cell').sum()
        data.attrs['unit'] = units.get(variable_name, 'm3')

        output_path = output_dir / f'{variable_name}_map.png'
        plot_variable(background_shapefile, feature_shapefiles, geometry_geopackage,
                      data, variable_name, output_path, cmap, flow_paths=paths)
