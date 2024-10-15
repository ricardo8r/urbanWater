from typing import Dict, Any, Tuple
import pandas as pd
from duwcm.data_structures import UrbanWaterData, RoofData, RoofFlowsData, Flow

class RoofClass:
    """
    Calculates water balance for a roof surface.

    Inflows: precipitation, irrigation
    Outflows: evaporation, effective runoff, non-effectiverunoff
    """

    def __init__(self, params: Dict[str, Dict[str, Any]]):
        """
        Args:
            params (Dict[str, float]): System parameters
                area: Roof area [m^2]
                effective_roof_area: Area connected with gutter [%]
                roof_initial_loss: Maximum initial loss [mm]
                roof_current_storage: Roof initial storage (t=0) [mm]
                time_step: Time step [day]
        """
        self.area = params['roof']['area']
        self.effective_area_ratio = (1.0 if  params['pervious']['area'] == 0
                                     else params['roof']['effective_area'] / 100)
        self.max_storage = params['roof']['max_storage']
        self.time_step = params['general']['time_step']

    def solve(self, forcing: pd.Series, previous_state: UrbanWaterData,
              current_state: UrbanWaterData) -> Tuple[RoofData, RoofFlowsData]:
        """
        Args: 
            forcing (pd.DataFrame): Climate forcing data with columns:
                precipitation: Precipitation [mm]
                potential_evaporation: Potential evaporation [mm]
                irrigation: Irrigation on roof (default: 0) [mm]
            previous_state (pd.DataFrame): State variables from the previous time step with columns:
                Roof:
                    previous_storage: Initial storage at the current time step (t) [L]

        Returns:
            Dict[str, float]: Water balance components for the current time step
                evaporation: Evaporation from interception storage in roof [mm]
                effective_runoff: Effective impervious surface runoff (Rain tank and sewer) [mm]
                non_effective_runoff: Non effective runoff (pavement and pervious)
                storage: Roof interception storage after total ouflows (t+1) [mm]
                water_balance: Total water balance [L]
        """
        precipitation = forcing['precipitation']
        potential_evaporation = forcing['potential_evaporation']
        irrigation = forcing.get('roof_irrigation', 0.0)

        previous_storage = previous_state.roof.storage

        if self.area == 0:
            return self._zero_balance()

        total_inflow = precipitation + irrigation
        current_storage = min(self.max_storage, max(0.0, previous_storage + total_inflow))
        evaporation = min(potential_evaporation, current_storage)
        final_storage = current_storage - evaporation

        excess_water = total_inflow - evaporation - (final_storage - previous_storage)
        effective_runoff = self.effective_area_ratio * max(0.0, excess_water)
        non_effective_runoff = max(0.0, excess_water - effective_runoff)

        water_balance = (excess_water - effective_runoff - non_effective_runoff) * self.area

        roof_data = RoofData(
            evaporation = evaporation * self.area,
            effective_runoff = effective_runoff,
            non_effective_runoff = non_effective_runoff,
            storage = final_storage,
            water_balance = water_balance
        )

        roof_flows = RoofFlowsData(flows=[
            Flow(
                source="atmosphere",
                destination="roof",
                variable="precipitation",
                amount=precipitation * self.area,
                unit="L"
            ),
            Flow(
                source="external",
                destination="roof",
                variable="irrigation",
                amount=irrigation * self.area,
                unit="L"
            ),
            Flow(
                source="roof",
                destination="raintank",
                variable="effective_runoff",
                amount=effective_runoff * self.area,
                unit="L"
            ),
            Flow(
                source="roof",
                destination="pervious",
                variable="non_effective_runoff",
                amount=non_effective_runoff * self.area,
                unit="L"
            ),
            Flow(
                source="roof",
                destination="atmosphere",
                variable="evaporation",
                amount=evaporation * self.area,
                unit="L"
            )
        ])

        return roof_data, roof_flows

    @staticmethod
    def _zero_balance() -> Tuple[RoofData, RoofFlowsData]:
        return RoofData(
            irrigation = 0.0,
            evaporation = 0.0,
            effective_runoff = 0.0,
            non_effective_runoff = 0.0,
            storage = 0.0,
            water_balance = 0.0
        ), RoofFlowsData(flows=[])