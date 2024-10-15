"""
Urban Water Model Module

This module defines the core structure and components of the urban water balance model.
It provides the UrbanWaterModel class, which integrates various submodels to simulate
water dynamics in an urban environment.

Key components:
    - UrbanWaterData: A dataclass that holds the state variables for all submodels.
    - UrbanWaterModel: The main class that orchestrates the simulation, managing submodels
    and state variables for each cell in the urban grid.

The module supports the simulation of:
    - Roof surface
    - Rain tank dynamics
    - Pavement surface
    - Pervious surface
    - Vadose zone
    - Groundwater dynamics
    - Stormwater
    - Water reuse
    - Wastewater

The UrbanWaterModel class provides methods for initializing the model, updating states,
and managing the overall simulation process. It serves as the central component in the
urban water balance simulation.
"""

from typing import Dict, Any
import numpy as np
import pandas as pd

from duwcm.functions import find_order
from duwcm.data_structures import UrbanWaterData, UrbanWaterFlowsData, ComponentFlows

# Import subcomponents and data classes
from duwcm.components import (
    roof, raintank, pavement, pervious, vadose,
    groundwater, stormwater, reuse, wastewater
)

class UrbanWaterModel:
    """
    Urban water model class. Includes submodels:
        - Roof
        - Rain tank
        - Pavement
        - Pervious
        - Vadose
        - Groundwater
        - Stormawater
        - Reuse
        - Wastewater
    """

    SubmodelClasses = {
        'roof': roof.RoofClass,
        'raintank': raintank.RainTankClass,
        'pavement': pavement.PavementClass,
        'pervious': pervious.PerviousClass,
        'vadose': vadose.VadoseClass,
        'groundwater': groundwater.GroundwaterClass,
        'stormwater': stormwater.StormwaterClass,
        'reuse': reuse.ReuseClass,
        'wastewater': wastewater.WastewaterClass
    }
    def __init__(self, params: Dict[str, Dict[str, float]], path: pd.DataFrame, soil_data: pd.DataFrame,
                 et_data: pd.DataFrame, demand_data: pd.DataFrame, reuse_settings: pd.DataFrame, direction: int):
        """
        Initialize the UrbanWaterModel.

        Args:
            params: Dictionary of parameter dictionaries for each grid cell.
            path: Downstream path DataFrame.
            soil_data: Soil parameter data.
            et_data: Evapotranspiration parameter data.
            demand_data: Water demand data.
            reuse_settings: Water reuse settings.
            num_timesteps: Number of time steps in the simulation.
            direction: Number of neighbors considered (4, 6, or 8)
        """
        self.path = path
        self.params = params
        self.soil_data = soil_data
        self.et_data = et_data
        self.demand_data = demand_data
        self.reuse_settings = reuse_settings

        # Initialize submodels, current and previous states
        self.submodels, self.current, self.previous, self.flows = self._init_submodels()

        self.wastewater_cells = [i for i, p in self.params.items() if p['wastewater']['capacity'] > 0]
        self.stormwater_cells = [i for i, p in self.params.items() if p['stormwater']['capacity'] > 0]

        # Calculate the order of cells
        self.cell_order = find_order(self.path, direction)

        # Set initial conditions
        self._set_initial_conditions()

    def _init_submodels(self) -> Dict[int, Dict[str, Any]]:
        """Initialize submodels for each grid cell."""
        submodels = {}
        current_states = {}
        previous_states = {}
        flows = {}

        for cell_id, cell_params in self.params.items():
            reuse_index = 1 if self.reuse_settings.shape[1] == 1 else cell_id
            cell_submodels = {
                'roof': self.SubmodelClasses['roof'](cell_params),
                'raintank': self.SubmodelClasses['raintank'](cell_params),
                'pavement': self.SubmodelClasses['pavement'](cell_params),
                'pervious': self.SubmodelClasses['pervious'](cell_params, self.soil_data, self.et_data),
                'vadose': self.SubmodelClasses['vadose'](cell_params, self.soil_data, self.et_data),
                'groundwater': self.SubmodelClasses['groundwater'](cell_params, self.soil_data, self.et_data),
                'stormwater': self.SubmodelClasses['stormwater'](cell_params),
                'reuse': self.SubmodelClasses['reuse'](cell_params, self.demand_data, self.reuse_settings[reuse_index]),
                'wastewater': self.SubmodelClasses['wastewater'](cell_params)
            }

            submodels[cell_id] = cell_submodels
            current_states[cell_id] = UrbanWaterData()
            previous_states[cell_id] = UrbanWaterData()
            flows[cell_id] = UrbanWaterFlowsData()

        return submodels, current_states, previous_states, flows

    def _set_initial_conditions(self):
        for cell_id, params in self.params.items():
            self.previous[cell_id].groundwater.water_level = params['groundwater']['initial_level']
            self.previous[cell_id].wastewater.storage = params['wastewater']['initial_storage']
            self.previous[cell_id].raintank.storage = params['raintank']['initial_storage']
            self.previous[cell_id].vadose.moisture = params['vadose']['initial_moisture']
            self.previous[cell_id].stormwater.storage = params['stormwater']['initial_storage']
            self.previous[cell_id].roof.storage = 0
            self.previous[cell_id].pavement.storage = 0
            self.previous[cell_id].pervious.storage = 0

    def update_states(self):
        """Update previous state with current state and reset current state."""
        for cell_id, current_state in self.current.items():
            # Update previous state
            for attr, value in current_state.__dict__.items():
                setattr(self.previous[cell_id], attr, value)

            # Cross model transfer
            self.previous[cell_id].raintank.storage = current_state.reuse.rt_storage

            # Reset current state
            for attr in current_state.__dict__:
                setattr(current_state, attr, type(getattr(current_state, attr))())

            # Reset flows
            for attr in self.flows[cell_id].__dict__:
                setattr(self.flows[cell_id], attr, ComponentFlows())

    def distribute_wastewater(self):
        for w in self.wastewater_cells:
            available_cells = list(self.cell_order)
            while self.current[w].wastewater.storage > 0 and available_cells:
                select = np.random.choice(available_cells)
                reuse_index = 1 if self.reuse_settings.shape[1] == 1 else select
                setreuse = self.reuse_settings[reuse_index]

                # Toilet use
                wws_toilet_use = min(self.current[w].wastewater.storage,
                                     self.current[select].reuse.toilet_demand * setreuse.cWWSforT)
                self.current[select].reuse.toilet_demand -= wws_toilet_use

                # Irrigation use
                wws_irrigation_use = min(self.current[w].wastewater.storage - wws_toilet_use,
                                         self.current[select].reuse.irrigation_demand * setreuse.cWWSforIR)
                self.current[select].reuse.irrigation_demand -= wws_irrigation_use

                # Update storages and uses
                self.current[w].wastewater.storage -= (wws_toilet_use + wws_irrigation_use)
                self.current[w].wastewater.use += (wws_toilet_use + wws_irrigation_use)
                self.current[select].wastewater.supply += (wws_toilet_use + wws_irrigation_use)
                self.current[select].reuse.imported_water -= (wws_toilet_use + wws_irrigation_use)

                available_cells.remove(select)

    def distribute_stormwater(self):
        for s in self.stormwater_cells:
            available_cells = list(self.cell_order)
            while self.current[s].stormwater.storage > 0 and available_cells:
                select = np.random.choice(available_cells)
                reuse_index = 1 if self.reuse_settings.shape[1] == 1 else select
                setreuse = self.reuse_settings[reuse_index]

                # Toilet use
                sws_toilet_use = min(self.current[s].stormwater.storage,
                                     self.current[select].reuse.toilet_demand * setreuse.SWSforT)
                self.current[select].reuse.toilet_demand -= sws_toilet_use

                # Irrigation use
                sws_irrigation_use = min(self.current[s].stormwater.storage - sws_toilet_use,
                                         self.current[select].reuse.irrigation_demand * setreuse.SWSforIR)
                self.current[select].reuse.irrigation_demand -= sws_irrigation_use

                # Update storages and uses
                self.current[s].stormwater.storage -= (sws_toilet_use + sws_irrigation_use)
                self.current[s].stormwater.use += (sws_toilet_use + sws_irrigation_use)
                self.current[select].stormwater.supply += (sws_toilet_use + sws_irrigation_use)
                self.current[select].reuse.imported_water -= (sws_toilet_use + sws_irrigation_use)

                available_cells.remove(select)
