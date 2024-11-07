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
        precipitation = forcing.get('precipitation', 0.0)
        potential_evaporation = forcing.get('potential_evaporation', 0.0)

        # Calculate total runoff
        raintank_runoff = self.stormwater_data.flows.get_flow('from_raintank')
        pavement_runoff = self.stormwater_data.flows.get_flow('from_pavement')
        pervious_runoff = self.stormwater_data.flows.get_flow('from_pervious')
        upstream_inflow = self.stormwater_data.flows.get_flow('from_upstream')

        total_runoff = raintank_runoff + pavement_runoff + pervious_runoff + upstream_inflow

        # Handle zero capacity case
        if self.stormwater_data.storage.capacity == 0:
            combined_sewer_inflow = self.wastewater_runoff_ratio * total_runoff
            runoff = total_runoff - combined_sewer_inflow

            # Update flows for zero capacity case
            self.stormwater_data.flows.set_flow('to_wastewater', combined_sewer_inflow)
            self.stormwater_data.flows.set_flow('to_downstream', runoff)
            return

        # Calculate runoff distribution
        combined_sewer_inflow = self.wastewater_runoff_ratio * total_runoff
        runoff = total_runoff - combined_sewer_inflow

        # Calculate first flush and inflow
        first_flush = min(runoff, self.stormwater_data.first_flush)
        inflow = runoff - first_flush
        if self.stormwater_data.is_open:
            inflow += precipitation * self.stormwater_data.area

        # Calculate storage and evaporation
        current_storage = min(self.stormwater_data.storage.capacity,
                            max(0.0, self.stormwater_data.storage.previous + inflow))
        evaporation = 0.0
        if self.stormwater_data.is_open:
            evaporation = min(potential_evaporation * self.stormwater_data.area, current_storage)

        # Calculate final storage and overflow
        final_storage = current_storage - evaporation
        overflow = max(0.0, self.stormwater_data.storage.previous + inflow - final_storage)
        runoff_sewer = first_flush + overflow

        water_balance = (inflow - evaporation - overflow -
                         (final_storage - self.stormwater_data.storage.previous))

        # Update storage
        self.stormwater_data.storage.amount = final_storage

        # Update flows
        if self.stormwater_data.is_open:
            self.stormwater_data.flows.set_flow('precipitation', precipitation * self.stormwater_data.area)
            self.stormwater_data.flows.set_flow('evaporation', evaporation)
        self.stormwater_data.flows.set_flow('to_wastewater', combined_sewer_inflow)
        self.stormwater_data.flows.set_flow('to_downstream', runoff_sewer)