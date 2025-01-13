from typing import Dict, Any, Tuple
import pandas as pd
from duwcm.data_structures import ImperviousData

class ImperviousClass:
    """
    Calculates water balance for a impervious surface.

    Inflows: Precipitation, irrigation, runoff from rain tank
    Outflows: Evaporation, infiltration, effective runoff, non-effective runoff
    """

    def __init__(self, params: Dict[str, Dict[str, Any]], impervious_data: ImperviousData):
        """
        Args:
            params (Dict[str, float]): Surface parameters
                area: Paved area [m²]
                effective_area: Effective impervious area ratio [%]
                capcity: Maximum storage capacity [m³]
                previous: Initial storage [m³]
                infiltration_capacity: impervious infiltration capacity to groundwater [m³/d]
                time_step: Time step [day]
        """
        self.impervious_data = impervious_data
        self.impervious_data.area = params['impervious']['area']

        self.impervious_data.flows.set_areas(self.impervious_data.area)
        self.impervious_data.storage.set_area(self.impervious_data.area)
        self.impervious_data.storage.set_capacity(params['impervious']['max_storage'], 'mm')
        self.impervious_data.storage.set_previous(0, 'mm')

        self.impervious_data.effective_outflow = (1.0 if params['pervious']['area'] == 0
                                                else params['impervious']['effective_area'] / 100)
        self.time_step = params['general']['time_step']

    def solve(self, forcing: pd.Series) -> None:
        """
        Args:
            forcing (pd.DataFrame): Climate forcing data with columns:
                precipitation: Precipitation [mm]
                potential_evaporation: Potential evaporation [mm]
                irrigation: Irrigation on paved area [mm] (default: 0)

        Updates impervious_data with:
            storage: Final interception storage level (t+1) [m³]
        Updates flows with:
            precipitation: Direct precipitation [m³]
            irrigation: Irrigation [m³]
            from_demand: Demanded water for irrigation + leakage [m³]
            from_raintank: Runoff from rain tank [m³]
            evaporation: Evaporation [m³]
            to_stormwater: Effective runoff to stormwater system [m³]
            to_pervious: Non-effective runoff to pervious area [m³]
        """
        data = self.impervious_data

        if data.area == 0:
            return

        data.flows.set_flow('precipitation', forcing['precipitation'], 'mm')
        data.flows.set_flow('from_demand', forcing.get('impervious_irrigation', 0.0), 'mm')
        raintank_inflow = data.flows.get_flow('from_raintank')

        inflow = (data.flows.get_flow('precipitation', 'm3') +
                  data.flows.get_flow('from_demand', 'm3') +
                  raintank_inflow)

        storage = min(data.storage.get_capacity('m3'), max(0.0, data.storage.get_previous('m3') + inflow))

        data.flows.set_flow('evaporation', forcing['potential_evaporation'], 'mm')
        data.flows.set_flow('evaporation', min(data.flows.get_flow('evaporation', 'm3'), storage), 'm3')

        data.storage.set_amount(storage - data.flows.get_flow('evaporation', 'm3'), 'm3')

        excess_water = (inflow -
                        data.flows.get_flow('evaporation', 'm3') -
                        data.storage.get_change('m3'))
        effective_runoff = data.effective_outflow * max(0.0, excess_water)
        non_effective_runoff = max(0.0, excess_water - effective_runoff)

        data.flows.set_flow('to_stormwater', effective_runoff, 'm3')
        data.flows.set_flow('to_pervious', non_effective_runoff, 'm3')
