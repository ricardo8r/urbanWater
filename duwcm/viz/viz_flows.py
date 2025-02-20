from typing import Dict, List, Optional, Union
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import holoviews as hv
from holoviews import opts, dim

from duwcm.data_structures import UrbanWaterData
from duwcm.diagnostics import DiagnosticTracker
from duwcm.postprocess import calculate_flow_matrix, calculate_reuse_flow_matrix

def create_flows(results: Dict[str, pd.DataFrame],
                            viz_type: str = 'sankey') -> Union[go.Figure, hv.Element]:
    """Create flow visualization (Sankey or Chord) of water flows between components."""

    flow_matrix = calculate_flow_matrix(results)

    if viz_type == 'sankey':
        return _create_sankey_diagram(flow_matrix)
    if viz_type == 'chord':
        return _create_chord_diagram(flow_matrix)

def create_reuse_flows(results: Dict[str, pd.DataFrame],
                            viz_type: str = 'sankey') -> Union[go.Figure, hv.Element]:
    """Create flow visualization (Sankey or Chord) of water flows for demand/reuse."""

    flow_matrix = calculate_reuse_flow_matrix(results)

    if viz_type == 'sankey':
        return _create_sankey_diagram(flow_matrix)
    if viz_type == 'chord':
        return _create_chord_diagram(flow_matrix)


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

def create_cell_flows(cell_id: int, tracker: DiagnosticTracker) -> tuple[go.Figure, go.Figure]:
    """Create internal and external flow diagrams for a cell."""
    internal_matrix = tracker.get_internal_flow_matrix(cell_id=cell_id)
    external_matrix = tracker.get_external_flow_matrix(cell_id=cell_id)

    internal_fig = _create_sankey_diagram(internal_matrix)
    external_fig = _create_sankey_diagram(external_matrix)

    internal_fig.update_layout(title=f"Cell {cell_id} - Internal Flows")
    external_fig.update_layout(title=f"Cell {cell_id} - External Flows")

    return internal_fig, external_fig
