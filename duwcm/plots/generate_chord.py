from pathlib import Path
from typing import Dict
import numpy as np
import pandas as pd
from pycirclize import Circos

from duwcm.data_structures import UrbanWaterData
from duwcm.functions import calculate_flow_matrix

def generate_chord(results: Dict[str, pd.DataFrame], output_dir: Path) -> None:
    """Generate a chord diagram showing water flows between components."""
    output_dir.mkdir(parents=True, exist_ok=True)

    nodes = (['imported', 'precipitation', 'irrigation'] +
             UrbanWaterData.COMPONENTS +
             ['seepage', 'baseflow', 'evaporation'])
    flow_matrix = calculate_flow_matrix(results, nodes)
    flow_matrix[flow_matrix != 0] = np.log10(flow_matrix[flow_matrix != 0]) + 1e-10

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