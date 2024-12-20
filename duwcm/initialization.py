"""
Groundwater initialization methods for urban water model.

This module provides methods for initializing groundwater and related states 
using either cyclic spinup or ensemble approaches.
"""

from typing import Dict
import pandas as pd
from tqdm import tqdm
from dynaconf import Dynaconf

from duwcm.water_model import UrbanWaterModel


def initialize_model(model: UrbanWaterModel, forcing_data: pd.DataFrame, config: Dynaconf) -> None:
    """
    Initialize model states using specified method from config.

    Args:
        model: Urban water model instance
        forcing_data: Forcing dataset
        config: Configuration object with simulation settings
    """
    final_states = cyclic(
        model,
        forcing_data,
        num_cycles=config.simulation.spinup_cycles
    )

    apply_states(model, final_states)

def cyclic(model: UrbanWaterModel,
           forcing_data: pd.DataFrame,
           num_cycles: int = 3,
           convergence_threshold: float = 0.01,
           verbose: bool = True) -> Dict:
    """
    Initialize model states using cyclic spinup through annual forcing data.
    """
    # Get annual period if multi-year data provided
    if len(forcing_data) > 365:
        annual_forcing = forcing_data.iloc[:365]
    else:
        annual_forcing = forcing_data

    # Store initial states to check convergence
    prev_states = {}
    for cell_id, data in model.data.items():
        prev_states[cell_id] = {
            'groundwater': data.groundwater.water_level.get_previous('m'),
            'vadose': data.vadose.moisture.get_previous('mm'),
            'surface_water': data.groundwater.surface_water_level.get_previous('m')
        }

    converged = False

    # Run cycles
    iterator = range(num_cycles)
    if verbose:
        iterator = tqdm(iterator, desc="Spinup cycles")

    for cycle in iterator:
        # Run one year
        for _, forcing in annual_forcing.iterrows():
            # Solve for each cell in the correct order
            for cell_id in model.cell_order:
                cell_data = model.data[cell_id]
                for component_name, component in cell_data.iter_components():
                    component_class = model.classes[cell_id][component_name]
                    component_class.solve(forcing)
            model.update_states()

        # Check convergence
        max_relative_change = 0
        current_states = {}

        for cell_id, data in model.data.items():
            current_states[cell_id] = {
                'groundwater': data.groundwater.water_level.get_previous('m'),
                'vadose': data.vadose.moisture.get_previous('mm'),
                'surface_water': data.groundwater.surface_water_level.get_previous('m')
            }

            # Calculate maximum relative change across all states
            for key in current_states[cell_id]:
                prev_val = prev_states[cell_id][key]
                curr_val = current_states[cell_id][key]

                if abs(prev_val) > 1e-6:  # Avoid division by zero
                    rel_change = abs((curr_val - prev_val) / prev_val)
                    max_relative_change = max(max_relative_change, rel_change)

        if verbose:
            print(f"Cycle {cycle+1} max relative change: {max_relative_change:.4f}")

        if max_relative_change < convergence_threshold:
            converged = True
            if verbose:
                print(f"Converged after {cycle+1} cycles")
            break

        prev_states = current_states

    if not converged and verbose:
        print("Warning: Maximum cycles reached without convergence")

    return current_states

def apply_states(model: UrbanWaterModel, states: Dict) -> None:
    """
    Apply initialized states to model.

    Args:
        model: Urban water model instance
        states: Dict of states from initialization
    """
    for cell_id, cell_states in states.items():
        data = model.data[cell_id]
        data.groundwater.water_level.set_previous(
            cell_states['groundwater'], 'm')
        data.vadose.moisture.set_previous(
            cell_states['vadose'], 'mm')
        data.groundwater.surface_water_level.set_previous(
            cell_states['surface_water'], 'm')
