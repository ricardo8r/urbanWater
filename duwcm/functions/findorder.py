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
    d1 = np.where(path_index.u1 == 0)  # u1=0: most upstream cell
    order = path_index.index[d1].values
    order = np.insert(order, 0, 0)
    more: List[Union[int, float]] = []

    for i in path_index.iloc[d1]['down']:
        if i == 0:
            break
        if path_index.loc[i, 'u2'] == 0:
            order = np.append(order, i)
            down = path_index.loc[i, 'down']
            if down != 0:
                if path_index.loc[down, 'u2'] != 0:
                    more.append(down)
                while path_index.loc[down, 'u2'] == 0:
                    order = np.append(order, down)
                    down = path_index.loc[down, 'down']
                    if down == 0:
                        break
                    if path_index.loc[down, 'u2'] != 0:
                        more.append(down)
        else:
            more.append(i)

    more = list(set(more))

    new: List[Union[int, float]] = []
    for mul in more:
        if _is_available(path_index, mul, order, direction):
            new.append(mul)
            order = np.append(order, mul)
            more.remove(mul)

    while len(order) < len(path_index) + 1:
        for i in path_index.loc[new, 'down']:
            if i in order:
                continue
            if path_index.loc[i, 'u2'] == 0:
                order = np.append(order, i)
                down = path_index.loc[i, 'down']
                if down == 0:
                    break
                if path_index.loc[down, 'u2'] != 0:
                    more.append(down)
                while path_index.loc[down, 'u2'] == 0:
                    order = np.append(order, down)
                    down = path_index.loc[down, 'down']
                    if down == 0:
                        break
                    if path_index.loc[down, 'u2'] != 0:
                        more.append(down)
            else:
                more.append(i)

        more = list(set(more))
        new = []
        for mul in more:
            if _is_available(path_index, mul, order, direction):
                order = np.append(order, mul)
                new.append(mul)
                more.remove(mul)

    return np.delete(order, 0)

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
    if direction == 6:
        return all(path_index.loc[mul, f"u{i}"] in order for i in range(1, 7))
    return all(path_index.loc[mul, f"u{i}"] in order for i in range(1, 5))
