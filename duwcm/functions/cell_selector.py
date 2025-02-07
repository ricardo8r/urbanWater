from typing import List
import pandas as pd

def select_cells(model_params: dict, flow_paths: pd.DataFrame, selected_cells: List[int]) -> tuple:
    """Filter model parameters and flow paths to selected cells.

    Args:
        model_params: Original model parameters dictionary
        flow_paths: Original flow paths DataFrame
        selected_cells: List of cell IDs to select

    Returns:
        Tuple of (filtered_params, filtered_paths)
    """
    filtered_params = {k: v for k, v in model_params.items() if k in selected_cells}

    filtered_paths = flow_paths.loc[flow_paths.index.isin(selected_cells)].copy()
    for col in filtered_paths.columns:
        if col != 'down':
            filtered_paths[col] = filtered_paths[col].apply(lambda x: x if x in selected_cells else 0)
    filtered_paths['down'] = filtered_paths['down'].apply(lambda x: x if x in selected_cells else 0)

    return filtered_params, filtered_paths
