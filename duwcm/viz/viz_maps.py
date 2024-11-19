from typing import Dict, List, Optional, Union
from pathlib import Path
import pandas as pd
import geopandas as gpd
import plotly.graph_objects as go

def create_map_base(geometry_geopackage: Path, background_shapefile: Path) -> go.Figure:
    """Create base map with hexagonal grid and background."""
    gdf_geometry = gpd.read_file(geometry_geopackage)
    gdf_background = gpd.read_file(background_shapefile)

    if gdf_geometry.crs != gdf_background.crs:
        gdf_background = gdf_background.to_crs(gdf_geometry.crs)

    # Project and get center
    gdf_background_projected = gdf_background.to_crs(epsg=3857)
    centroid_projected = gdf_background_projected.geometry.centroid
    centroid = centroid_projected.to_crs(epsg=4326)

    # Convert to WGS84
    gdf_geometry = gdf_geometry.to_crs(epsg=4326)
    gdf_background = gdf_background.to_crs(epsg=4326)

    fig = go.Figure()

    # Add hexagons
    fig.add_trace(go.Choroplethmapbox(
        geojson=gdf_geometry.__geo_interface__,
        locations=gdf_geometry.index,
        z=[1]*len(gdf_geometry),
        colorscale=['white', 'lightblue'],
        showscale=False,
        marker_opacity=0.5,
        marker_line_width=0.6,
        marker_line_color='lightblue'
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

    # Calculate bounds and center
    bounds = gdf_background.total_bounds
    center_lon, center_lat = (bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2

    fig.update_layout(
        mapbox_style="carto-positron",
        mapbox={
            "bearing": 0,
            "center": {"lat": center_lat, "lon": center_lon},
            "pitch": 0,
            "zoom": 10
        },
        margin={"r":0,"t":0,"l":0,"b":0}
    )

    return fig

def create_dynamic_map(gdf: gpd.GeoDataFrame, variables: List[str],
                      time_series_data: pd.DataFrame) -> go.Figure:
    """Create interactive map with time slider and variable selector."""
    gdf_wgs84 = gdf.to_crs(epsg=4326)
    bounds = gdf_wgs84.total_bounds
    center_lon, center_lat = (bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2

    monthly_data = time_series_data.groupby(pd.Grouper(freq='ME')).mean()
    global_min = {var: monthly_data[var].min().min() for var in variables}
    global_max = {var: monthly_data[var].max().max() for var in variables}

    fig = go.Figure()

    for variable in variables:
        fig.add_trace(go.Choroplethmapbox(
            geojson=gdf_wgs84.__geo_interface__,
            locations=gdf_wgs84.index,
            z=monthly_data.loc[monthly_data.index[0], variable],
            zmin=global_min[variable],
            zmax=global_max[variable],
            colorscale="Viridis",
            marker_opacity=0.7,
            marker_line_width=0,
            colorbar_title_text=f"{variable.replace('_', ' ').capitalize()} [ML/yr]",
            colorbar_title_side="right",
            colorbar_thickness=20,
            colorbar_title_font={"size": 12},
            visible=variable == variables[0],
            name=variable
        ))

    # Add slider and dropdown
    sliders = [{
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
    }]

    dropdown_buttons = [{
        'args': [{"visible": [i == j for j in range(len(variables))],
                 "colorbar_title_text": f"{variable.replace('_', ' ').capitalize()} [ML/yr]"}],
        'label': variable.replace('_', ' ').capitalize(),
        'method': "update"
    } for i, variable in enumerate(variables)]

    fig.update_layout(
        mapbox_style="carto-positron",
        mapbox={"center": {"lat": center_lat, "lon": center_lon}, "zoom": 11},
        updatemenus=[{
            'buttons': dropdown_buttons,
            'direction': "down",
            'pad': {"r": 10, "t": 10},
            'showactive': True,
            'x': 0.1,
            'xanchor': "left",
            'y': 1.1,
            'yanchor': "top"
        }],
        sliders=sliders,
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
