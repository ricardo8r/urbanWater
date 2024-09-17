from typing import Dict, Any
import pandas as pd
from duwcm.data_structures import UrbanWaterData, PavementData

class PavementClass:
    """
    Calculates water balance for a pavement surface.

    Inflows: Precipitation, irrigation, runoff from rain tank
    Outflows: Evaporation, infiltration, effective runoff, non-effective runoff
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
        self.area = params['pavement']['area']
        self.effective_area = (1.0 if params['pervious']['area'] == 0
                               else params['pavement']['effective_area'] / 100)
        self.max_storage = params['pavement']['max_storage']
        self.infiltration_capacity = params['pavement']['infiltration_capacity']
        self.time_step = params['general']['time_step']

    def solve(self, forcing: pd.Series, previous_state: UrbanWaterData,
              current_state: UrbanWaterData) -> PavementData:
        """
        Args:
            forcing (pd.DataFrame): Climate forcing data with columns:
                precipitation: Precipitation [mm]
                potential_evaporation: Potential evaporation [mm]
                irrigation: Irrigation on paved area [mm] (default: 0)
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
        irrigation = forcing.get('pavement_irrigation', 0)

        previous_storage = previous_state.pavement.storage
        raintank_runoff = current_state.raintank.runoff_pavement

        if self.area == 0:
            return self._zero_balance()

        inflow = raintank_runoff / self.area
        total_inflow = precipitation + irrigation + inflow

        current_storage = min(self.max_storage, max(0.0, previous_storage + total_inflow))
        evaporation = min(potential_evaporation, current_storage)

        final_storage = current_storage - evaporation
        infiltration = max(0.0, min(total_inflow - (self.max_storage - previous_storage),
                                    self.infiltration_capacity * self.time_step))

        excess_water = (total_inflow - evaporation - infiltration -
                        (final_storage - previous_storage))
        effective_runoff = self.effective_area * max(0.0, excess_water)
        non_effective_runoff = max(0.0, excess_water - effective_runoff)

        water_balance = (excess_water - effective_runoff - non_effective_runoff) * self.area

        return PavementData(
            inflow = inflow,
            evaporation = evaporation,
            infiltration = infiltration,
            effective_runoff = effective_runoff,
            non_effective_runoff = non_effective_runoff,
            storage = final_storage,
            water_balance = water_balance
        )

    @staticmethod
    def _zero_balance() -> PavementData:
        return PavementData(
            inflow = 0.0,
            evaporation = 0.0,
            infiltration = 0.0,
            effective_runoff = 0.0,
            non_effective_runoff = 0.0,
            storage = 0.0,
            water_balance = 0.0
        )
