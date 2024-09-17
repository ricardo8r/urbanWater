from typing import List, Tuple
import numpy as np
import pandas as pd

def find_nearest_downstream(df: pd.DataFrame, direction: int, cell_size: float) -> Tuple[List[int], List[float]]:
    """
    Derive the nearest downstream block having open water.

    Args:
        df (pd.DataFrame): DataFrame with index=cellid and columns: downID, CentreX, CentreY, pLU_WAT
        direction (int): Number of neighbors (6, 4, or 8)
        cell_size (float): Side length of one cell [m]

    Returns:
        Tuple[List[int], List[float]]: 
            - List of indices of the nearest downstream blocks having open water
            - List of distances between each block and its nearest downstream open water [m]
    """
    downstream_ow = []
    downstream_ow_distance = []

    for current_id in df.index:
        distance_counts = [0, 0, 0]  # [1, sqrt(2), sqrt(3)]
        downstream_id = df.downID[current_id]

        if downstream_id > df.index.min():
            while df.pLU_WAT[downstream_id] < 0.0001:
                if direction == 6:
                    distance_counts[2] += 1
                else:
                    is_diagonal = (df.CentreX[current_id] != df.CentreX[downstream_id]) and \
                                  (df.CentreY[current_id] != df.CentreY[downstream_id])
                    distance_counts[1 if is_diagonal else 0] += 1

                current_id = downstream_id
                downstream_id = df.downID[downstream_id]
                if downstream_id < df.index.min():
                    break

        if downstream_id > df.index.min():
            if direction == 6:
                distance_counts[2] += 1
            else:
                is_diagonal = (df.CentreX[current_id] != df.CentreX[downstream_id]) and \
                              (df.CentreY[current_id] != df.CentreY[downstream_id])
                distance_counts[1 if is_diagonal else 0] += 1

        downstream_ow.append(downstream_id)
        total_distance = (distance_counts[0] + np.sqrt(2) * distance_counts[1] +
                          np.sqrt(3) * distance_counts[2]) * cell_size
        downstream_ow_distance.append(total_distance)

    return downstream_ow, downstream_ow_distance