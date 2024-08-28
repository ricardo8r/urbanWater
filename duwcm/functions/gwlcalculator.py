from typing import Tuple

def gw_levels(groundwater_level: float) -> Tuple[float, float, int, int]:
    """
    Calculates the upper and lower groundwater levels and their corresponding indexes for referencing in the database.

    Args:
        groundwater_level (float): Current groundwater level [m-SL]

    Returns:
        Tuple[float, float, int, int]: A tuple containing:
            - upper_level (float): First value in predefined table above groundwater level [m-SL]
            - lower_level (float): First value in predefined table below groundwater level [m-SL]
            - upper_index (int): Index of upper_level in the database
            - lower_index (int): Index of lower_level in the database
    """
    upper_level = float(groundwater_level)

    if 0.0 <= upper_level <= 2.5:
        upper_level = (upper_level * 10.0) // 1 / 10.0
        upper_index = int(upper_level * 10.0)
    elif upper_level < 3.0:
        upper_level, upper_index = 2.5, 25
    elif upper_level < 5.0:
        upper_level = int(upper_level)
        upper_index = 23 + upper_level
    elif upper_level < 10.0:
        upper_level, upper_index = 5.0, 28
    else:
        upper_level, upper_index = 10.0, 29

    if upper_level < 2.5:
        lower_level = round(upper_level + 0.1, 2)
        lower_index = upper_index + 1
    elif upper_level < 3.0:
        lower_level, lower_index = 3.0, upper_index + 1
    elif upper_level < 4.0:
        lower_level, lower_index = 4.0, upper_index + 1
    elif upper_level < 5.0:
        lower_level, lower_index = 5.0, upper_index + 1
    else:
        lower_level, lower_index = 10.0, 29

    return upper_level, lower_level, upper_index, lower_index