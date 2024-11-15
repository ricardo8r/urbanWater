from typing import Dict, Any, Tuple
import numpy as np
import pandas as pd
from duwcm.data_structures import GroundwaterData
from duwcm.functions import soil_selector, gw_levels

# Constants
MAX_SOIL_DEPTH = 10.0
MAX_SOIL_INDEX = 29
PIPE_DEPTH = 3.0
INFILTRATION_FACTOR = 0.5

class GroundwaterClass:
    """
    Simulates groundwater dynamics

    Inflows: Leakage (irrigation + indoor water usage), vadose zone percolation,
            pavement infiltration
    Outflows: Seepage to deep groundwater, baseflow to open water, pipe insfiltration
    """
    def __init__(self, params: Dict[str, Dict[str, Any]], soil_data: pd.DataFrame,
                 et_data: pd.DataFrame, groundwater_data: GroundwaterData):
        """
        Args:
            params (Dict[str, float]): Groundwater parameters
                area: Groundwater area [m^2]
                roof_area: Roof area [m^2]
                pavement_area: Paved area [m^2]
                pervious_area: Pervious area [m^2]
                vadose_area: Vadose zone area [m^2]
                indoor_water_use: Indoor water use [L]
                leakage_rate: Leakage rate [%]
                seepage_model: Seepage model, constant downward [0] or dynamic flux [1]
                drainage_resistance: Drainage resistance from groundwater to open water [d]
                seepage_resistance: Vertical flow resistance from shallow to deep groundwater [d]
                infiltration_recession: Infiltration store recession constant ratio
                hydraulic_head: Predefined hydraulic head of deep groundwater [m-SL]
                downward_seepage: Predefined constant flux from shallow to deep groundwater [mm/d]
                soil_type: Soil type
                crop_type: Crop type
                dt: Time step [day]
        """
        self.groundwater_data = groundwater_data
        self.groundwater_data.area = params['groundwater']['area']
        self.groundwater_data.storage_coefficient = 0

        self.roof_area = params['roof']['area']
        self.pavement_area = params['pavement']['area']
        self.pervious_area = params['pervious']['area']
        self.vadose_area = params['vadose']['area']

        self.groundwater_data.leakage_rate = params['groundwater']['leakage_rate'] / 100
        self.groundwater_data.seepage_model = params['groundwater']['seepage_model']
        self.groundwater_data.drainage_resistance = params['groundwater']['drainage_resistance']
        self.groundwater_data.seepage_resistance = params['groundwater']['seepage_resistance']
        self.groundwater_data.infiltration_recession = params['groundwater']['infiltration_recession']
        self.groundwater_data.hydraulic_head = params['groundwater']['hydraulic_head']
        self.groundwater_data.downward_seepage = params['groundwater']['downward_seepage']

        self.indoor_water_use = params['general']['indoor_water_use']
        self.time_step = params['general']['time_step']
        soil_type = params['soil']['soil_type']
        crop_type = params['soil']['crop_type']
        self.soil_params = soil_selector(soil_data, et_data, soil_type, crop_type)

    def solve(self, forcing: pd.Series) -> None:
        """
        Calculates the groundwater dynamics for the current time step.

        Args:

            forcing (pd.DataFrame): Climate forcing data with columns:
                open_water_level: Open water level [m-SL]

        Updates groundwater_data with:
            water_level: Groundwater level [m-SL]
            surface_water_level: Surface water level [m-SL]
            storage_coefficient: Storage coefficient [-]
        Updates flows with:
            from_vadose: Percolation from vadose zone [L]
            from_pavement: Infiltration from pavement [L]
            from_input: Irrigation and indoor use leakage [L]
            to_output: Seepage and baseflow [L]
            to_wastewater: Pipe infiltration [L]
        """
        data = self.groundwater_data
        open_water_level = forcing.get('open_water_level', 0.0)

        # Calculate total inflow
        irrigation_leakage = (data.flows.get_flow('from_roof') +
                              data.flows.get_flow('from_pavement_leakage') +
                              data.flows.get_flow('from_pervious'))

        indoor_use_leakage = (self.indoor_water_use * data.leakage_rate /
                              (1 - data.leakage_rate))
        leakage = irrigation_leakage + indoor_use_leakage

        vadose_percolation = data.flows.get_flow('from_vadose')
        pavement_infiltration = data.flows.get_flow('from_pavement_infiltration')

        inflow = (leakage + vadose_percolation + pavement_infiltration) / data.area

        # Calculate storage coefficient
        data.storage_coefficient = self._storage_coefficient(data.water_level.previous)

        # Calculate groundwater dynamics
        water_level, seepage, infiltration = self._gw_dynamics(
            inflow, open_water_level, data.storage_coefficient,
            data.water_level.previous,
            data.surface_water_level.previous
        )

        # Calculate baseflow
        baseflow = (inflow - seepage - infiltration - data.storage_coefficient *
                   (data.water_level.previous +
                    data.surface_water_level.previous / data.storage_coefficient -
                    water_level) * 1000)

        # Update water levels
        water_level = max(0,data.water_level.previous +
                          data.surface_water_level.previous / data.storage_coefficient -
                          (inflow - seepage - infiltration - baseflow) / (1000 * data.storage_coefficient))
        surface_water_level = min(0, data.water_level.previous +
                                  data.surface_water_level.previous / data.storage_coefficient -
                                  (inflow - seepage - infiltration - baseflow) /
                                  (1000 * data.storage_coefficient)) * data.storage_coefficient

        data.water_level.amount = water_level
        data.surface_water_level.amount = surface_water_level

        # Update flows
        data.flows.set_flow('seepage', seepage * data.area)
        data.flows.set_flow('baseflow', baseflow * data.area)
        data.flows.set_flow('to_wastewater', -infiltration * data.area)

    def _storage_coefficient(self, initial_level: float) -> float:
        gw_up, gw_low, id_up, id_low = gw_levels(initial_level)
        if initial_level >= MAX_SOIL_DEPTH:
            return self.soil_params[MAX_SOIL_INDEX]['stor_coef']

        return (self.soil_params[id_low]['stor_coef'] +
                (initial_level - gw_low) / (gw_up - gw_low) *
                (self.soil_params[id_up]['stor_coef'] - self.soil_params[id_low]['stor_coef']))


    def _gw_dynamics(self, inflow: float, open_water_level: float, storage_coefficient: float,
                    initial_level: float, above_level: float) -> Tuple[float, float, float]:
        """Calculate groundwater dynamics."""
        data = self.groundwater_data
        if data.seepage_model > INFILTRATION_FACTOR:
            water_level = self._dynamic_flux(inflow, open_water_level, storage_coefficient,
                                             initial_level, above_level)
            avg_water_level = 0.5 * (water_level + initial_level + above_level)
            seepage = ((data.hydraulic_head - avg_water_level) * 1000 *
                      self.time_step / data.seepage_resistance)
            infiltration = (3.0 - avg_water_level) * 1000 * data.infiltration_recession * self.time_step
        else:
            water_level = self._constant_flux(inflow, open_water_level, storage_coefficient,
                                            initial_level, above_level)
            avg_water_level = 0.5 * (water_level + initial_level + above_level)
            seepage = data.downward_seepage * self.time_step
            infiltration = (3.0 - avg_water_level) * 1000 * data.infiltration_recession * self.time_step

        return water_level, seepage, infiltration

    def _dynamic_flux(self, inflow: float, open_water_level: float,
                     storage_coefficient: float, initial_level: float,
                     above_level: float) -> float:
        """Calculate water level for dynamic flux model."""
        data = self.groundwater_data
        numerator = (inflow/1000 * data.drainage_resistance * data.seepage_resistance -
                     data.hydraulic_head * data.drainage_resistance -
                     open_water_level * data.seepage_resistance -
                     3.0 * data.infiltration_recession * data.drainage_resistance * data.seepage_resistance)
        denominator = (data.drainage_resistance + data.seepage_resistance +
                       data.infiltration_recession * data.drainage_resistance * data.seepage_resistance)

        exp_term = np.exp(-self.time_step * denominator /
                          (storage_coefficient * data.drainage_resistance * data.seepage_resistance))

        return -(numerator/denominator + (-(initial_level + above_level) - numerator/denominator) * exp_term)

    def _constant_flux(self, inflow: float, open_water_level: float,
                      storage_coefficient: float, initial_level: float,
                      above_level: float) -> float:
        """Calculate water level for constant flux model."""
        data = self.groundwater_data
        numerator = ((inflow - data.downward_seepage)/1000 * data.drainage_resistance -
                     3.0 * data.infiltration_recession * data.drainage_resistance - open_water_level)
        denominator = 1 + data.infiltration_recession * data.drainage_resistance

        exp_term = np.exp(-self.time_step * denominator / (storage_coefficient * data.drainage_resistance))

        return -(numerator/denominator + (-(initial_level + above_level) - numerator/denominator) * exp_term)