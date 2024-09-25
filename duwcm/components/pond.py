from typing import Dict, Any
import pandas as pd
from duwcm.data_structures import UrbanWaterData, PondData

class PondClass:
    """
    Calculates water balance for a pond.

    Inflows: Precipitation, runoff from ....
    Outflows: Evaporation, infiltration, overflow
    """

    def __init__(self, params: Dict[str, Dict[str, Any]]):
        """
        Args:
            params (Dict[str, float]): Surface parameters
                area: Paved area [m^2]
                effective_area: Effective pavement area ratio [%]
                max_storage: Maximum storage capacity [mm]
                infiltration_capacity: Pavement infiltration capacity to groundwater [mm/d]
                time_step: Time step [day]
        """
        self.area = params['pond']['area']
        self.max_storage = params['pond']['max_storage']
        self.infiltration_capacity = params['pond']['infiltration_capacity']
        self.time_step = params['general']['time_step']

    def solve(self, forcing: pd.Series, previous_state: UrbanWaterData,
              current_state: UrbanWaterData) -> PondData:
        """
        Args:
            forcing (pd.DataFrame): Climate forcing data with columns:
                precipitation: Precipitation [mm]
                potential_evaporation: Potential evaporation [mm]
            previous_state (pd.DataFrame): State variables from the previous time step with columns:
                Pavement:
                    previous_storage: Initial storage at current time step (t) [L]
            current_state (pd.DataFrame): Current state variables with columns:
                Rain tank:
                    raintank_runoff: Effective imprevious surface runoff from raintank to pavement [L]

        Returns:
            Dict[str, float]:
                inflow: Effective impervious surface runoff inflow [mm/m^2]
                evaporation: Evaporation from interception storage on pavement area [mm]
                infiltration: Infiltration to groundwater (if current storage = max storage) [mm]
                effective_runoff: Effective impervious surface runoff [mm]
                non_effective_runoff: Non-effective runoff [mm]
                storage: Final interception storage level (t+1) [mm]
                water_balance: Total water balance [L]
        """
        precipitation = forcing['precipitation']
        potential_evaporation = forcing['potential_evaporation']

        previous_storage = previous_state.pond.storage

        if self.area == 0:
            return self._zero_balance()

        #inflow = #from where
        total_inflow = precipitation #+ inflow

        current_storage = min(self.max_storage, max(0.0, previous_storage + total_inflow))
        evaporation = min(potential_evaporation, current_storage)

        final_storage = current_storage - evaporation
        infiltration = max(0.0, min(total_inflow - (self.max_storage - previous_storage),
                                    self.infiltration_capacity * self.time_step))

        overflow = (total_inflow - evaporation - infiltration -
                        (final_storage - previous_storage))

        water_balance = (overflow - infiltration -evaporation) * self.area

        return PondData(
            #inflow = inflow,
            evaporation = evaporation * self.area,
            infiltration = infiltration,
            overflow = overflow,
            storage = final_storage,
            water_balance = water_balance
        )

    @staticmethod
    def _zero_balance() -> PondData:
        return PondData(
            evaporation = 0.0,
            infiltration = 0.0,
            overflow = 0.0,
            storage = 0.0,
            water_balance = 0.0
        )