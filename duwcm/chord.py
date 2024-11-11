from typing import Dict
import pandas as pd
import holoviews as hv
from holoviews import opts
import colorcet as cc
from duwcm.data_structures import UrbanWaterData

def plot_chord_diagram(results: Dict[str, pd.DataFrame], cell_id: int, timestep: int) -> hv.Chord:
    """
    Create a chord diagram showing water flows between urban water components for a specific cell and timestep.
    
    Args:
        results (Dict[str, pd.DataFrame]): Dictionary containing simulation results for each component
        cell_id (int): ID of the cell to visualize
        timestep (int): Timestep index to visualize

    Returns:
        hv.Chord: Holoviews chord diagram object
    """
    # Initialize holoviews
    hv.extension('bokeh')

    # Get components and connections from UrbanWaterData
    components = UrbanWaterData.COMPONENTS
    flow_connections = UrbanWaterData.FLOW_CONNECTIONS

    # Create color mapping
    colors = cc.glasbey_dark[:len(components)]
    color_dict = dict(zip(components, colors))

    # Create links data for the chord diagram
    links = []
    for (source, target), (source_flow, target_flow) in flow_connections.items():
        try:
            source_data = results[source].xs((cell_id, timestep), level=['cell', 'timestep'])
            if source_flow in source_data:
                flow_value = source_data[source_flow]
                if flow_value > 0:  # Only include non-zero flows
                    links.append((source, target, float(flow_value)))
        except (KeyError, ValueError):
            continue

    # Create the chord diagram
    chord = hv.Chord(links)

    # Style the diagram
    chord.opts(
        opts.Chord(
            cmap='Category20',
            edge_cmap='Category20',
            edge_color=dimension='source',
            node_color=color_dict,
            labels='index',
            node_size=10,
            edge_line_width=2,
            height=600,
            width=600,
            title=f'Water Flows for Cell {cell_id} at Timestep {timestep}',
            tools=['hover']
        )
    )

    return chord