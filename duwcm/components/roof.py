from typing import Dict, Any, Tuple
import pandas as pd
from duwcm.data_structures import RoofData

class RoofClass:
    """
    Calculates water balance for a roof surface.

    Inflows: precipitation, irrigation
    Outflows: evaporation, effective runoff, non-effectiverunoff
    """

    def __init__(self, params: Dict[str, Dict[str, Any]], roof_data: RoofData):
        """
        Args:
            params (Dict[str, float]): System parameters
                area: Roof area [m^2]
                effective_outflow: Area connected with gutter [%]
                roof_initial_storage: Roof initial storage (t=0) [mm]
                leakage_rate: Leakage to groundwater [%]
                time_step: Time step [day]
        """
        self.roof_data = roof_data
        self.roof_data.area = params['roof']['area']
        self.roof_data.storage.capacity = params['roof']['max_storage']
        self.roof_data.effective_outflow = (1.0 if  params['pervious']['area'] == 0
                                            else params['roof']['effective_area'] / 100)
        self.leakage_rate = params['groundwater']['leakage_rate'] / 100
        self.time_step = params['general']['time_step']

    def solve(self, forcing: pd.Series) -> None:
        """
        Args: 
            forcing (pd.DataFrame): Climate forcing data with columns:
                precipitation: Precipitation [mm]
                potential_evaporation: Potential evaporation [mm]
                irrigation: Irrigation on roof (default: 0) [mm]
        Data:
            storage: Roof interception storage after total ouflows (t+1) [mm]
        Flows:
            evaporation: Evaporation from interception storage in roof [mm]
            effective_runoff: Effective impervious surface runoff (Rain tank and sewer) [mm]
            non_effective_runoff: Non effective runoff (pavement and pervious)
        """
        precipitation = forcing['precipitation']
        potential_evaporation = forcing['potential_evaporation']
        irrigation = forcing.get('roof_irrigation', 0.0)

        if self.roof_data.area == 0:
            return

        irrigation_leakage = irrigation * self.leakage_rate / (1 - self.leakage_rate)
        total_inflow = precipitation + irrigation
        current_storage = min(self.roof_data.storage.capacity, max(0.0, self.roof_data.storage.previous + total_inflow))
        evaporation = min(potential_evaporation, current_storage)
        final_storage = current_storage - evaporation

        excess_water = total_inflow - evaporation - (final_storage - self.roof_data.storage.previous)
        effective_runoff = self.roof_data.effective_outflow * max(0.0, excess_water)
        non_effective_runoff = max(0.0, excess_water - effective_runoff)

        water_balance = (excess_water - effective_runoff - non_effective_runoff) * self.roof_data.area

        self.roof_data.storage.amount = final_storage


        # Update flows using setters
        self.roof_data.flows.set_flow('precipitation', precipitation * self.roof_data.area)
        self.roof_data.flows.set_flow('irrigation', irrigation * self.roof_data.area)
        self.roof_data.flows.set_flow('evaporation', evaporation * self.roof_data.area)
        self.roof_data.flows.set_flow('to_raintank', effective_runoff * self.roof_data.area)
        self.roof_data.flows.set_flow('to_pervious', non_effective_runoff * self.roof_data.area)
        self.roof_data.flows.set_flow('to_groundwater', irrigation_leakage * self.roof_data.area)