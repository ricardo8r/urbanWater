from pathlib import Path
from typing import Dict
import pandas as pd

from duwcm.diagnostics import DiagnosticTracker
from duwcm.plots import generate_alluvial

def generate_alluvial_cells(flow_paths: pd.DataFrame, selected_cells: set,
                            output_dir: Path, tracker: DiagnosticTracker) -> None:
    """Generate an alluvial diagram for each cell."""
    output_dir = output_dir / 'figures'
    output_dir.mkdir(parents=True, exist_ok=True)
    for cell_id in selected_cells:
        detailed_matrix = tracker.get_internal_flow_matrix(cell_id=cell_id)
        fig = generate_alluvial(detailed_matrix)
        output_file = output_dir / f'cell_{cell_id}_internal.png'
        fig.write_image(output_file, scale=2)

        detailed_matrix = tracker.get_external_flow_matrix(cell_id=cell_id)
        fig = generate_alluvial(detailed_matrix)
        output_file = output_dir / f'cell_{cell_id}_external.png'
        fig.write_image(output_file, scale=2)
