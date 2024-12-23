from typing import Dict, Any, Tuple
import pandas as pd
from duwcm.data_structures import SewerageData
from duwcm.flow_manager import FlowProcess

# Constants
TO_METERS = 0.001

class SewerageClass:
    """
    Simulates cluster sewerage storage dynamics.

    Inflows: Stormwater, reuse, upstream and infiltration
    Outflows: Sewer
    """
    def __init__(self, params: Dict[str, Dict[str, Any]], sewerage_data: SewerageData):
        """
        Args:
            params (Dict[str, float]): System parameters
                area: sewerage area [m²]
                capacity: sewerage storage capacity [m³]
                previous: sewerage initial storage [m³]
        """
        self.sewerage_data = sewerage_data
        self.sewerage_data.area = params['sewerage']['area']

        self.sewerage_data.flows.set_areas(self.sewerage_data.area)
        self.sewerage_data.flows.set_capacity(FlowProcess.SEWERAGE, params['sewerage']['max_pipe_flow'], 'm3')
        self.sewerage_data.storage.set_area(self.sewerage_data.area)
        self.sewerage_data.storage.set_capacity(params['sewerage']['capacity'], 'L')
        self.sewerage_data.storage.set_previous(params['sewerage']['initial_storage'], 'L')

    def solve(self, forcing: pd.Series) -> None:
        """
        Calculate the states and fluxes on sewerage storage during current time step.

        Args:
            forcing (pd.DataFrame): Climate forcing data with columns:

        Updates sewerage_data with:
            storage: Sewerage storage at the end of the time step [m³]
        Updates flows with:
            from_reuse: Outflow from onsite sewerage storage [m³]
            from_groundwater: Infiltration from groundwater [m³]
            from_stormwater: Inflow of stormwater [m³]
            to_downstream: sewerage sewer discharge [m³]
        """
        data = self.sewerage_data
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