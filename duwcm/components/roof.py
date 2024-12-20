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
                area: Roof area [m²]
                effective_outflow: Area connected with gutter [%]
                storage capacity: Roof storage capacity [mm]
                roof_initial_storage: Roof initial storage (t=0) [mm]
                leakage_rate: Leakage to groundwater [%]
                time_step: Time step [day]
        """
        self.roof_data = roof_data
        self.roof_data.area = abs(params['roof']['area'])  #TODO

        self.roof_data.flows.set_areas(self.roof_data.area)
        self.roof_data.storage.set_area(self.roof_data.area)
        self.roof_data.storage.set_capacity(params['roof']['max_storage'], 'mm')
        self.roof_data.storage.set_previous(0, 'mm')

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
            storage: Roof interception storage volume after total outflows (t+1) [m³]
        Updates flows with:
            precipitation: Direct precipitation [m³]
            irrigation: Irrigation [m³]
            from_demand: Demanded water for irrigation + leakage [m³]
            evaporation: Evaporation [m³]
            to_raintank: Effective impervious surface runoff [m³]
            to_pervious: Non-effective runoff [m³]
            to_groundwater: Irrigation leakage [m³]
        """
        data = self.roof_data

        if data.area == 0:
            return

        data.flows.set_flow('precipitation', forcing['precipitation'], 'mm')
        data.flows.set_flow('from_demand', forcing.get('roof_irrigation', 0.0), 'mm')

        total_inflow = data.flows.get_flow('precipitation', 'm3') + data.flows.get_flow('from_demand', 'm3')
        current_storage = min(data.storage.get_capacity('m3'), max(0.0, data.storage.get_previous('m3') + total_inflow))

        data.flows.set_flow('evaporation', forcing['potential_evaporation'], 'mm')
        data.flows.set_flow('evaporation', min(data.flows.get_flow('evaporation', 'm3'), current_storage), 'm3')
        data.storage.set_amount(current_storage - data.flows.get_flow('evaporation', 'm3'), 'm3')

        excess_water = total_inflow - data.flows.get_flow('evaporation', 'm3') - data.storage.get_change('m3')
        effective_runoff = data.effective_outflow * max(0.0, excess_water)
        non_effective_runoff = max(0.0, excess_water - effective_runoff)

        excess_runoff = data.flows.set_flow('to_raintank', effective_runoff, 'm3')
        data.flows.set_flow('to_stormwater', excess_runoff, 'm3')
        data.flows.set_flow('to_pervious', non_effective_runoff, 'm3')
        data.flows.set_flow('to_groundwater',data.flows.get_flow('from_demand', 'm3') *
                            self.leakage_rate / (1 - self.leakage_rate), 'm3')
        data.flows.set_flow('from_demand', data.flows.get_flow('from_demand', 'm3') /
                            (1 - self.leakage_rate), 'm3')