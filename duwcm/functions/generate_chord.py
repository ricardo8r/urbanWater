from pathlib import Path
from typing import Dict
import numpy as np
import pandas as pd
from pycirclize import Circos
from pycirclize.utils import calc_group_spaces, ColorCycler

from duwcm.data_structures import UrbanWaterData

def generate_chord(results: Dict[str, pd.DataFrame], output_dir: Path) -> None:
    """
    Generate a chord diagram showing accumulated water flows between components using pycirclize.

    Args:
        geometry_geopackage (Path): Path to the GeoPackage file containing geometry data
        results (Dict[str, pd.DataFrame]): Dictionary containing results for all components
        output_dir (Path): Directory to save the diagram
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # All nodes for the chord diagram
    nodes = (['imported_water', 'precipitation', 'irrigation'] +
             UrbanWaterData.COMPONENTS +
             ['deep_seepage', 'baseflow', 'evaporation'])
    #nodes = (UrbanWaterData.COMPONENTS +
    #        ['imported_water', 'precipitation', 'irrigation',
    #         'evaporation', 'deep_seepage', 'baseflow'])

    # Create symmetric adjacency matrix
    flow_matrix = pd.DataFrame(0, index=nodes, columns=nodes, dtype=float)
    flow_values = pd.DataFrame(0, index=nodes, columns=nodes, dtype=float)

    # Process flow connections
    for (src_comp, source_flow), (trg_comp, target_flow) in UrbanWaterData.FLOW_CONNECTIONS.items():
        try:
            # Handle regular component flows
            if src_comp in UrbanWaterData.COMPONENTS and trg_comp in UrbanWaterData.COMPONENTS:
                flow_value = results[src_comp][source_flow].sum() * 0.001  # Convert to m³
                if flow_value > 0:
                    flow_values.loc[src_comp, trg_comp] = float(flow_value)
                    flow_matrix.loc[src_comp, trg_comp] = float(np.log(flow_value + 1e-10) / np.log(10))
                continue

            # Handle flows with external components
            if src_comp not in UrbanWaterData.COMPONENTS:  # External to component
                flow_value = results[trg_comp][target_flow].sum() * 0.001
                if flow_value > 0:
                    flow_values.loc[src_comp, trg_comp] = float(flow_value)
                    flow_matrix.loc[src_comp, trg_comp] = float(np.log(flow_value + 1e-10) / np.log(10))

            elif trg_comp not in UrbanWaterData.COMPONENTS:  # Component to external
                flow_name = source_flow
                if source_flow == 'transpiration':
                    flow_name = 'transpiration'
                    trg_comp = 'evaporation'
                elif source_flow == 'baseflow':
                    flow_value = results[src_comp][source_flow].sum() * 0.001
                    if flow_value > 0:
                        flow_values.loc[src_comp, 'baseflow'] = float(flow_value)
                        flow_matrix.loc[src_comp, 'baseflow'] = float(np.log(flow_value + 1e-10) / np.log(10))
                    if flow_value < 0:
                        flow_values.loc['baseflow', src_comp] = float(abs(flow_value))
                        flow_matrix.loc['baseflow', src_comp] = float(np.log(abs(flow_value) + 1e-10) / np.log(10))
                    continue

                flow_value = results[src_comp][flow_name].sum() * 0.001
                if flow_value > 0:
                    flow_values.loc[src_comp, trg_comp] = float(flow_value)
                    flow_matrix.loc[src_comp, trg_comp] = float(np.log(flow_value + 1e-10) / np.log(10))

        except (KeyError, ValueError) as e:
            print(f"Error processing {src_comp} -> {trg_comp}: {e}")
            continue

    # Remove rows and columns that sum to zero
    non_zero_mask = (flow_matrix.sum(axis=0) != 0) | (flow_matrix.sum(axis=1) != 0)
    active_nodes = flow_matrix.index[non_zero_mask].tolist()

    # Filter matrices to only include non-zero rows/columns
    flow_matrix = flow_matrix.loc[active_nodes, active_nodes]
    flow_values = flow_values.loc[active_nodes, active_nodes]
    flow_matrix = flow_matrix.rename(columns={'imported_water': 'imported', 'deep_seepage': 'seepage'},
                                     index={'imported_water': 'imported', 'deep_seepage': 'seepage'})
    flow_values = flow_values.rename(columns={'imported_water': 'imported', 'deep_seepage': 'seepage'},
                                     index={'imported_water': 'imported', 'deep_seepage': 'seepage'})

    # Initialize from matrix
    circos = Circos.initialize_from_matrix(
        flow_matrix,
        space=2,
        r_lim=(95, 100),
        cmap="tab20",
        label_kws={"r": 103, "size": 10},
        link_kws={"direction": 1, "ec": 'black', "lw": 0.5}
    )

    filename = output_dir / 'chord.png'
    circos.savefig(filename)