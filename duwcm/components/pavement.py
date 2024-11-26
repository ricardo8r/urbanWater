from typing import Dict, Any, Tuple
import pandas as pd
from duwcm.data_structures import PavementData

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

        self.pavement_data.flows.set_areas(self.pavement_data.area)
        self.pavement_data.storage.set_area(self.pavement_data.area)
        self.pavement_data.storage.set_capacity(params['pavement']['max_storage'], 'mm')
        self.pavement_data.storage.set_previous(0, 'mm')

        self.pavement_data.effective_outflow = (1.0 if params['pervious']['area'] == 0
                                                else params['pavement']['effective_area'] / 100)
        self.pavement_data.infiltration_capacity = (params['pavement']['infiltration_capacity'] *
                                               params['pavement']['area']) * 0.001
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

        if data.area == 0:
            return

        data.flows.set_flow('precipitation', forcing['precipitation'], 'mm')
        data.flows.set_flow('from_demand', forcing.get('pavement_irrigation', 0.0), 'mm')
        raintank_inflow = data.flows.get_flow('from_raintank')

        inflow = (data.flows.get_flow('precipitation', 'm3') +
                  data.flows.get_flow('from_demand', 'm3') +
                  raintank_inflow)

        storage = min(data.storage.get_capacity('m3'), max(0.0, data.storage.get_previous('m3') + inflow))

        data.flows.set_flow('evaporation', forcing['potential_evaporation'], 'mm')
        data.flows.set_flow('evaporation', min(data.flows.get_flow('evaporation', 'm3'), storage), 'm3')

        data.storage.set_amount(storage - data.flows.get_flow('evaporation', 'm3'), 'm3')

        data.flows.set_flow('to_groundwater_infiltration',
                            max(0.0, min(data.infiltration_capacity * self.time_step,
                                         inflow - data.storage.get_capacity('m3') +
                                         data.storage.get_previous('m3'))), 'm3')

        excess_water = (inflow -
                        data.flows.get_flow('evaporation', 'm3') -
                        data.flows.get_flow('to_groundwater_infiltration', 'm3') -
                        data.storage.get_change('m3'))
        effective_runoff = data.effective_outflow * max(0.0, excess_water)
        non_effective_runoff = max(0.0, excess_water - effective_runoff)

        data.flows.set_flow('to_stormwater', effective_runoff, 'm3')
        data.flows.set_flow('to_pervious', non_effective_runoff, 'm3')
        data.flows.set_flow('to_groundwater_leakage',data.flows.get_flow('from_demand', 'm3') *
                            self.leakage_rate / (1 - self.leakage_rate), 'm3')
        data.flows.set_flow('from_demand', data.flows.get_flow('from_demand', 'm3') /
                            (1 - self.leakage_rate), 'm3')
