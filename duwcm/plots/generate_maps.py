from typing import Dict, List, Any, Optional
from pathlib import Path
from dynaconf import Dynaconf

import numpy as np
import pandas as pd
import pint
import pint_pandas

import geopandas as gpd
import matplotlib.pyplot as plt

from mpl_toolkits.axes_grid1 import make_axes_locatable
from shapely.geometry import LineString

from duwcm.postprocess import extract_local_results

ureg = pint.UnitRegistry()
pint_pandas.PintType.ureg = ureg

def generate_system_maps(background_shapefile: Path, feature_shapefiles: List[Path],
                         geometry_geopackage: Path, flow_paths: pd.DataFrame,
                         output_dir: Path, config: Dynaconf) -> None:
    """Create maps showing cell IDs, elevation and flow paths with background features."""
    gdf_geometry = gpd.read_file(geometry_geopackage)
    gdf_background = gpd.read_file(background_shapefile)
    if gdf_background.crs != gdf_geometry.crs:
        gdf_background = gdf_background.to_crs(gdf_geometry.crs)

    # Get selected cells from config
    selected_cells = getattr(config.grid, 'selected_cells', None)
    if selected_cells is not None:
        selected = gdf_geometry['BlockID'].isin(selected_cells)
    else:
        selected = pd.Series(True, index=gdf_geometry.index)

    # Map 1: Cell IDs
    _, ax1 = plt.subplots(figsize=(12, 10))
    plot_background_map(ax1, gdf_background, feature_shapefiles, gdf_geometry, selected_cells)

    if (~selected).any():
        gdf_geometry[~selected].plot(ax=ax1, color='lightgray', edgecolor='none', alpha=0.2)
    if selected.any():
        gdf_geometry[selected].plot(ax=ax1, color='lightblue', edgecolor='none', alpha=0.3)

    for idx, row in gdf_geometry.iterrows():
        if selected_cells is None or row['BlockID'] in selected_cells:
            centroid = row.geometry.centroid
            ax1.annotate(str(int(row['BlockID'])),
                        (centroid.x, centroid.y),
                        ha='center', va='center',
                        fontsize=8, color='black',
                        bbox={'facecolor': 'white',
                              'edgecolor': 'none',
                              'alpha': 0.4,
                              'pad': 0.5})
    ax1.set_title('Cell IDs')
    ax1.axis('off')
    plt.savefig(output_dir / 'cells_map.png', dpi=300, bbox_inches='tight')
    plt.close()

    # Map 2: Elevation
    _, ax2 = plt.subplots(figsize=(12, 10))
    plot_background_map(ax2, gdf_background, feature_shapefiles, gdf_geometry, selected_cells)

    elevation = gdf_geometry['AvgElev']
    vmin, vmax = elevation.min(), elevation.max()

    if (~selected).any():
        gdf_geometry[~selected].plot(ax=ax2, color='lightgray', alpha=0.2)

    selected_geom = gdf_geometry[selected].copy() if selected.any() else gdf_geometry
    selected_geom.plot(column='AvgElev',
                      ax=ax2,
                      cmap='terrain',
                      alpha=0.7)

    divider = make_axes_locatable(ax2)
    cax = divider.append_axes("right", size="5%", pad=0.1)
    sm = plt.cm.ScalarMappable(cmap='terrain', norm=plt.Normalize(vmin=vmin, vmax=vmax))
    sm.set_array([])
    cbar = plt.colorbar(sm, cax=cax)
    cbar.set_label('Elevation [m]', rotation=270, labelpad=15)

    ax2.set_title('Elevation')
    ax2.axis('off')
    plt.savefig(output_dir / 'elevation_map.png', dpi=300, bbox_inches='tight')
    plt.close()

    # Map 3: Flow paths
    _, ax3 = plt.subplots(figsize=(12, 10))
    plot_background_map(ax3, gdf_background, feature_shapefiles, gdf_geometry, selected_cells)

    if (~selected).any():
        gdf_geometry[~selected].plot(ax=ax3, color='lightgray', edgecolor='none', alpha=0.2)
    if selected.any():
        gdf_geometry[selected].plot(ax=ax3, color='lightblue', edgecolor='none', alpha=0.3)

    # Draw flow paths using plot_linear approach
    cell_data = {row['BlockID']: row for _, row in gdf_geometry.iterrows()}

    for cell_id, row in cell_data.items():
        if selected_cells is None or cell_id in selected_cells:
            downstream_id = flow_paths.loc[cell_id, 'down']
            if downstream_id in cell_data and downstream_id != 0:
                # Get center points
                start_point = row.geometry.centroid
                end_point = cell_data[downstream_id].geometry.centroid
                line = LineString([start_point, end_point])

                # Draw line with arrow
                line_coords = line.xy
                ax3.plot(line_coords[0], line_coords[1],
                        color='red', linewidth=1.5, alpha=0.6)

                # Add arrow
                arrow_pos = 0.5  # Position along the line (0-1)
                arrow_x = line_coords[0][0] + (line_coords[0][1] - line_coords[0][0]) * arrow_pos
                arrow_y = line_coords[1][0] + (line_coords[1][1] - line_coords[1][0]) * arrow_pos
                dx = line_coords[0][1] - line_coords[0][0]
                dy = line_coords[1][1] - line_coords[1][0]
                ax3.arrow(arrow_x, arrow_y, dx*0.1, dy*0.1,
                         head_width=50, head_length=50,
                         fc='red', ec='red', alpha=0.6)

    # Mark outflow cells
    outflow_cells = flow_paths[flow_paths['down'] == 0].index
    for cell_id in outflow_cells:
        if cell_id in cell_data:
            cell = cell_data[cell_id]
            centroid = cell.geometry.centroid
            ax3.plot(centroid.x, centroid.y, 'r*', markersize=15,
                    label='Outflow point' if cell_id == outflow_cells[0] else "")

    if len(outflow_cells) > 0:
        ax3.legend(loc='upper right', bbox_to_anchor=(1.1, 1))

    ax3.set_title('Flow Paths')
    ax3.axis('off')
    plt.savefig(output_dir / 'flow_paths_map.png', dpi=300, bbox_inches='tight')
    plt.close()

def generate_maps(background_shapefile: Path, feature_shapefiles: List[Path],
                  geometry_geopackage: Path, results: Dict[str, pd.DataFrame],
                  output_dir: Path, flow_paths: pd.DataFrame) -> None:
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

    local_results = extract_local_results(results)

    for variable_name, (cmap, paths) in variables_to_plot.items():
        if variable_name == 'vadose_moisture':
            data = local_results['vadose_moisture'].groupby(level='cell').last()
        elif variable_name == 'groundwater':
            data = local_results['groundwater'].groupby(level='cell').last()
        else:
            data = local_results[variable_name].groupby(level='cell').sum()

        output_path = output_dir / f'{variable_name}_map.png'
        plot_variable(background_shapefile, feature_shapefiles, geometry_geopackage,
                      data, variable_name, output_path, cmap, flow_paths=paths)

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
        abs_min, abs_max = min(abs(vmin), abs(vmax)), max(abs(vmin), abs(vmax))
        return np.interp(abs(value), [abs_min, abs_max], [1.5, 5])

    cell_data = {row['BlockID']: row for _, row in gdf_geometry.iterrows()}

    for cell_id, row in cell_data.items():
        if pd.notna(row[variable_name]):
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

    data_values = data.pint.magnitude
    gdf_geometry = gpd.read_file(geometry_geopackage)
    gdf_geometry[variable_name] = gdf_geometry['BlockID'].map(data_values)

    gdf_background = gpd.read_file(background_shapefile)
    if gdf_background.crs != gdf_geometry.crs:
        gdf_background = gdf_background.to_crs(gdf_geometry.crs)

    _, ax = plt.subplots(figsize=(12, 10))
    plot_background_map(ax, gdf_background, feature_shapefiles, gdf_geometry)

    if variable_name in ['stormwater_runoff', 'sewerage_discharge']:
        sm = plot_linear(ax, gdf_geometry, flow_paths, variable_name, cmap)
    else:
        values = gdf_geometry[variable_name].dropna()
        if not values.empty:
            if values.mean() < 0:  # Now working with float values
                cmap = cmap + "_r"

            vmin = values.min()
            vmax = values.max()
            sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=vmin, vmax=vmax))
            sm.set_array([])

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

    # Format label using the pint unit
    unit = data.pint.units
    if unit == ureg.meter**3:
        label = fr'{variable_name.replace("_", " ").capitalize()} [m³/yr]'
    else:
        label = fr'{variable_name.replace("_", " ").capitalize()} [{unit:~P}]'

    divider = make_axes_locatable(ax)
    cax = divider.append_axes("right", size="3%", pad=0.1)
    cbar = plt.colorbar(sm, cax=cax)
    cbar.formatter.set_powerlimits((0, 0))
    cbar.ax.yaxis.set_offset_position('right')
    cbar.ax.yaxis.offsetText.set_fontsize(8)
    cbar.ax.yaxis.offsetText.set_position((0, 1.05))
    cbar.update_ticks()
    cbar.set_label(label, rotation=270, labelpad=15)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()

def plot_background_map(ax: plt.Axes, gdf_background: gpd.GeoDataFrame,
                       feature_shapefiles: List[Path], gdf_geometry: gpd.GeoDataFrame,
                       selected_cells: Optional[List[int]] = None) -> None:
    """Plot background elements for all maps."""
    gdf_background.plot(ax=ax, color='none', edgecolor='gray', alpha=0.8)

    for shapefile in feature_shapefiles:
        gdf_feature = gpd.read_file(shapefile)
        if gdf_feature.crs != gdf_geometry.crs:
            gdf_feature = gdf_feature.to_crs(gdf_geometry.crs)
        if 'Rivers' in str(shapefile):
            gdf_feature.plot(ax=ax, color='dodgerblue', edgecolor='dodgerblue', alpha=0.8, linewidth=1)
        else:
            gdf_feature.plot(ax=ax, color='none', edgecolor='gray', alpha=0.8, linewidth=1)

    if selected_cells is not None:
        selected = gdf_geometry['BlockID'].isin(selected_cells)
        if (~selected).any():
            gdf_geometry[~selected].plot(ax=ax, color='lightgray', edgecolor='none', alpha=0.2)
        if selected.any():
            gdf_geometry[selected].plot(ax=ax, color='lightblue', edgecolor='none', alpha=0.3)
    else:
        gdf_geometry.plot(ax=ax, color='lightblue', edgecolor='none', alpha=0.3)
