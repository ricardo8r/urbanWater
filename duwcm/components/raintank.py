from typing import Dict, Any, Tuple
import pandas as pd
from duwcm.data_structures import RainTankData

class RainTankClass:
    """
    Calculates water balance for a rain tank.

    Inflows: Precipitation, roof runoff
    Outflows: Evaporation, runoff sewer and pavement
    """

    def __init__(self, params: Dict[str, Dict[str, Any]], raintank_data: RainTankData):
        """
        Args:
            params (Dict[str, Dict[str, Any]]): System parameters
                is_open: is the rain tank open?
                area: Rain tank area [m²]
                capacity: Rain tank capacity [m³]
                previous: Rain tank initial storage [m³]
                first_flush: Predefined first flush [m³]
                effective_outflow: Effective runoff from roof to pavement [%]
                install_ratio: Houses with rain tank [%]
                number_houses: Number of houses per cell []
        """
        self.raintank_data = raintank_data
        self.raintank_data.is_open = params['raintank']['is_open']
        self.raintank_data.install_ratio = params['raintank']['install_ratio'] / 100
        raintank_total_ratio = params['general']['number_houses'] * params['raintank']['install_ratio'] / 100
        self.raintank_data.area = params['raintank']['area'] * raintank_total_ratio

        self.raintank_data.flows.set_areas(self.raintank_data.area)
        self.raintank_data.storage.set_area(self.raintank_data.area)
        #self.raintank_data.flows.set_capacity(params['raintank']['capacity'] * raintank_total_ratio, 'L')
        self.raintank_data.storage.set_capacity(params['raintank']['capacity'] * raintank_total_ratio, 'L')
        self.raintank_data.storage.set_previous(params['raintank']['initial_storage'], 'L')

        self.raintank_data.first_flush = params['raintank']['first_flush'] * raintank_total_ratio * 0.001
        self.raintank_data.effective_outflow = (1.0 if  params['pavement']['area'] == 0
                                            else params['raintank']['effective_area'] / 100)

    def solve(self, forcing: pd.Series) -> None:
        """
        Args:
            forcing (pd.DataFrame): Climate forcing data with columns:
                precipitation: Precipitation [mm]
                potential_evaporation: Potential evaporation [mm]

        Updates raintank_data with:
            storage: Rain tank storage volume after all outflows (t+1) [m³]
        Updates flows with:
            precipitation: Direct precipitation if tank is open [m³]
            from_roof: Effective runoff from roof area [m³]
            evaporation: Evaporation if tank is open [m³]
            to_stormwater: First flush and effective overflow to stormwater system [m³]
            to_pavement: Non-effective overflow to pavement [m³]

        Notes:
            - First flush is diverted to stormwater before storage
            - Overflow is split between stormwater and pavement based on effective_outflow ratio
            - Only installed tanks (based on install_ratio) receive roof runoff
        """
        data = self.raintank_data

        roof_inflow = data.flows.get_flow('from_roof', 'm3')

        if data.storage.get_capacity('m3') == 0:
            system_outflow = roof_inflow
            runoff_stormwater = data.effective_outflow * system_outflow
            runoff_pavement = system_outflow - runoff_stormwater

            # Update flows for zero capacity case
            data.flows.set_flow('to_stormwater', runoff_stormwater, 'm3')
            data.flows.set_flow('to_pavement', runoff_pavement, 'm3')
            return

        if data.is_open:
            data.flows.set_flow('precipitation', forcing['precipitation'], 'mm')

        first_flush = min(roof_inflow * data.install_ratio,
                          data.first_flush)
        inflow = (roof_inflow * data.install_ratio - first_flush +
                            data.is_open * data.flows.get_flow('precipitation', 'm3'))

        current_storage = min(data.storage.get_capacity('m3'), max(0.0, data.storage.get_previous('m3') + inflow))

        data.flows.set_flow('evaporation', forcing['potential_evaporation'], 'mm')
        data.flows.set_flow('evaporation', data.is_open *
                            min(data.flows.get_flow('evaporation', 'm3'), current_storage), 'm3')

        data.storage.set_amount(current_storage - data.flows.get_flow('evaporation', 'm3'), 'm3')

        overflow = max(0.0, inflow - data.flows.get_flow('evaporation', 'm3') - data.storage.get_change('m3'))
        system_outflow = first_flush + overflow + roof_inflow * (1.0 - data.install_ratio)

        runoff_stormwater = data.effective_outflow * system_outflow
        runoff_pavement = system_outflow - runoff_stormwater

        data.flows.set_flow('to_stormwater', runoff_stormwater, 'm3')
        data.flows.set_flow('to_pavement', runoff_pavement, 'm3')