from typing import Dict, Any, Tuple
import pandas as pd
from duwcm.data_structures import UrbanWaterData, GroundwaterData
from duwcm.functions.selector import soil_selector
from duwcm.functions.gwlcalculator import gw_levels

# Constants
MAX_SOIL_DEPTH = 10.0
MAX_SOIL_INDEX = 29
PIPE_HEIGHT = 3.0
INFILTRATION_FACTOR = 0.5

class GroundwaterClass:
    """
    Simulates groundwater dynamics

    Inflows: Leakage (irrigation + indoor water usage), vadose zone percolation,
            pavement infiltration
    Outflows: Seepage to deep groundwater, baseflow to open water, pipe insfiltration
    """
    def __init__(self, params: Dict[str, Dict[str, Any]], soil_data: pd.DataFrame, et_data: pd.DataFrame):
        """
        Args:
            params (Dict[str, float]): Groundwater parameters
                Area: Groundwater area [m^2]
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
        self.area = params['groundwater']['area']
        self.roof_area = params['roof']['area']
        self.pavement_area = params['pavement']['area']
        self.pervious_area = params['pervious']['area']
        self.vadose_area = params['vadose']['area']
        self.leakage_rate = params['groundwater']['leakage_rate'] / 100
        self.seepage_model = params['groundwater']['seepage_model']
        self.drainage_resistance = params['groundwater']['drainage_resistance']
        self.seepage_resistance = params['groundwater']['seepage_resistance']
        self.infiltration_recession = params['groundwater']['infiltration_recession']
        self.hydraulic_head = params['groundwater']['hydraulic_head']
        self.downward_seepage = params['groundwater']['downward_seepage']
        self.indoor_water_use = params['general']['indoor_water_use']
        self.time_step = params['general']['time_step']

        soil_type = params['soil']['soil_type']
        crop_type = params['soil']['crop_type']
        self.soil_params = soil_selector(soil_data, et_data, soil_type, crop_type)

    def solve(self, forcing: pd.Series, previous_state: UrbanWaterData,
              current_state: UrbanWaterData) -> GroundwaterData:
        """
        Calculates the groundwater dynamics for the current time step.

        Args:

            forcing (pd.DataFrame): Climate forcing data with columns:
                roof_irrigation: Irrigation on roof area [mm]
                pavement_irrigation: Irrigation on pavement area [mm]
                pervious_irrigation: Irrigation on pervious area [mm]
                open_water_level: Open water level [m-SL]
            previous_state (pd.DataFrame): State variables from the previous time step with columns:
                Groundwater:
                    initial_level: Groundwater storage level [m-SL]
            current_state (pd.DataFrame): Current state variables with columns:
                Vadose zone:
                    vadose_percolation: Percolation from vadose zone [mm m^2]
                Pavement:
                    pavement_infiltration: Infiltration from pavement to groundwater [mm m^2]

        Returns:
            Dict[str, float]: Computed states and fluxes of groundwater during current time step
                total_irrigation: Total irrigation [L]
                leakage_depth: Leakage depth [mm]
                inflow: Percolation from vadose zone and infiltration from road [mm]
                storage_coefficient: Storage coefficient
                seepage: Seepage from groundwater to deep groundwater [L]
                pipe_infiltration: Infiltration to wastewater pipe [L]
                baseflow: Flow to open water [L]
                water_level: Groundwater level [m]
                water_balance: Total water balance [L]
        """
        roof_irrigation = forcing.get('roof_irrigation', 0.0)
        pavement_irrigation = forcing.get('pavement_irrigation', 0.0)
        pervious_irrigation = forcing.get('pervious_irrigation', 0.0)
        open_water_level = forcing.get('open_water_level', 0.0)

        initial_level = previous_state.groundwater.water_level
        vadose_percolation = current_state.vadose.percolation
        pavement_infiltration = current_state.pavement.infiltration

        total_irrigation = (roof_irrigation * self.roof_area +
                            pavement_irrigation * self.pavement_area +
                            pervious_irrigation * self.pervious_area)

        leakage_depth = ((total_irrigation + self.indoor_water_use) * self.leakage_rate /
                         (1 - self.leakage_rate)) / self.area

        inflow = (leakage_depth + (vadose_percolation * self.vadose_area +
                                   pavement_infiltration * self.pavement_area) / self.area)


        storage_coefficient = self._storage_coefficient(initial_level)

        water_level, baseflow, seepage, infiltration = self._gw_dynamics(inflow, open_water_level,
                                                                         storage_coefficient, initial_level)

        water_balance = (inflow - seepage - infiltration - baseflow -
                         initial_level - water_level) * self.area
        seepage = seepage * self.area
        baseflow = baseflow * self.area
        infiltration = infiltration * self.area


        return GroundwaterData(
            total_irrigation = total_irrigation,
            leakage_depth = leakage_depth,
            inflow = inflow,
            storage_coefficient = storage_coefficient,
            seepage = seepage,
            baseflow = baseflow,
            pipe_infiltration = infiltration,
            water_level = water_level,
            water_balance = water_balance
        )

    def _storage_coefficient(self, initial_level: float) -> float:
        gw_up, gw_low, id_up, id_low = gw_levels(initial_level)
        if initial_level > MAX_SOIL_DEPTH:
            return self.soil_params[MAX_SOIL_INDEX]['stor_coef']

        return (self.soil_params[id_low]['stor_coef'] +
                (initial_level - gw_low) / (gw_up - gw_low) *
                (self.soil_params[id_up]['stor_coef'] - self.soil_params[id_low]['stor_coef']))

    def _gw_dynamics(self, inflow: float, open_water_level: float, storage_coefficient: float,
                     initial_level: float) -> Tuple[float, float, float]:
        if self.drainage_resistance == 0:
            baseflow = 0
        else:
            baseflow = (initial_level - open_water_level) / self.drainage_resistance

        infiltration = (initial_level - PIPE_HEIGHT) * self.infiltration_recession

        if self.seepage_model > INFILTRATION_FACTOR:
            seepage = (initial_level - self.hydraulic_head) / self.seepage_resistance
        else:
            seepage = self.downward_seepage

        water_level = (initial_level + (inflow - seepage - baseflow - infiltration) *
                       self.time_step / storage_coefficient)

        return water_level, seepage, baseflow, infiltration