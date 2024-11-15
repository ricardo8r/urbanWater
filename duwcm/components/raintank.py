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
                area: Rain tank area [m2]
                capacity: Rain tank capacity [L]
                first_flush: Predefined first flush [L]
                effective_outflow: Effective runoff from roof to pavement [%]
                install_ratio: Houses with rain tank [%]
                number_houses: Number of houses per cell []
                roof_area: Roof area [m2]
        """
        self.raintank_data = raintank_data
        self.raintank_data.is_open = params['raintank']['is_open']
        self.raintank_data.install_ratio = params['raintank']['install_ratio'] / 100
        raintank_total_ratio = params['general']['number_houses'] * params['raintank']['install_ratio'] / 100
        self.raintank_data.storage.capacity = params['raintank']['capacity'] * raintank_total_ratio
        self.raintank_data.area = params['raintank']['area'] * raintank_total_ratio
        self.raintank_data.first_flush = params['raintank']['first_flush'] * raintank_total_ratio
        self.raintank_data.effective_outflow = (1.0 if  params['pavement']['area'] == 0
                                            else params['raintank']['effective_area'] / 100)

        self.roof_area = params['roof']['area']

    def solve(self, forcing: pd.Series) -> None:
        """
        Args:
            forcing (pd.DataFrame): Climate forcing data with columns:
                precipitation: Precipitation [mm]
                potential_evaporation: Potential evaporation [mm]

        Updates raintank_data with:
            storage: Rain tank storage volume after all outflows (t+1) [L]
        Updates flows with:
            precipitation: Direct precipitation if tank is open [L]
            from_roof: Effective runoff from roof area [L]
            evaporation: Evaporation if tank is open [L]
            to_stormwater: First flush and effective overflow to stormwater system [L]
            to_pavement: Non-effective overflow to pavement [L]

        Notes:
            - Unlike other components that use mm for storage, rain tank uses liters (L)
            - First flush is diverted to stormwater before storage
            - Overflow is split between stormwater and pavement based on effective_outflow ratio
            - Only installed tanks (based on install_ratio) receive roof runoff
        """
        data = self.raintank_data
        precipitation = forcing['precipitation'] * data.area
        potential_evaporation = forcing['potential_evaporation'] * data.area

        roof_inflow = data.flows.get_flow('from_roof')

        if data.storage.capacity == 0:
            system_outflow = roof_inflow
            runoff_stormwater = data.effective_outflow * system_outflow
            runoff_pavement = system_outflow - runoff_stormwater

            # Update flows for zero capacity case
            data.flows.set_flow('to_stormwater', runoff_stormwater)
            data.flows.set_flow('to_pavement', runoff_pavement)
            return

        first_flush = min(roof_inflow * data.install_ratio,
                          data.first_flush)
        inflow = (roof_inflow * data.install_ratio - first_flush +
                            data.is_open * precipitation)

        data.storage.amount = min(data.storage.capacity, max(0.0, data.storage.previous + inflow))
        evaporation = data.is_open * min(potential_evaporation, data.storage.amount)
        data.storage.amount -= evaporation

        overflow = max(0.0, inflow - evaporation - data.storage.change)
        system_outflow = first_flush + overflow + roof_inflow * (1.0 - data.install_ratio)

        runoff_stormwater = data.effective_outflow * system_outflow
        runoff_pavement = system_outflow - runoff_stormwater


        # Update flows using setters
        if data.is_open:
            data.flows.set_flow('precipitation', precipitation)
        data.flows.set_flow('evaporation', evaporation)
        data.flows.set_flow('to_stormwater', runoff_stormwater)
        data.flows.set_flow('to_pavement', runoff_pavement)