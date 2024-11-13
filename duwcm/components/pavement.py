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
                area: Paved area [m^2]
                effective_area: Effective pavement area ratio [%]
                max_storage: Maximum storage capacity [mm]
                infiltration_capacity: Pavement infiltration capacity to groundwater [mm/d]
                time_step: Time step [day]
        """
        self.pavement_data = pavement_data
        self.pavement_data.area = params['pavement']['area']
        self.pavement_data.storage.capacity = params['pavement']['max_storage']
        self.pavement_data.effective_outflow = (1.0 if params['pervious']['area'] == 0
                                                else params['pavement']['effective_area'] / 100)
        self.pavement_data.infiltration_capacity = params['pavement']['infiltration_capacity']
        self.leakage_rate = params['groundwater']['leakage_rate'] / 100
        self.time_step = params['general']['time_step']

    def solve(self, forcing: pd.Series) -> None:
        """
        Args:
            forcing (pd.DataFrame): Climate forcing data with columns:
                precipitation: Precipitation [mm]
                potential_evaporation: Potential evaporation [mm]
                irrigation: Irrigation on paved area [mm] (default: 0)
            previous_state (pd.DataFrame): State variables from the previous time step with columns:
                Pavement:
                    previous_storage: Initial storage at current time step (t) [L]
            flows (UrbanWaterFlowsData): Current state variables with columns:
                Rain tank:
                    raintank_runoff: Effective imprevious surface runoff from raintank to pavement [L]
        Data:
            storage: Final interception storage level (t+1) [mm]
        Flows:
            inflow: Effective impervious surface runoff inflow [mm/m^2]
            evaporation: Evaporation from interception storage on pavement area [mm]
            infiltration: Infiltration to groundwater (if current storage = max storage) [mm]
            effective_runoff: Effective impervious surface runoff [mm]
            non_effective_runoff: Non-effective runoff [mm]
        """
        data = self.pavement_data
        precipitation = forcing['precipitation']
        potential_evaporation = forcing['potential_evaporation']
        irrigation = forcing.get('pavement_irrigation', 0)

        if data.area == 0:
            return

        irrigation_leakage = irrigation * self.leakage_rate / (1 - self.leakage_rate)
        raintank_inflow = data.flows.get_flow('from_raintank') / data.area
        inflow = precipitation + irrigation + raintank_inflow / data.area

        storage = min(data.storage.capacity, max(0.0, data.storage.previous + inflow))
        evaporation = min(potential_evaporation, storage)

        data.storage.amount = storage - evaporation
        infiltration = max(0.0, min(data.infiltration_capacity * self.time_step,
                                    inflow - data.storage.capacity + data.storage.previous))

        excess_water = inflow - evaporation - infiltration - data.storage.change
        effective_runoff = data.effective_outflow * max(0.0, excess_water)
        non_effective_runoff = max(0.0, excess_water - effective_runoff)


        # Update flows using setters
        data.flows.set_flow('precipitation', precipitation * data.area)
        data.flows.set_flow('irrigation', irrigation * data.area)
        data.flows.set_flow('evaporation', evaporation * data.area)
        data.flows.set_flow('to_stormwater', effective_runoff * data.area)
        data.flows.set_flow('to_pervious', non_effective_runoff * data.area)
        data.flows.set_flow('to_groundwater_infiltration', infiltration * data.area)
        data.flows.set_flow('to_groundwater_leakage', irrigation_leakage * data.area)
