from typing import Dict, List, Optional, Union
from pathlib import Path
import pandas as pd
import geopandas as gpd
import plotly.graph_objects as go

def create_map_base(geometry_geopackage: Path, background_shapefile: Path,
                    flow_paths: pd.DataFrame) -> go.Figure:
    """Create base map with hexagonal grid, background, elevation and flow paths."""
    gdf_geometry = gpd.read_file(geometry_geopackage)
    gdf_background = gpd.read_file(background_shapefile)

    if gdf_geometry.crs != gdf_background.crs:
        gdf_background = gdf_background.to_crs(gdf_geometry.crs)

    gdf_geometry = gdf_geometry.to_crs(epsg=4326)
    gdf_geometry = gdf_geometry.set_crs('EPSG:2056', allow_override=True)
    bounds = gdf_geometry.total_bounds
    center_lon, center_lat = (bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2

    gdf_background = gdf_background.to_crs(epsg=4326)

    fig = go.Figure()

    # Add hexagons for grid view
    fig.add_trace(go.Choroplethmapbox(
        geojson=gdf_geometry.__geo_interface__,
        locations=gdf_geometry.index,
        z=[1]*len(gdf_geometry),
        colorscale=['white', 'lightblue'],
        showscale=False,
        marker_opacity=0.8,
        marker_line_width=0.6,
        marker_line_color='lightblue',
        visible=True,
        name='Grid',
        selected={"marker": {"opacity": 1}},
        unselected={"marker": {"opacity": 0.6}},
        selectedpoints=[]
    ))

    # Add hexagons colored by elevation
    fig.add_trace(go.Choroplethmapbox(
        geojson=gdf_geometry.__geo_interface__,
        locations=gdf_geometry.index,
        z=gdf_geometry['AvgElev'],
        colorscale='viridis',
        showscale=True,
        marker_opacity=0.7,
        marker_line_width=0.5,
        colorbar_title="Elevation [m]",
        visible=False,
        name='Elevation'
    ))

    # Add flow paths
    lines_lons = []
    lines_lats = []

    cell_data = {row['BlockID']: row for _, row in gdf_geometry.iterrows()}
    for cell_id, row in cell_data.items():
        downstream_id = flow_paths.loc[cell_id, 'down']
        if downstream_id in cell_data and downstream_id != 0:
            start_point = row.geometry.centroid
            end_point = cell_data[downstream_id].geometry.centroid

            # Add to lines
            lines_lons.extend([start_point.x, end_point.x, None])
            lines_lats.extend([start_point.y, end_point.y, None])

    # Add single trace for all flow paths
    fig.add_trace(go.Scattermapbox(
        lon=lines_lons,
        lat=lines_lats,
        mode='lines',
        line={"width": 2, "color": 'red'},
        showlegend=True,
        visible=False,
        name='Flow Paths'
    ))

    # Add outlets with larger markers
    outflow_cells = gdf_geometry[gdf_geometry['BlockID'].isin(flow_paths[flow_paths['down'] == 0].index)]
    outflow_centroids = outflow_cells.geometry.centroid
    fig.add_trace(go.Scattermapbox(
        lon=outflow_centroids.x.tolist(),
        lat=outflow_centroids.y.tolist(),
        mode='markers',
        marker={"size": 15, "color": 'blue'},
        name='Outlets',
        visible=False,
        showlegend=True
    ))

    # Add background outline
    for _, row in gdf_background.iterrows():
        coords = _get_polygon_coordinates(row.geometry)
        for polygon in coords:
            lons, lats = zip(*polygon)
            fig.add_trace(go.Scattermapbox(
                lon=list(lons),
                lat=list(lats),
                mode='lines',
                line={"width": 1, "color": 'gray'},
                showlegend=False
            ))

    updatemenus = [{
        "type": "buttons",
        "direction": "right",
        "x": 0.1,
        "y": 1.1,
        "showactive": True,
        "buttons": [
            {
                "label": "Grid",
                "method": "update",
                "args": [{"visible": [True] + [False] * (len(fig.data)-1)},
                        {"showscale": False}]
            },
            {
                "label": "Elevation",
                "method": "update",
                "args": [{"visible": [False, True] + [False] * (len(fig.data)-2)},
                        {"showscale": True}]
            },
            {
                "label": "Flow Paths",
                "method": "update",
                "args": [{"visible": [False, False] + [True] * (len(fig.data)-2)},
                        {"showscale": False}]
            }
        ]
    }]

    fig.update_layout(
        mapbox_style="carto-positron",
        mapbox={
            "center": {"lat": center_lat, "lon": center_lon},
            "zoom": 10
        },
        updatemenus=updatemenus,
        margin={"r":0,"t":45,"l":0,"b":0},
        height=700
    )

    return fig

def create_dynamic_map(gdf_geometry: gpd.GeoDataFrame, background_shapefile: Path,
                       variables: List[str], time_series_data: pd.DataFrame) -> go.Figure:
    """Create interactive map with time slider and variable selector."""
    gdf_geometry = gdf_geometry.set_index('BlockID')
    gdf_geometry = gdf_geometry.to_crs(epsg=4326)
    bounds = gdf_geometry.total_bounds
    center_lon, center_lat = (bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2

    monthly_data = time_series_data.groupby(pd.Grouper(freq='ME')).mean()

    # Calculate absolute global min/max across ALL variables
    global_min = monthly_data[variables].min().min()  # Min across all variables
    global_max = monthly_data[variables].max().max()  # Max across all variables
    var_min = {var: monthly_data[var].min().min() for var in variables}
    var_max = {var: monthly_data[var].max().max() for var in variables}

    fig = go.Figure()

    gdf_background = gpd.read_file(background_shapefile)
    if gdf_geometry.crs != gdf_background.crs:
        gdf_background = gdf_background.to_crs(gdf_geometry.crs)
    gdf_background = gdf_background.to_crs(epsg=4326)


    # Create traces for each variable
    for variable in variables:
        fig.add_trace(go.Choroplethmapbox(
            geojson=gdf_geometry.__geo_interface__,
            locations=time_series_data.columns.get_level_values(1),
            z=monthly_data.loc[monthly_data.index[0], variable],
            zmin=var_min[variable],
            zmax=var_max[variable],
            colorscale="Viridis",
            marker_opacity=0.7,
            marker_line_width=0,
            colorbar_title_text=f"{variable.replace('_', ' ').capitalize()} [m³/yr]",
            colorbar_title_side="right",
            colorbar_thickness=20,
            colorbar_title_font={"size": 12},
            visible=variable == variables[0],
            name=variable
        ))

    # Add background outline
    for _, row in gdf_background.iterrows():
        coords = _get_polygon_coordinates(row.geometry)
        for polygon in coords:
            lons, lats = zip(*polygon)
            fig.add_trace(go.Scattermapbox(
                lon=list(lons),
                lat=list(lats),
                mode='lines',
                line={"width": 1, "color": 'gray'},
                showlegend=False
            ))

    # Create variable buttons that preserve the current zmin/zmax setting
    var_buttons = []
    for i, variable in enumerate(variables):
        var_buttons.append({
            'args': [{"visible": [i == j for j in range(len(variables))],
                     "colorbar_title_text": f"{variable.replace('_', ' ').capitalize()} [m³/yr]"}],
            'label': variable.replace('_', ' ').capitalize(),
            'method': "update"
        })

    # Scale buttons now need to handle all variables
    scale_buttons = [
        {
            'args': [{"zmin": [var_min[var] for var in variables],
                     "zmax": [var_max[var] for var in variables]}],
            'label': "Local Scale",
            'method': "restyle"
        },
        {
            'args': [{"zmin": [global_min for _ in variables],
                     "zmax": [global_max for _ in variables]}],
            'label': "Global Scale",
            'method': "restyle"
        }
    ]

    # Update layout
    fig.update_layout(
        mapbox_style="carto-positron",
        mapbox={"center": {"lat": center_lat, "lon": center_lon}, "zoom": 11},
        updatemenus=[
            {
                'buttons': var_buttons,
                'direction': "down",
                'showactive': True,
                'x': 0.1,
                'y': 1.1,
                'xanchor': "left",
                'yanchor': "top"
            },
            {
                'buttons': scale_buttons,
                'direction': "down",
                'showactive': True,
                'x': 0.3,
                'y': 1.1,
                'xanchor': "left",
                'yanchor': "top"
            }
        ],
        sliders=[{
            'active': 0,
            'currentvalue': {"prefix": "Month: ", "offset": 20},
            'pad': {"b": 10, "t": 50},
            'len': 0.875,
            'x': 0.0625,
            'xanchor': "left",
            'y': 0,
            'yanchor': "top",
            'steps': [{
                'method': 'update',
                'args': [{'z': [monthly_data.loc[month_end, var] for var in variables]}],
                'label': month_end.strftime('%Y-%m')
            } for month_end in monthly_data.index]
        }],
        margin={"r":0, "t":45, "l":0, "b":120},
        height=700
    )

    return fig

def _get_polygon_coordinates(polygon):
    """Extract coordinates from a polygon geometry."""
    if polygon.geom_type == 'Polygon':
        return [list(polygon.exterior.coords)]
    if polygon.geom_type == 'MultiPolygon':
        return [list(geom.exterior.coords) for geom in polygon.geoms]
    return []
