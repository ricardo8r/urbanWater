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
    - Water demand
    - Wastewater

The UrbanWaterModel class provides methods for initializing the model, updating states,
and managing the overall simulation process. It serves as the central component in the
urban water balance simulation.
"""
from typing import Dict, Any
import numpy as np
import pandas as pd

from duwcm.functions import find_order
from duwcm.data_structures import UrbanWaterData

from duwcm.components import (
    roof, raintank, pavement, pervious, vadose,
    groundwater, stormwater, demand, wastewater
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
        - Demand
        - Wastewater
    """

    def __init__(self, params: Dict[str, Dict[str, float]], path: pd.DataFrame, soil_data: pd.DataFrame,
                 et_data: pd.DataFrame, demand_settings: pd.DataFrame, reuse_settings: pd.DataFrame, direction: int):
        """
        Initialize the UrbanWaterModel.

        Args:
            params: Dictionary of parameter dictionaries for each grid cell.
            path: Downstream path DataFrame.
            soil_data: Soil parameter data.
            et_data: Evapotranspiration parameter data.
            demand_settings: Water demand data.
            reuse_settings: Water reuse settings.
            num_timesteps: Number of time steps in the simulation.
            direction: Number of neighbors considered (4, 6, or 8)
        """
        self.path = path
        self.params = params
        self.soil_data = soil_data
        self.et_data = et_data
        self.demand_settings = demand_settings
        self.reuse_settings = reuse_settings

        # Initialize submodels
        self._init_submodels()

        self.wastewater_cells = [i for i, p in self.params.items() if p['wastewater']['capacity'] > 0]
        self.stormwater_cells = [i for i, p in self.params.items() if p['stormwater']['capacity'] > 0]

        # Calculate the order of cells
        self.cell_order = find_order(self.path, direction)

    def _init_submodels(self) -> Dict[int, Dict[str, Any]]:
        """Initialize submodels for each grid cell."""
        self.classes = {}
        self.data = {}

        for cell_id, cell_params in self.params.items():
            self.data[cell_id] = UrbanWaterData()
            reuse_index = 1 if self.reuse_settings.shape[1] == 1 else cell_id

            cell_submodels = {
                'roof': roof.RoofClass(cell_params, self.data[cell_id].roof),
                'raintank': raintank.RainTankClass(cell_params, self.data[cell_id].raintank),
                'pavement': pavement.PavementClass(cell_params, self.data[cell_id].pavement),
                'pervious': pervious.PerviousClass(cell_params, self.soil_data, self.et_data,
                                                   self.data[cell_id].pervious),
                'vadose': vadose.VadoseClass(cell_params, self.soil_data, self.et_data, self.data[cell_id].vadose),
                'groundwater': groundwater.GroundwaterClass(cell_params, self.soil_data, self.et_data,
                                                            self.data[cell_id].groundwater),
                'stormwater': stormwater.StormwaterClass(cell_params, self.data[cell_id].stormwater),
                'demand': demand.DemandClass(cell_params, self.demand_settings, self.reuse_settings[reuse_index],
                                          self.data[cell_id].demand),
                'wastewater': wastewater.WastewaterClass(cell_params, self.data[cell_id].wastewater)
            }
            self.classes[cell_id] = cell_submodels

        # Connect upstream flows for both stormwater and wastewater
        for cell_id in self.params:
            for up in self.path.loc[cell_id].iloc[1:]:
                if up != 0:
                    # Link stormwater flows
                    self.data[cell_id].stormwater.flows.from_upstream.add_source(
                        self.data[up].stormwater.flows.to_downstream
                    )
                    # Link wastewater flows
                    self.data[cell_id].wastewater.flows.from_upstream.add_source(
                        self.data[up].wastewater.flows.to_downstream
                    )

    def update_states(self):
        """Update previous state with current state."""
        for cell_id, data in self.data.items():
            data.update_storage()
            data.reset_flows()

    def distribute_wastewater(self):
        for w in self.wastewater_cells:
            available_cells = list(self.cell_order)
            while self.data[w].wastewater.storage.amount > 0 and available_cells:
                select = np.random.choice(available_cells)
                reuse_index = 1 if self.reuse_settings.shape[1] == 1 else select
                setreuse = self.reuse_settings[reuse_index]

                # Toilet use
                wws_toilet_use = min(
                    self.data[w].wastewater.storage.amount,
                    self.data[select].demand.rt_toilet_demand * setreuse.cWWSforT
                )
                self.data[select].demand.rt_toilet_demand -= wws_toilet_use

                # Irrigation use
                wws_irrigation_use = min(
                    self.data[w].wastewater.storage.amount - wws_toilet_use,
                    self.data[select].demand.rt_irrigation_demand * setreuse.cWWSforIR
                )
                self.data[select].demand.rt_irrigation_demand -= wws_irrigation_use

                # Update storages and uses
                self.data[w].wastewater.storage.amount -= (wws_toilet_use + wws_irrigation_use)
                self.data[w].wastewater.use += (wws_toilet_use + wws_irrigation_use)
                self.data[select].wastewater.supply += (wws_toilet_use + wws_irrigation_use)
                self.data[select].demand.imported_water -= (wws_toilet_use + wws_irrigation_use)

                available_cells.remove(select)

    def distribute_stormwater(self):
        for s in self.stormwater_cells:
            available_cells = list(self.cell_order)
            while self.data[s].stormwater.storage.amount > 0 and available_cells:
                select = np.random.choice(available_cells)
                reuse_index = 1 if self.reuse_settings.shape[1] == 1 else select
                setreuse = self.reuse_settings[reuse_index]

                # Toilet use
                sws_toilet_use = min(
                    self.data[s].stormwater.storage.amount,
                    self.data[select].demand.rt_toilet_demand * setreuse.SWSforT
                )
                self.data[select].demand.rt_toilet_demand -= sws_toilet_use

                # Irrigation use
                sws_irrigation_use = min(
                    self.data[s].stormwater.storage.amount - sws_toilet_use,
                    self.data[select].demand.rt_irrigation_demand * setreuse.SWSforIR
                )
                self.data[select].demand.rt_irrigation_demand -= sws_irrigation_use

                # Update storages and uses
                self.data[s].stormwater.storage.amount -= (sws_toilet_use + sws_irrigation_use)
                self.data[s].stormwater.use += (sws_toilet_use + sws_irrigation_use)
                self.data[select].stormwater.supply += (sws_toilet_use + sws_irrigation_use)
                self.data[select].demand.imported_water -= (sws_toilet_use + sws_irrigation_use)

                available_cells.remove(select)
