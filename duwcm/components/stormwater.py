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
                is_open: is the stormwater storage open for precipitation and evaporation
                area: Area of stormwater storage [m²]
                capacity: Stormwater storage capacity [m³]
                pervious: Stormwater initial storage [m³]
                first_flush: Predefined first flush of stormwater storage [m³]
                wastewater_runoff_ratio: Percentage of runoff that becomes inflow to wastewater system [%]
        """
        self.stormwater_data = stormwater_data
        self.stormwater_data.area = params['stormwater']['area']
        self.stormwater_data.is_open = params['stormwater']['is_open']

        self.stormwater_data.flows.set_areas(self.stormwater_data.area)
        self.stormwater_data.storage.set_area(self.stormwater_data.area)
        self.stormwater_data.storage.set_capacity(params['stormwater']['capacity'], 'mm')
        self.stormwater_data.storage.set_previous(params['stormwater']['initial_storage'], 'mm')

        self.stormwater_data.first_flush = params['stormwater']['first_flush'] * 0.001
        self.wastewater_runoff_ratio = params['stormwater']['wastewater_runoff_per'] / 100

    def solve(self, forcing: pd.Series) -> None:
        """
        Args:
            forcing (pd.DataFrame): Climate forcing data with columns:
                precipitation: Precipitation of the time step [mm]
                potential_evaporation: Potential evaporation of the time step [mm]

        Updates stormwater_data with:
            storage: Storage volume at the end of the time step [m³]
        Updates flows with:
            precipitation: Direct precipitation [m³]
            evaporation: Evaporation [m³]
            from_raintank: Outflow from raintank [m³]
            from_pavement: Runoff from pavement [m³]
            from_pervious: Overflow from pervious [m³]
            from_upstream: Stormwater from upstream cells [m³]
            to_wastewater: Combined sewer inflow [m³]
            to_downstream: Stormwater discharge [m³]
        """
        data = self.stormwater_data

        # Calculate total runoff
        raintank_runoff = data.flows.get_flow('from_raintank', 'm3')
        pavement_runoff = data.flows.get_flow('from_pavement', 'm3')
        pervious_runoff = data.flows.get_flow('from_pervious', 'm3')
        upstream_inflow = data.flows.get_flow('from_upstream', 'm3')

        total_runoff = raintank_runoff + pavement_runoff + pervious_runoff + upstream_inflow
        combined_sewer_inflow = self.wastewater_runoff_ratio * total_runoff
        runoff = total_runoff - combined_sewer_inflow

        # Handle zero capacity case
        if data.storage.get_capacity('m3') == 0:
            runoff += data.flows.set_flow('to_wastewater', combined_sewer_inflow, 'm3')
            data.flows.set_flow('to_downstream', runoff, 'm3')
            data.flows.set_flow('precipitation', 0)
            data.flows.set_flow('evaporation', 0)
            return

        # Calculate first flush and inflow
        first_flush = min(runoff, data.first_flush)
        inflow = runoff - first_flush
        if data.is_open:
            data.flows.set_flow('precipitation', forcing['precipitation'], 'mm')
            inflow += data.flows.get_flow('precipitation', 'm3')

        # Calculate storage and evaporation
        current_storage = min(data.storage.get_capacity('m3'), max(0.0, data.storage.get_previous('m3') + inflow))
        data.flows.set_flow('evaporation', 0)
        if data.is_open:
            data.flows.set_flow('evaporation', forcing['potential_evaporation'], 'mm')
            data.flows.set_flow('evaporation', min(data.flows.get_flow('evaporation', 'm3'), current_storage), 'm3')

        # Calculate final storage and overflow
        data.storage.set_amount(current_storage - data.flows.get_flow('evaporation', 'm3'), 'm3')
        overflow = max(0.0, inflow - data.storage.get_change('m3'))
        runoff_sewer = first_flush + overflow

        # Update flows
        runoff_sewer += data.flows.set_flow('to_wastewater', combined_sewer_inflow, 'm3')
        data.flows.set_flow('to_downstream', runoff_sewer, 'm3')