from pathlib import Path
from typing import Dict
import pandas as pd

import matplotlib.pyplot as plt
from sankeyflow import Sankey
import networkx as nx

from duwcm.data_structures import UrbanWaterData

def generate_sankey(results: Dict[str, pd.DataFrame], output_dir: Path) -> None:
    """Generate a Sankey diagram showing accumulated water flows between components."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Set up flow tuples list for Sankey diagram
    flows = []

    # Process precipitation inflows
    for comp in ['roof', 'pavement', 'pervious', 'raintank', 'stormwater']:
        if comp in results:
            flow_value = results[comp]['precipitation'].sum() * 0.001
            if flow_value > 0:
                flows.append(('Precipitation', comp.capitalize(), float(flow_value)))

    # Process irrigation and imported water
    for comp in ['roof', 'pavement', 'pervious']:
        if comp in results:
            flow_value = results[comp]['irrigation'].sum() * 0.001
            if flow_value > 0:
                flows.append(('Irrigation', comp.capitalize(), float(flow_value)))

    # Process component-to-component flows from FLOW_CONNECTIONS
    for (src_comp, source_flow), (trg_comp, target_flow) in UrbanWaterData.FLOW_CONNECTIONS.items():
        try:
            if src_comp in results and trg_comp in results:
                flow_value = results[src_comp][source_flow].sum() * 0.001
                if flow_value > 0:
                    flows.append((src_comp.capitalize(), trg_comp.capitalize(), float(flow_value)))
        except (KeyError, ValueError) as e:
            print(f"Error processing {src_comp} -> {trg_comp}: {e}")
            continue

    # Process evaporation outflows
    for comp in ['roof', 'pavement', 'pervious', 'raintank', 'stormwater']:
        if comp in results:
            flow_value = results[comp]['evaporation'].sum() * 0.001
            if flow_value > 0:
                flows.append((comp.capitalize(), 'Evaporation', float(flow_value)))

    # Process transpiration
    if 'vadose' in results:
        flow_value = results['vadose']['transpiration'].sum() * 0.001
        if flow_value > 0:
            flows.append(('Vadose', 'Transpiration', float(flow_value)))

    # Process baseflow and seepage
    if 'groundwater' in results:
        baseflow = results['groundwater']['baseflow'].sum() * 0.001
        seepage = results['groundwater']['seepage'].sum() * 0.001
        if baseflow > 0:
            flows.append(('Groundwater', 'Baseflow', float(abs(baseflow))))
        if seepage > 0:
            flows.append(('Groundwater', 'Deep Seepage', float(seepage)))

    # Create and save the Sankey diagram
    plt.figure(figsize=(20, 10), dpi=144)
    print(flows)
    sankey = Sankey(flows=flows, flow_color_mode='source')
    sankey.draw()
    plt.show()

    filename = output_dir / 'sankey.png'
    plt.savefig(filename, bbox_inches='tight')
    plt.close()

def generate_flow_network(results: Dict[str, pd.DataFrame], output_dir: Path) -> None:
    """Generate a directed graph showing water flows between components."""
    import networkx as nx
    import matplotlib.pyplot as plt
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create directed graph
    G = nx.DiGraph()
    
    # Define node positions for better layout
    pos = {
        'Precipitation': (0, 0.8),
        'Imported Water': (0, 0.4),
        'Irrigation': (0, 0),
        'Roof': (0.25, 0.9),
        'Raintank': (0.25, 0.7),
        'Pavement': (0.25, 0.5),
        'Pervious': (0.25, 0.3),
        'Vadose': (0.5, 0.4),
        'Groundwater': (0.75, 0.4),
        'Stormwater': (0.5, 0.7),
        'Wastewater': (0.75, 0.7),
        'Demand': (0.5, 0.1),
        'Evaporation': (1, 0.8),
        'Transpiration': (1, 0.6),
        'Baseflow': (1, 0.4),
        'Deep Seepage': (1, 0.2),
    }
    
    # Add nodes
    for node, (x, y) in pos.items():
        G.add_node(node, pos=(x, y))
    
    # Add edges with weights
    edges = []
    
    # Process precipitation inflows
    for comp in ['roof', 'pavement', 'pervious', 'raintank', 'stormwater']:
        if comp in results:
            flow_value = results[comp]['precipitation'].sum() * 0.001
            if flow_value > 0:
                edges.append(('Precipitation', comp.capitalize(), flow_value))
    
    # Process component-to-component flows
    for (src_comp, source_flow), (trg_comp, target_flow) in UrbanWaterData.FLOW_CONNECTIONS.items():
        try:
            if src_comp in results and trg_comp in results:
                flow_value = results[src_comp][source_flow].sum() * 0.001
                if flow_value > 0:
                    edges.append((src_comp.capitalize(), trg_comp.capitalize(), flow_value))
        except (KeyError, ValueError):
            continue
    
    # Process evaporation and other outflows
    for comp in ['roof', 'pavement', 'pervious', 'raintank', 'stormwater']:
        if comp in results:
            flow_value = results[comp]['evaporation'].sum() * 0.001
            if flow_value > 0:
                edges.append((comp.capitalize(), 'Evaporation', flow_value))
    
    # Add vadose transpiration
    if 'vadose' in results:
        flow_value = results['vadose']['transpiration'].sum() * 0.001
        if flow_value > 0:
            edges.append(('Vadose', 'Transpiration', flow_value))
    
    # Add groundwater flows
    if 'groundwater' in results:
        baseflow = abs(results['groundwater']['baseflow'].sum() * 0.001)
        seepage = results['groundwater']['seepage'].sum() * 0.001
        if baseflow > 0:
            edges.append(('Groundwater', 'Baseflow', baseflow))
        if seepage > 0:
            edges.append(('Groundwater', 'Deep Seepage', seepage))
    
    # Add edges to graph
    for source, target, weight in edges:
        G.add_edge(source, target, weight=weight)
    
    # Create the visualization
    plt.figure(figsize=(15, 10))
    
    # Draw the network
    pos_nodes = nx.get_node_attributes(G, 'pos')
    
    # Draw nodes
    nx.draw_networkx_nodes(G, pos_nodes, node_color='lightblue', 
                          node_size=2000, alpha=0.7)
    
    # Draw edges with width proportional to weight
    edge_weights = [G[u][v]['weight'] for u, v in G.edges()]
    max_weight = max(edge_weights)
    edge_widths = [2 + 8 * (w / max_weight) for w in edge_weights]
    
    nx.draw_networkx_edges(G, pos_nodes, edge_color='gray',
                          width=edge_widths, alpha=0.6,
                          arrowsize=20)
    
    # Add labels
    nx.draw_networkx_labels(G, pos_nodes, font_size=10)
    
    # Add edge labels (flow values)
    edge_labels = {(u, v): f'{G[u][v]["weight"]:.1f}' 
                  for u, v in G.edges()}
    nx.draw_networkx_edge_labels(G, pos_nodes, edge_labels, 
                                font_size=8)
    
    plt.title('Urban Water Flow Network')
    plt.axis('off')
    
    # Save the figure
    filename = output_dir / 'flow_network.png'
    plt.savefig(filename, bbox_inches='tight', dpi=300)
    plt.close()
