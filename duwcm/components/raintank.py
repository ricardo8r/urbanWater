from typing import Dict, Any, Tuple
import pandas as pd
from duwcm.data_structures import UrbanWaterData, RainTankData, RainTankFlowsData, Flow

class RainTankClass:
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
        self.is_open = params['raintank']['is_open']
        raintank_total_ratio = params['general']['number_houses'] * params['raintank']['install_ratio'] / 100
        self.install_ratio = params['raintank']['install_ratio'] / 100
        self.area = params['raintank']['area'] * raintank_total_ratio
        self.capacity = params['raintank']['capacity'] * raintank_total_ratio
        self.first_flush = params['raintank']['first_flush'] * raintank_total_ratio
        self.effective_system_outflow = (1.0 if params['pavement']['area'] == 0
                                         else params['raintank']['effective_system_outflow'] / 100)
        self.roof_area = params['roof']['area']

    def solve(self, forcing: pd.Series, previous_state: UrbanWaterData,
              current_state: UrbanWaterData) -> Tuple[RainTankData, RainTankFlowsData]:
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

        previous_storage = previous_state.raintank.storage
        roof_runoff = current_state.roof.effective_runoff

        if self.capacity == 0:
            system_outflow = roof_runoff * self.roof_area
            runoff_stormwater = self.effective_system_outflow * system_outflow
            runoff_pavement = system_outflow - runoff_stormwater
            return self._zero_balance(system_outflow, runoff_stormwater, runoff_pavement)

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

        runoff_stormwater = self.effective_system_outflow * system_outflow
        runoff_pavement = system_outflow - runoff_stormwater

        raintank_data = RainTankData(
            first_flush=first_flush,
            inflow=inflow,
            overflow=overflow,
            evaporation=evaporation,
            runoff_stormwater=runoff_stormwater,
            runoff_pavement=runoff_pavement,
            system_outflow=system_outflow,
            storage=final_storage,
            water_balance=water_balance
        )

        raintank_flows = RainTankFlowsData(flows=[
            Flow(
                source="roof",
                destination="raintank",
                variable="runoff",
                amount=roof_runoff * self.roof_area * self.install_ratio,
                unit="L"
            ),
            Flow(
                source="input",
                destination="raintank",
                variable="precipitation",
                amount=self.is_open * precipitation * self.area,
                unit="L"
            ),
            Flow(
                source="raintank",
                destination="output",
                variable="evaporation",
                amount=evaporation,
                unit="L"
            ),
            Flow(
                source="raintank",
                destination="stormwater",
                variable="runoff",
                amount=runoff_stormwater,
                unit="L"
            ),
            Flow(
                source="raintank",
                destination="pavement",
                variable="runoff",
                amount=runoff_pavement,
                unit="L"
            ),
        ])

        return raintank_data, raintank_flows

    @staticmethod
    def _zero_balance(system_outflow: float, runoff_stormwater: float,
                      runoff_pavement: float) -> Tuple[RainTankData, RainTankFlowsData]:
        return RainTankData(
            first_flush=0.0,
            inflow=0.0,
            overflow=0.0,
            evaporation=0.0,
            runoff_stormwater=runoff_stormwater,
            runoff_pavement=runoff_pavement,
            system_outflow=system_outflow,
            storage=0.0,
            water_balance=0.0
        ), RainTankFlowsData(flows=[
            Flow(
                source="raintank",
                destination="output",
                variable="evaporation",
                amount=0.0,
                unit="L"
            ),
            Flow(
                source="raintank",
                destination="stormwater",
                variable="runoff",
                amount=runoff_stormwater,
                unit="L"
            ),
            Flow(
                source="raintank",
                destination="pavement",
                variable="runoff",
                amount=runoff_pavement,
                unit="L"
            )
        ])