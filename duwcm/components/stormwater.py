from typing import Dict, Any, Tuple
import pandas as pd
from duwcm.data_structures import StormwaterData

class StormwaterClass:
    """
    Simulates storm water storage dynamics.

    Inflows: Precipitation, raintank runoff, pavement runoff, pervious runoff, upstream inflow
    Outflows: Flush, overflow, evaporation, wastewater inflow
    """
    def __init__(self, params: Dict[str, Dict[str, Any]], stormwater_data: StormwaterData):
        """
        Args:
            params (Dict[str, Dict[str, Any]]): Stormwater storage parameters
                pavement_area: Area of pavement [m^2]
                pervious_area: Area of pervious surface [m^2]
                is_open: is the stormwater storage open for precipitation and evaporation
                area: Area of stormwater storage [m^2]
                capacity: Stormwater storage capacity [L]
                first_flush: Predefined first flush of stormwater storage [L]
                wastewater_runoff_ratio: Percentage of runoff that becomes inflow to wastewater system [%]
        """
        self.stormwater_data = stormwater_data
        self.stormwater_data.area = params['stormwater']['area']
        self.stormwater_data.is_open = params['stormwater']['is_open']
        self.stormwater_data.storage.capacity = params['stormwater']['capacity']
        self.stormwater_data.first_flush = params['stormwater']['first_flush']
        self.wastewater_runoff_ratio = params['stormwater']['wastewater_runoff_per'] / 100

        self.pavement_area = params['pavement']['area']
        self.pervious_area = params['pervious']['area']

    def solve(self, forcing: pd.Series) -> None:
        """
        Args:
            forcing (pd.DataFrame): Climate forcing data with columns:
                precipitation: Precipitation of the time step [mm]
                potential_evaporation: Potential evaporation of the time step [mm]

        Updates stormwater_data with:
            storage: Storage volume at the end of the time step [L]
        Updates flows with:
            precipitation: Direct precipitation if storage is open [L]
            from_raintank: Outflow from raintank [L]
            from_pavement: Runoff from pavement [L]
            from_pervious: Overflow from pervious [L]
            from_upstream: Stormwater from upstream cells [L]
            to_wastewater: Combined sewer inflow [L]
            to_downstream: Stormwater discharge [L]
            evaporation: Evaporation if storage is open [L]
        """
        data = self.stormwater_data
        precipitation = forcing.get('precipitation', 0.0)
        potential_evaporation = forcing.get('potential_evaporation', 0.0)

        # Calculate total runoff
        raintank_runoff = data.flows.get_flow('from_raintank')
        pavement_runoff = data.flows.get_flow('from_pavement')
        pervious_runoff = data.flows.get_flow('from_pervious')
        upstream_inflow = data.flows.get_flow('from_upstream')

        total_runoff = raintank_runoff + pavement_runoff + pervious_runoff + upstream_inflow

        # Handle zero capacity case
        if data.storage.capacity == 0:
            combined_sewer_inflow = self.wastewater_runoff_ratio * total_runoff
            runoff = total_runoff - combined_sewer_inflow

            # Update flows for zero capacity case
            data.flows.set_flow('to_wastewater', combined_sewer_inflow)
            data.flows.set_flow('to_downstream', runoff)
            return

        # Calculate runoff distribution
        combined_sewer_inflow = self.wastewater_runoff_ratio * total_runoff
        runoff = total_runoff - combined_sewer_inflow

        # Calculate first flush and inflow
        first_flush = min(runoff, data.first_flush)
        inflow = runoff - first_flush
        if data.is_open:
            inflow += precipitation * data.area

        # Calculate storage and evaporation
        current_storage = min(data.storage.capacity, max(0.0, data.storage.previous + inflow))
        evaporation = 0.0
        if data.is_open:
            evaporation = min(potential_evaporation * data.area, current_storage)

        # Calculate final storage and overflow
        data.storage.amount = current_storage - evaporation
        overflow = max(0.0, inflow - data.storage.change)
        runoff_sewer = first_flush + overflow

        # Update flows
        if data.is_open:
            data.flows.set_flow('precipitation', precipitation * data.area)
            data.flows.set_flow('evaporation', evaporation)
        data.flows.set_flow('to_wastewater', combined_sewer_inflow)
        data.flows.set_flow('to_downstream', runoff_sewer)