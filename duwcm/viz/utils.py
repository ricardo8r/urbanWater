from typing import Dict, List, Optional, Union
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd
import plotly.graph_objects as go
import holoviews as hv
from holoviews import opts, dim

from duwcm.data_structures import UrbanWaterData

def plot_aggregated_results(aggregated_results: pd.DataFrame, forcing: pd.DataFrame) -> go.Figure:
    """Create interactive plot of aggregated results with dropdown menu."""
    plot_configs = ['Evapotranspiration', 'Stormwater', 'Baseflow', 'Wastewater']
    variable_colors = {
        'Evapotranspiration': 'green',
        'Stormwater': 'orange',
        'Baseflow': 'red',
        'Wastewater': 'brown'
    }

    total_area = aggregated_results.attrs['total_area']

    plot_data = pd.DataFrame({
        'Precipitation': forcing['precipitation'],
        'Evaporation': forcing['potential_evaporation'],
        'Evapotranspiration': (aggregated_results['evaporation'] + aggregated_results['transpiration']) / total_area,
        'Stormwater': aggregated_results['stormwater'] / total_area,
        'Baseflow': aggregated_results['baseflow'] / total_area,
        'Wastewater': aggregated_results['wastewater'] / total_area
    })

    fig = go.Figure()

    for i, config in enumerate(plot_configs):
        # Add precipitation trace
        fig.add_trace(go.Scatter(
            x=plot_data.index,
            y=plot_data['Precipitation'],
            name='Precipitation',
            fill='tozeroy',
            line={"color": 'lightblue'},
            visible=False
        ))

        # Add specific traces based on configuration
        if config == 'Evapotranspiration':
            fig.add_trace(go.Scatter(
                x=plot_data.index,
                y=plot_data['Evaporation'],
                name='Potential Evaporation',
                line={"color": 'purple', "dash": 'dash'},
                yaxis='y2',
                visible=False
            ))
        else:
            fig.add_trace(go.Scatter(
                x=plot_data.index,
                y=plot_data['Evapotranspiration'],
                name='Evapotranspiration',
                line={"color": 'green', "dash": 'dash'},
                visible=False
            ))

        fig.add_trace(go.Scatter(
            x=plot_data.index,
            y=plot_data[config],
            name=config,
            line={"color": variable_colors[config]},
            yaxis='y2',
            visible=False
        ))

    # Make first set visible
    for i in range(3):
        fig.data[i].visible = True

    # Create dropdown menu
    dropdown_buttons = [{
        'label': config,
        'method': 'update',
        'args': [
            {'visible': [j in range(i*3, (i+1)*3) for j in range(len(fig.data))]},
            {'yaxis.title.text': 'Precipitation & Evapotranspiration [mm/day]',
             'yaxis2.title.text': f"{config} [mm/day]"}
        ]
    } for i, config in enumerate(plot_configs)]

    fig.update_layout(
        updatemenus=[{
            'active': 0,
            'buttons': dropdown_buttons,
            'direction': "down",
            'pad': {"r": 10, "t": 10},
            'showactive': True,
            'x': 0.1,
            'xanchor': "left",
            'y': 1.15,
            'yanchor': "top"
        }],
        yaxis={"title": 'Precipitation & Evapotranspiration [mm/day]'},
        yaxis2={"overlaying": 'y', "side": 'right'},
        height=600,
        hovermode='x unified',
        legend={
            "orientation": 'h',
            "yanchor": 'bottom',
            "y": 1.02,
            "xanchor": 'right',
            "x": 1
        }
    )

    return fig

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

def create_flow_visualization(results: Dict[str, pd.DataFrame],
                            viz_type: str = 'sankey') -> Union[go.Figure, hv.Element]:
    """Create flow visualization (Sankey or Chord) of water flows between components."""
    nodes = (['imported', 'precipitation', 'irrigation'] +
             UrbanWaterData.COMPONENTS +
             ['seepage', 'baseflow', 'evaporation'])

    flow_matrix = _calculate_flow_matrix(results, nodes)

    if viz_type == 'sankey':
        return _create_sankey_diagram(flow_matrix)
    if viz_type == 'chord':
        return _create_chord_diagram(flow_matrix)

def _get_polygon_coordinates(polygon):
    """Extract coordinates from a polygon geometry."""
    if polygon.geom_type == 'Polygon':
        return [list(polygon.exterior.coords)]
    if polygon.geom_type == 'MultiPolygon':
        return [list(geom.exterior.coords) for geom in polygon.geoms]
    return []

def _calculate_flow_matrix(results: Dict[str, pd.DataFrame], nodes: List[str]) -> pd.DataFrame:
    """Calculate flow matrix between components."""
    flow_matrix = pd.DataFrame(0, index=nodes, columns=nodes, dtype=float)

    # Process component connections
    for (src_comp, source_flow), (trg_comp, target_flow) in UrbanWaterData.FLOW_CONNECTIONS.items():
        if src_comp in UrbanWaterData.COMPONENTS and trg_comp in UrbanWaterData.COMPONENTS:
            flow_value = results[src_comp][source_flow].sum() * 0.001
            if flow_value > 0:
                flow_matrix.loc[src_comp, trg_comp] = float(flow_value)

    # Add precipitation flows
    for comp in ['roof', 'pavement', 'pervious', 'raintank', 'stormwater']:
        if comp in results:
            flow_value = results[comp]['precipitation'].sum() * 0.001
            if flow_value > 0:
                flow_matrix.loc['precipitation', comp] = float(flow_value)

    # Add irrigation flows
    for comp in ['roof', 'pavement', 'pervious']:
        if comp in results:
            flow_value = results[comp]['irrigation'].sum() * 0.001
            if flow_value > 0:
                flow_matrix.loc['irrigation', comp] = float(flow_value)

    # Add evaporation flows
    for comp in ['roof', 'pavement', 'pervious', 'raintank', 'stormwater']:
        if comp in results:
            flow_value = results[comp]['evaporation'].sum() * 0.001
            if flow_value > 0:
                flow_matrix.loc[comp, 'evaporation'] = float(flow_value)

    # Add transpiration
    if 'vadose' in results:
        flow_value = results['vadose']['transpiration'].sum() * 0.001
        if flow_value > 0:
            flow_matrix.loc['vadose', 'evaporation'] = float(flow_value)

    # Add imported water flows
    if 'demand' in results:
        flow_value = results['demand']['imported_water'].sum() * 0.001
        if flow_value > 0:
            flow_matrix.loc['imported', 'demand'] = float(flow_value)

    # Add baseflow and seepage
    if 'groundwater' in results:
        flow_value = results['groundwater']['seepage'].sum() * 0.001
        if flow_value > 0:
            flow_matrix.loc['groundwater', 'seepage'] = float(flow_value)
        elif flow_value < 0:
            flow_matrix.loc['seepage', 'groundwater'] = abs(float(flow_value))

        flow_value = results['groundwater']['baseflow'].sum() * 0.001
        if flow_value > 0:
            flow_matrix.loc['groundwater', 'baseflow'] = float(flow_value)
        elif flow_value < 0:
            flow_matrix.loc['baseflow', 'groundwater'] = abs(float(flow_value))

    # Remove empty rows/columns
    non_zero_mask = (flow_matrix.sum(axis=0) != 0) | (flow_matrix.sum(axis=1) != 0)
    return flow_matrix.loc[non_zero_mask, non_zero_mask]

def _create_sankey_diagram(flow_matrix: pd.DataFrame) -> go.Figure:
    """Create Sankey diagram from flow matrix."""
    # Prepare data for Sankey diagram
    source, target, value = [], [], []
    for i in flow_matrix.index:
        for j in flow_matrix.columns:
            if flow_matrix.loc[i,j] > 0:
                source.append(i)
                target.append(j)
                value.append(flow_matrix.loc[i,j])

    # Create Sankey diagram
    fig = go.Figure(data=[go.Sankey(
        arrangement = "snap",
        node = {
            'label': list(flow_matrix.index),
            'pad': 15,
            'thickness': 20
        },
        link = {
            'source': [flow_matrix.index.get_loc(s) for s in source],
            'target': [flow_matrix.index.get_loc(t) for t in target],
            'value': value
        }
    )])

    fig.update_layout(
        title="Water Flow Diagram (m³/year)",
        font_size=10,
        height=800
    )

    return fig

def _create_chord_diagram(flow_matrix: pd.DataFrame) -> hv.Element:
    """Create Chord diagram from flow matrix."""
    # Prepare data for chord diagram
    flow_data = []
    nodes_data = []
    node_map = {name: i for i, name in enumerate(flow_matrix.index)}

    # Create nodes dataset
    for name in flow_matrix.index:
        nodes_data.append({'ID': node_map[name], 'Name': name})

    # Create flows dataset
    for i in flow_matrix.index:
        for j in flow_matrix.columns:
            if flow_matrix.loc[i,j] > 0:
                flow_data.append({
                    'Source': node_map[i],
                    'Target': node_map[j],
                    'Value': np.log10(flow_matrix.loc[i,j] + 1e-10)
                })

    # Create holoviews datasets
    flows_ds = hv.Dataset(pd.DataFrame(flow_data), ['Source', 'Target'], 'Value')
    nodes_ds = hv.Dataset(pd.DataFrame(nodes_data), 'ID', 'Name')

    # Create chord diagram
    chord = hv.Chord((flows_ds, nodes_ds)).opts(
        opts.Chord(
            cmap='Category20',
            edge_cmap='Category20',
            edge_color=dim('Source').str(),
            node_color=dim('ID').str(),
            labels='Name',
            height=800,
            width=800,
            title='Water Flow Diagram (log₁₀ m³/year)'
        )
    )

    return chord