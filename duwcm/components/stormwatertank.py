from typing import Dict, Any
import pandas as pd
from duwcm.data_structures import UrbanWaterData, StormwaterTankData

class StormwaterTankClass:
    """
    Calculates water balance for a rain tank.

    Inflows: Precipitation, roof runoff
    Outflows: Evaporation, runoff sewer and pavement
    """

    def __init__(self, params: Dict[str, Dict[str, Any]]):
        """
        Args:
            params (Dict[str, Dict[str, Any]]): System parameters
                is_open: is the rain tank open?
                area: Rain tank area [m2]
                capacity: Rain tank capacity [L]
                first_flush: Predefined first flush [L]
                effective_system_outflow: Effective runoff from roof to pavement [%]
                install_ratio: Houses with rain tank [%]
                number_houses: Number of houses per cell []
                roof_area: Roof area [m2]
        """
        self.is_open = params['stormwatertank']['is_open']
        stormwatertank_total_ratio = params['general']['number_houses'] * params['stormwatertank']['install_ratio'] / 100
        self.install_ratio = params['stormwatertank']['install_ratio'] / 100
        self.area = params['stormwatertank']['area'] * stormwatertank_total_ratio
        self.capacity = params['stormwatertank']['capacity'] * stormwatertank_total_ratio
        self.first_flush = params['stormwatertank']['first_flush'] * stormwatertank_total_ratio
        self.effective_system_outflow = (1.0 if params['pavement']['area'] == 0
                                         else params['stormwatertank']['effective_system_outflow'] / 100)

    def solve(self, forcing: pd.Series, previous_state: UrbanWaterData,
              current_state: UrbanWaterData) -> StormwaterTankData:
        """
        Args:
            forcing (pd.DataFrame): Climate forcing data with columns:
                precipitation: Precipitation [mm]
                potential_evaporation: Potential evaporation [mm]
            previous_state (pd.DataFrame): State variables from the previous time step with columns:
                Rain tank:
                    previous_storage: Initial storage at the current time step (t) [L]
            current_state (pd.DataFrame): Current state variables with columns:
                Roof:
                    roof_runoff: Effective impervious surface runoff (collected to rain tank) [mm m^2]

        Returns:
            Dict[str, float]:
                first_flush: First flush [L]
                inflow: Inflow to rain tank [L]
                overflow: Rain tank overflow [L]
                evaporation: Evaporation [L]
                runoff_sewer: Effective impervious surface runoff to storm sewer [L]
                runoff_pavement: Effective impervious surface runoff to pavement [L]
                system_outflow: Outflow from roof-rain tank system [L]
                storage: Final rain tank storage after outflows (t+1) [L]
                water_balance: Total water balance [L]
        """
        precipitation = forcing['precipitation']
        potential_evaporation = forcing['potential_evaporation']

        previous_storage = previous_state.stormwatertank.storage
        roof_runoff = current_state.roof.effective_runoff

        if self.capacity == 0:
            system_outflow = roof_runoff * self.roof_area
            runoff_sewer = self.effective_system_outflow * system_outflow
            runoff_pavement = system_outflow - runoff_sewer
            return self._zero_balance(system_outflow, runoff_sewer, runoff_pavement)

        first_flush = min(roof_runoff * self.roof_area * self.install_ratio,
                                           self.first_flush)
        inflow = (roof_runoff * self.roof_area * self.install_ratio - first_flush +
                            self.is_open * precipitation * self.area)

        current_storage = min(self.capacity, max(0.0, previous_storage + inflow))
        evaporation = self.is_open * min(potential_evaporation * self.area,
                                                current_storage)
        final_storage = current_storage - evaporation

        overflow = max(0.0, inflow - evaporation - (final_storage - previous_storage))
        system_outflow = (first_flush + overflow +
                        roof_runoff * self.roof_area * (1.0 - self.install_ratio))

        water_balance = inflow - (evaporation + overflow) - (final_storage - previous_storage)

        runoff_sewer = self.effective_system_outflow * system_outflow
        runoff_pavement = system_outflow - runoff_sewer


        return StormwaterTankData(
            first_flush=first_flush,
            inflow=inflow,
            overflow=overflow,
            runoff_sewer=runoff_sewer,
            runoff_pavement=runoff_pavement,
            system_outflow=system_outflow,
            storage=final_storage,
            water_balance=water_balance
        )

    @staticmethod
    def _zero_balance(system_outflow: float, runoff_sewer: float, runoff_pavement: float) -> StormwaterTankData:
        return StormwaterTankData(
            first_flush=0.0,
            inflow=0.0,
            overflow=0.0,
            runoff_sewer=runoff_sewer,
            runoff_pavement=runoff_pavement,
            system_outflow=system_outflow,
            storage=0.0,
            water_balance=0.0
        )