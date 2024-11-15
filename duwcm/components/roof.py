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
                storage capacity: Roof storage capacity [L]
                roof_initial_storage: Roof initial storage (t=0) [mm]
                leakage_rate: Leakage to groundwater [%]
                time_step: Time step [day]
        """
        self.roof_data = roof_data
        self.roof_data.area = abs(params['roof']['area'])  #TODO
        self.roof_data.storage.capacity = (params['roof']['max_storage'] *
                                           params['roof']['area'])
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

        Updates roof_data with:
            storage: Roof interception storage volume after total outflows (t+1) [L]
        Updates flows with:
            to_raintank: Effective impervious surface runoff [L]
            to_pervious: Non-effective runoff [L]
            to_groundwater: Irrigation leakage [L]
        """
        data = self.roof_data
        precipitation = forcing['precipitation'] * data.area
        potential_evaporation = forcing['potential_evaporation'] * data.area
        irrigation = forcing.get('roof_irrigation', 0.0) * data.area

        if data.area == 0:
            return

        irrigation_leakage = irrigation * self.leakage_rate / (1 - self.leakage_rate)
        total_inflow = precipitation + irrigation
        current_storage = min(data.storage.capacity, max(0.0, data.storage.previous + total_inflow))
        evaporation = min(potential_evaporation, current_storage)

        data.storage.amount = current_storage - evaporation

        excess_water = total_inflow - evaporation - data.storage.change
        effective_runoff = data.effective_outflow * max(0.0, excess_water)
        non_effective_runoff = max(0.0, excess_water - effective_runoff)

        # Update flows using setters
        data.flows.set_flow('precipitation', precipitation)
        data.flows.set_flow('irrigation', irrigation)
        data.flows.set_flow('evaporation', evaporation)
        data.flows.set_flow('to_raintank', effective_runoff)
        data.flows.set_flow('to_pervious', non_effective_runoff)
        data.flows.set_flow('to_groundwater', irrigation_leakage)