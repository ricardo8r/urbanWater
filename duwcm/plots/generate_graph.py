from pathlib import Path
from typing import Dict
import pandas as pd

import matplotlib.pyplot as plt
import networkx as nx

from duwcm.data_structures import UrbanWaterData
from duwcm.postprocess import calculate_flow_matrix

def generate_graph(results: Dict[str, pd.DataFrame], output_dir: Path) -> None:
    """Generate a directed graph showing water flows between components."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Define node positions with lowercase keys to match flow matrix
    pos = {
        'precipitation': (0, 0.8),
        'imported': (0, 0.4),
        'irrigation': (0, 0),
        'roof': (0.25, 0.9),
        'raintank': (0.25, 0.7),
        'impervious': (0.25, 0.5),
        'pervious': (0.25, 0.3),
        'vadose': (0.5, 0.4),
        'groundwater': (0.75, 0.4),
        'stormwater': (0.5, 0.7),
        'sewerage': (0.75, 0.7),
        'demand': (0.5, 0.1),
        'evaporation': (1, 0.8),
        'transpiration': (1, 0.6),
        'baseflow': (1, 0.4),
        'seepage': (1, 0.2),
        'runoff': (0.75,0.8)
    }

    flow_matrix = calculate_flow_matrix(results)

    # Create directed graph
    graph = nx.DiGraph()

    # Add nodes
    for node, (x, y) in pos.items():
        if node in flow_matrix.index:
            graph.add_node(node, pos=(x, y))

    # Add edges from flow matrix
    for source in flow_matrix.index:
        for target in flow_matrix.columns:
            flow_value = flow_matrix.loc[source, target]
            if flow_value > 0:
                graph.add_edge(source, target, weight=flow_value)

    plt.figure(figsize=(15, 10))
    pos_nodes = nx.get_node_attributes(graph, 'pos')

    # Draw nodes
    nx.draw_networkx_nodes(graph, pos_nodes, node_color='lightblue',
                          node_size=2000, alpha=0.7)

    # Draw edges
    edge_weights = [graph[u][v]['weight'] for u, v in graph.edges()]
    max_weight = max(edge_weights) if edge_weights else 1
    edge_widths = [2 + 8 * (w / max_weight) for w in edge_weights]

    nx.draw_networkx_edges(graph, pos_nodes, edge_color='gray',
                          width=edge_widths, alpha=0.6,
                          arrowsize=20)

    # Add labels with capitalized first letter for display
    labels = {node: node.capitalize() for node in graph.nodes()}
    nx.draw_networkx_labels(graph, pos_nodes, labels, font_size=10)

    # Format edge labels with proper capitalization
    edge_labels = {(u, v): f'{graph[u][v]["weight"]:.1f}'
                  for u, v in graph.edges()}
    nx.draw_networkx_edge_labels(graph, pos_nodes, edge_labels,
                                font_size=8)

    plt.title('Urban Water Flow Network')
    plt.axis('off')

    filename = output_dir / 'flow_network.png'
    plt.savefig(filename, bbox_inches='tight', dpi=300)
    plt.close()
