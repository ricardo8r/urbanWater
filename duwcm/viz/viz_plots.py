from typing import Dict, List, Optional, Union
import pandas as pd
import plotly.graph_objects as go

def plot_aggregated_results(aggregated_results: pd.DataFrame, forcing: pd.DataFrame) -> go.Figure:
    """Create interactive plot with legend toggles for each data series."""

    plot_data = pd.DataFrame({
        'Precipitation': forcing['precipitation'],
        'Potential Evaporation': forcing['potential_evaporation'],
        'Evapotranspiration': (aggregated_results['evaporation'] +
                               aggregated_results['transpiration']),
        'Stormwater': aggregated_results['stormwater'],
        'Baseflow': aggregated_results['baseflow'],
        'Wastewater': aggregated_results['wastewater']
    })

    colors = {
        'Precipitation': 'lightblue',
        'Potential Evaporation': 'purple',
        'Evapotranspiration': 'green',
        'Stormwater': 'orange',
        'Baseflow': 'red',
        'Wastewater': 'brown'
    }

    fig = go.Figure()

    # Add precipitation (always visible)
    fig.add_trace(go.Scatter(
        x=plot_data.index,
        y=plot_data['Precipitation'],
        name='Precipitation',
        fill='tozeroy',
        line={"color": colors['Precipitation']},
    ))

    # Add other traces
    variables = list(plot_data.columns[1:])
    for var in variables:
        fig.add_trace(go.Scatter(
            x=plot_data.index,
            y=plot_data[var],
            name=var,
            line={"color": colors[var], "dash": 'dash' if var == 'Potential Evaporation' else 'solid'},
            yaxis='y2' if var not in ['Evapotranspiration', 'Potential Evaporation'] else 'y',
        ))

    fig.update_layout(
        yaxis={"title": "Precipitation & Evapotranspiration [mm/day]", "autorange": "reversed"},
        yaxis2={"title": "Flow [m³/day]", "overlaying": "y", "side": "right"},
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