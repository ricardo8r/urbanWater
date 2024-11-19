from pathlib import Path
from typing import Dict
import numpy as np
import pandas as pd
from pycirclize import Circos
from pycirclize.utils import calc_group_spaces, ColorCycler

from duwcm.data_structures import UrbanWaterData

def generate_chord(results: Dict[str, pd.DataFrame], output_dir: Path) -> None:
    """Generate a chord diagram showing accumulated water flows between components."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # All nodes for the chord diagram
    nodes = (['imported', 'precipitation', 'irrigation'] +
             UrbanWaterData.COMPONENTS +
             ['seepage', 'baseflow', 'evaporation'])

    # Create symmetric adjacency matrix
    flow_matrix = pd.DataFrame(0, index=nodes, columns=nodes, dtype=float)
    flow_values = pd.DataFrame(0, index=nodes, columns=nodes, dtype=float)

    # Process flow connections
    for (src_comp, source_flow), (trg_comp, target_flow) in UrbanWaterData.FLOW_CONNECTIONS.items():
        # Handle regular component flows
        if src_comp in UrbanWaterData.COMPONENTS and trg_comp in UrbanWaterData.COMPONENTS:
            flow_value = results[src_comp][source_flow].sum() * 0.001  # Convert to m³
            if flow_value > 0:
                flow_values.loc[src_comp, trg_comp] = float(flow_value)
                flow_matrix.loc[src_comp, trg_comp] = float(np.log(flow_value + 1e-10) / np.log(10))

    # Add precipitation flows
    for comp in ['roof', 'pavement', 'pervious', 'raintank', 'stormwater']:
        if comp in results:
            flow_value = results[comp]['precipitation'].sum() * 0.001
            if flow_value > 0:
                flow_values.loc['precipitation', comp] = float(flow_value)
                flow_matrix.loc['precipitation', comp] = float(np.log(flow_value + 1e-10) / np.log(10))

    # Add irrigation flows
    for comp in ['roof', 'pavement', 'pervious']:
        if comp in results:
            flow_value = results[comp]['irrigation'].sum() * 0.001
            if flow_value > 0:
                flow_values.loc['irrigation', comp] = float(flow_value)
                flow_matrix.loc['irrigation', comp] = float(np.log(flow_value + 1e-10) / np.log(10))

    # Add evaporation flows
    for comp in ['roof', 'pavement', 'pervious', 'raintank', 'stormwater']:
        if comp in results:
            flow_value = results[comp]['evaporation'].sum() * 0.001
            if flow_value > 0:
                flow_values.loc[comp, 'evaporation'] = float(flow_value)
                flow_matrix.loc[comp, 'evaporation'] = float(np.log(flow_value + 1e-10) / np.log(10))

    # Add transpiration to evaporation
    if 'vadose' in results:
        flow_value = results['vadose']['transpiration'].sum() * 0.001
        if flow_value > 0:
            flow_values.loc['vadose', 'evaporation'] = float(flow_value)
            flow_matrix.loc['vadose', 'evaporation'] = float(np.log(flow_value + 1e-10) / np.log(10))

    # Add imported water flows
    if 'demand' in results:
        flow_value = results['demand']['imported_water'].sum() * 0.001
        if flow_value > 0:
            flow_values.loc['imported', 'demand'] = float(flow_value)
            flow_matrix.loc['imported', 'demand'] = float(np.log(flow_value + 1e-10) / np.log(10))

    # Add baseflow
    if 'groundwater' in results:
        flow_value = results['groundwater']['baseflow'].sum() * 0.001
        if flow_value > 0:
            flow_values.loc['groundwater', 'baseflow'] = float(flow_value)
            flow_matrix.loc['groundwater', 'baseflow'] = float(np.log(flow_value + 1e-10) / np.log(10))
        if flow_value < 0:
            flow_values.loc['baseflow', 'groundwater'] = float(np.abs(flow_value))
            flow_matrix.loc['baseflow', 'groundwater'] = float(np.log(np.abs(flow_value) + 1e-10) / np.log(10))

    # Add deep seepage
    if 'groundwater' in results:
        flow_value = results['groundwater']['seepage'].sum() * 0.001
        if flow_value > 0:
            flow_values.loc['groundwater', 'seepage'] = float(flow_value)
            flow_matrix.loc['groundwater', 'seepage'] = float(np.log(flow_value + 1e-10) / np.log(10))
        if flow_value < 0:
            flow_values.loc['seepage', 'groundwater'] = float(np.abs(flow_value))
            flow_matrix.loc['seepage', 'groundwater'] = float(np.log(np.abs(flow_value) + 1e-10) / np.log(10))

    # Remove rows and columns that sum to zero
    non_zero_mask = (flow_matrix.sum(axis=0) != 0) | (flow_matrix.sum(axis=1) != 0)
    active_nodes = flow_matrix.index[non_zero_mask].tolist()

    # Filter matrices to only include non-zero rows/columns
    flow_matrix = flow_matrix.loc[active_nodes, active_nodes]
    flow_values = flow_values.loc[active_nodes, active_nodes]

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