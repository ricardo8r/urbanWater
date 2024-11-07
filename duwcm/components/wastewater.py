from typing import Dict, Any, Tuple
import pandas as pd
from duwcm.data_structures import WastewaterData

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
                groundwater_area: Area of groundwater storage [m^2]
                cluster_storage_capacity: Wastewater storage capacity [L]
        """
        self.wastewater_data = wastewater_data
        self.wastewater_data.area = params['wastewater']['area']
        self.wastewater_data.storage.capacity = params['wastewater']['capacity']
        self.groundwater_area = params['groundwater']['area']

    def solve(self, forcing: pd.Series) -> None:
        """
        Calculate the states and fluxes on wastewater storage during current time step.

        Args:
            forcing (pd.DataFrame): Climate forcing data with columns:

        Updates wastewater_data with:
            storage: Wastewater storage at the end of the time step [L]
        Updates flows with:
            from_reuse: Outflow from onsite wastewater storage [L]
            from_groundwater: Infiltration from groundwater [L]
            from_stormwater: Inflow of stormwater [L]
            to_downstream: Wastewater sewer discharge [L]
        """
        # Calculate total inflow
        total_inflow = (self.wastewater_data.flows.get_flow('from_reuse') +
                      self.wastewater_data.flows.get_flow('from_groundwater') +
                      self.wastewater_data.flows.get_flow('from_stormwater') +
                      self.wastewater_data.flows.get_flow('from_upstream'))

        if self.wastewater_data.storage.capacity == 0:
            self.wastewater_data.flows.set_flow('to_downstream', total_inflow)
            return

        # Calculate storage and discharge
        self.wastewater_data.storage.amount = min(self.wastewater_data.storage.capacity,
                                                  self.wastewater_data.storage.previous + total_inflow)
        discharge = max(0.0, total_inflow - self.wastewater_data.storage.change)

        # Update storage
        water_balance = total_inflow - discharge - self.wastewater_data.storage.change

        # Update flows
        self.wastewater_data.flows.set_flow('to_downstream', discharge)