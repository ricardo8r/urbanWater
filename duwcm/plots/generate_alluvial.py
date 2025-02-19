from pathlib import Path
from typing import Dict
import pandas as pd
import plotly.graph_objects as go

from duwcm.diagnostics import DiagnosticTracker
from duwcm.postprocess import (calculate_flow_matrix,
                               calculate_reuse_flow_matrix
                               )

def generate_alluvial_total(results: Dict[str, pd.DataFrame], output_dir: Path) -> None:
    """Generate total alluvial diagram."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get nodes and calculate flow matrix
    flow_matrix = calculate_flow_matrix(results)
    fig = generate_alluvial(flow_matrix)
    fig.write_image(output_dir / "sankey.png", scale=2)


def generate_alluvial_reuse(results: Dict[str, pd.DataFrame], output_dir: Path) -> None:
    """Generate an alluvial diagram for reuse."""
    output_dir.mkdir(parents=True, exist_ok=True)

    flow_matrix = calculate_reuse_flow_matrix(results)
    fig = generate_alluvial(flow_matrix)
    fig.write_image(output_dir / "reuse_sankey.png", scale=2)

def generate_alluvial(flow_matrix: pd.DataFrame) -> go.Figure:
    """Generate an alluvial diagram."""
    # Prepare Sankey data
    source, target, value = [], [], []
    node_labels = list(flow_matrix.index)
    node_map = {name: idx for idx, name in enumerate(node_labels)}

    # Create links from flow matrix
    for source_name in flow_matrix.index:
        for target_name in flow_matrix.columns:
            flow_value = flow_matrix.loc[source_name, target_name]
            if flow_value > 0:
                source.append(node_map[source_name])
                target.append(node_map[target_name])
                value.append(flow_value)

    # Create Sankey diagram
    fig = go.Figure(data=[go.Sankey(
        arrangement="snap",
        node={
            "pad": 15,
            "thickness": 20,
            "line": {"color": 'black', "width": 0.5},
            "label": node_labels,
            "customdata": node_labels,
        },
        link={
            "source": source,
            "target": target,
            "value": value
        }
    )])

    # Update layout
    fig.update_layout(
        title_text="Urban Water Flows (m³/year)",
        title_x=0.5,
        font_size=10,
        height=400,
        plot_bgcolor='white',
        paper_bgcolor='white'
    )

    return fig
