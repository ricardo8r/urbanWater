from typing import Dict, Any, Tuple
import pandas as pd
from duwcm.data_structures import PavementData

# Constants
TO_METERS = 0.001

class PavementClass:
    """
    Calculates water balance for a pavement surface.

    Inflows: Precipitation, irrigation, runoff from rain tank
    Outflows: Evaporation, infiltration, effective runoff, non-effective runoff
    """

    def __init__(self, params: Dict[str, Dict[str, Any]], pavement_data: PavementData):
        """
        Args:
            params (Dict[str, float]): Surface parameters
                area: Paved area [m²]
                effective_area: Effective pavement area ratio [%]
                capcity: Maximum storage capacity [m³]
                previous: Initial storage [m³]
                infiltration_capacity: Pavement infiltration capacity to groundwater [m³/d]
                time_step: Time step [day]
        """
        self.pavement_data = pavement_data
        self.pavement_data.area = params['pavement']['area']

        self.pavement_data.storage.set_area(self.pavement_data.area)
        self.pavement_data.storage.set_capacity(params['pavement']['max_storage'], 'mm')
        self.pavement_data.storage.set_previous(0, 'mm')

        self.pavement_data.effective_outflow = (1.0 if params['pervious']['area'] == 0
                                                else params['pavement']['effective_area'] / 100)
        self.pavement_data.infiltration_capacity = (params['pavement']['infiltration_capacity'] *
                                               params['pavement']['area']) * TO_METERS
        self.leakage_rate = params['groundwater']['leakage_rate'] / 100
        self.time_step = params['general']['time_step']

    def solve(self, forcing: pd.Series) -> None:
        """
        Args:
            forcing (pd.DataFrame): Climate forcing data with columns:
                precipitation: Precipitation [mm]
                potential_evaporation: Potential evaporation [mm]
                irrigation: Irrigation on paved area [mm] (default: 0)

        Updates pavement_data with:
            storage: Final interception storage level (t+1) [m³]
        Updates flows with:
            precipitation: Direct precipitation [m³]
            irrigation: Irrigation [m³]
            from_demand: Demanded water for irrigation + leakage [m³]
            from_raintank: Runoff from rain tank [m³]
            evaporation: Evaporation [m³]
            to_groundwater_infiltration: Infiltration to groundwater [m³]
            to_groundwater_leakage: Leakage from irrigation to groundwater [m³]
            to_stormwater: Effective runoff to stormwater system [m³]
            to_pervious: Non-effective runoff to pervious area [m³]
        """
        data = self.pavement_data
        precipitation = forcing['precipitation'] * TO_METERS * data.area
        potential_evaporation = forcing['potential_evaporation'] * TO_METERS * data.area
        irrigation = forcing.get('pavement_irrigation', 0) * TO_METERS * data.area

        if data.area == 0:
            return

        irrigation_leakage = irrigation * self.leakage_rate / (1 - self.leakage_rate)
        raintank_inflow = data.flows.get_flow('from_raintank')
        inflow = precipitation + irrigation + raintank_inflow

        storage = min(data.storage.get_capacity('m3'), max(0.0, data.storage.get_previous('m3') + inflow))
        evaporation = min(potential_evaporation, storage)

        data.storage.set_amount(storage - evaporation, 'm3')
        infiltration = max(0.0, min(data.infiltration_capacity * self.time_step,
                                    inflow - data.storage.get_capacity('m3') +
                                    data.storage.get_previous('m3')))

        excess_water = inflow - evaporation - infiltration - data.storage.get_change('m3')
        effective_runoff = data.effective_outflow * max(0.0, excess_water)
        non_effective_runoff = max(0.0, excess_water - effective_runoff)


        # Update flows using setters
        data.flows.set_flow('precipitation', precipitation)
        data.flows.set_flow('from_demand', irrigation + irrigation_leakage)
        data.flows.set_flow('evaporation', evaporation)
        data.flows.set_flow('to_stormwater', effective_runoff)
        data.flows.set_flow('to_pervious', non_effective_runoff)
        data.flows.set_flow('to_groundwater_infiltration', infiltration)
        data.flows.set_flow('to_groundwater_leakage', irrigation_leakage)
