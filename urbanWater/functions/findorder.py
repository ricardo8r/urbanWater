from typing import List, Union
import numpy as np
import pandas as pd

def find_order(path_index: pd.DataFrame, direction: int) -> np.ndarray:
    """
    Derive the calculation order for urban water balance simulation.

    Args:
        path_index (pd.DataFrame): Flow path data with columns ['down', 'u1', 'u2', 'u3', 'u4', ...]
        direction (int): Number of neighbors (6, 4, or 8)

    Returns:
        np.ndarray: Calculation order for grid cells
    """
    # First identify all terminal cells (those with no downstream cell or downstream = 0)
    terminal_cells = path_index[path_index['down'] == 0].index.values
    if len(terminal_cells) == 0:
        # If no terminal cells, treat cells with downstream connections 
        # outside the selected set as terminal
        terminal_cells = path_index[~path_index['down'].isin(path_index.index)].index.values

    # Start building order from terminal cells
    order = []
    processed = set()

    def add_upstream_cells(cell_id):
        if cell_id in processed:
            return
        # Get all valid upstream cells
        upstream = []
        for col in [f'u{i}' for i in range(1, direction + 1)]:
            if col in path_index.columns:
                up_id = path_index.loc[cell_id, col]
                if up_id != 0 and up_id in path_index.index:
                    upstream.append(up_id)
        # Recursively process upstream cells first
        for up_id in upstream:
            add_upstream_cells(up_id)
        # Add current cell if not already processed
        if cell_id not in processed:
            order.append(cell_id)
            processed.add(cell_id)

    # Process each terminal cell
    for cell in terminal_cells:
        add_upstream_cells(cell)

    # Handle any remaining unprocessed cells (disconnected components)
    remaining = set(path_index.index) - processed
    while remaining:
        cell = remaining.pop()
        add_upstream_cells(cell)

    return np.array(order)


def _is_available(path_index: pd.DataFrame, mul: Union[int, float], order: np.ndarray, direction: int) -> bool:
    """
    Check if all upstream cells are available in the order.

    Args:
        path_index (pd.DataFrame): Flow path data
        mul (Union[int, float]): Cell index to check
        order (np.ndarray): Current calculation order
        direction (int): Number of neighbors

    Returns:
        bool: True if all upstream cells are available, False otherwise
    """
    if direction == 8:
        return all(path_index.loc[mul, f"u{i}"] in order for i in range(1, 9))
    elif direction == 6:
        return all(path_index.loc[mul, f"u{i}"] in order for i in range(1, 7))
    else:
        return all(path_index.loc[mul, f"u{i}"] in order for i in range(1, 5))
