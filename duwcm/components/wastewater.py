from typing import Dict, Any, Tuple
import pandas as pd
from duwcm.data_structures import WastewaterData

# Constants
TO_METERS = 0.001

class WastewaterClass:
    """
    Simulates cluster wastewater storage dynamics.

    Inflows: Stormwater, reuse, upstream and infiltration
    Outflows: Sewer
    """
    def __init__(self, params: Dict[str, Dict[str, Any]], wastewater_data: WastewaterData):
        """
        Args:
            params (Dict[str, float]): System parameters
                area: Wastewater area [m²]
                capacity: Wastewater storage capacity [m³]
                previous: Wastewater initial storage [m³]
        """
        self.wastewater_data = wastewater_data
        self.wastewater_data.area = params['wastewater']['area']

        self.wastewater_data.flows.set_areas(self.wastewater_data.area)
        self.wastewater_data.storage.set_area(self.wastewater_data.area)
        self.wastewater_data.storage.set_capacity(params['wastewater']['capacity'], 'L')
        self.wastewater_data.storage.set_previous(params['wastewater']['initial_storage'], 'L')

    def solve(self, forcing: pd.Series) -> None:
        """
        Calculate the states and fluxes on wastewater storage during current time step.

        Args:
            forcing (pd.DataFrame): Climate forcing data with columns:

        Updates wastewater_data with:
            storage: Wastewater storage at the end of the time step [m³]
        Updates flows with:
            from_reuse: Outflow from onsite wastewater storage [m³]
            from_groundwater: Infiltration from groundwater [m³]
            from_stormwater: Inflow of stormwater [m³]
            to_downstream: Wastewater sewer discharge [m³]
        """
        data = self.wastewater_data
        total_inflow = (data.flows.get_flow('from_demand', 'm3') +
                        data.flows.get_flow('from_groundwater', 'm3') +
                        data.flows.get_flow('from_stormwater', 'm3') +
                        data.flows.get_flow('from_upstream', 'm3'))

        if data.storage.get_capacity('m3') == 0:
            data.flows.set_flow('to_downstream', total_inflow, 'm3')
            return

        # Calculate storage and discharge
        data.storage.set_amount(min(data.storage.get_capacity('m3'),
                                    data.storage.get_previous('m3') + total_inflow), 'm3')
        discharge = max(0.0, total_inflow - data.storage.get_change('m3'))

        # Update flows
        data.flows.set_flow('to_downstream', discharge, 'm3')