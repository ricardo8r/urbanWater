from typing import Dict, Any, Tuple
import pandas as pd
from duwcm.data_structures import WaterBodyData

class WaterBodyClass:
    """
    Simulates water balance for an urban waterbody or water feature.

    Inflows: Precipitation, pervious runoff, stormwater diversion, groundwater interaction
    Outflows: Evaporation, infiltration, overflow
    """
    def __init__(self, params: Dict[str, Dict[str, Any]], waterbody_data: WaterBodyData):
        """
        Args:
            params (Dict[str, Dict[str, Any]]): waterbody parameters
                area: Surface area of waterbody [m²]
                capacity: Maximum waterbody volume [m³]
                initial_storage: Initial water volume [m³]
                max_depth: Maximum depth [m]
                infiltration_rate: Rate of infiltration to groundwater [mm/day]
                stormwater_inflow: Percentage of stormwater diverted to waterbody [%]
                seepage_coefficient: Coefficient for groundwater interaction [1/day]
        """
        self.waterbody_data = waterbody_data
        self.waterbody_data.area = params['waterbody']['area']

        self.waterbody_data.flows.set_areas(self.waterbody_data.area)
        self.waterbody_data.storage.set_area(self.waterbody_data.area)
        self.waterbody_data.storage.set_capacity(params['waterbody']['capacity'], 'm3')
        self.waterbody_data.storage.set_previous(params['waterbody']['initial_storage'], 'm3')

        self.waterbody_data.max_depth = params['waterbody']['max_depth']
        self.waterbody_data.infiltration_rate = params['waterbody']['infiltration_rate'] / 1000  # mm/day to m/day
        self.waterbody_data.stormwater_inflow = params['waterbody']['stormwater_inflow'] / 100
        self.waterbody_data.seepage_coefficient = params['waterbody'].get('seepage_coefficient', 0.01)

        self.time_step = params['general']['time_step']

    def solve(self, forcing: pd.Series) -> None:
        """
        Args:
            forcing (pd.Series): Climate forcing data with columns:
                precipitation: Precipitation of the time step [mm]
                potential_evaporation: Potential evaporation of the time step [mm]
                open_water_level: Open water level for the time step [m-SL]

        Updates waterbody_data with:
            storage: waterbody volume at the end of the time step [m³]
        Updates flows with:
            precipitation: Direct precipitation [m³]
            evaporation: Evaporation [m³]
            from_stormwater: Inflow from stormwater diversion [m³]
            from_pervious: Inflow from pervious areas [m³]
            from_groundwater: Seepage from groundwater [m³]
            to_groundwater: Infiltration to groundwater [m³]
            to_stormwater: Overflow discharge [m³]
        """
        data = self.waterbody_data

        if data.area == 0:
            return

        # Direct precipitation input
        data.flows.set_flow('precipitation', forcing['precipitation'], 'mm')

        # Calculate current storage and depth
        current_storage = data.storage.get_previous('m3')
        if data.area > 0:
            current_depth = current_storage / data.area
        else:
            current_depth = 0

        # Calculate stormwater diversion inflow
        stormwater_diversion = data.flows.get_flow('from_stormwater', 'm3')

        # Calculate pervious inflow
        pervious_inflow = data.flows.get_flow('from_pervious', 'm3')

        # Calculate groundwater interaction (positive = inflow, negative = outflow)
        groundwater_level = data.groundwater_level.get_previous('m')
        groundwater_head_difference = groundwater_level - current_depth

        groundwater_interaction = (groundwater_head_difference *
                                  data.seepage_coefficient *
                                  data.area * 
                                  self.time_step)

        if groundwater_interaction > 0:  # Inflow from groundwater
            data.flows.set_flow('from_groundwater', groundwater_interaction, 'm3')
            data.flows.set_flow('to_groundwater', 0, 'm3')
        else:  # Outflow to groundwater
            data.flows.set_flow('from_groundwater', 0, 'm3')
            data.flows.set_flow('to_groundwater', -groundwater_interaction, 'm3')

        # Calculate infiltration to groundwater (separate from head-based interaction)
        infiltration = min(current_storage,
                          data.infiltration_rate * data.area * self.time_step)

        data.flows.set_flow('to_groundwater',
                           data.flows.get_flow('to_groundwater', 'm3') + infiltration, 'm3')

        # Calculate evaporation (higher for open water)
        # Use forcing's open water evaporation if available, otherwise use potential evaporation
        if 'open_water_evaporation' in forcing:
            evaporation_rate = forcing['open_water_evaporation']
        else:
            # Open water typically has 1.05-1.3x higher evaporation than potential
            evaporation_rate = forcing['potential_evaporation'] * 1.2

        data.flows.set_flow('evaporation', evaporation_rate, 'mm')
        evaporation_volume = min(current_storage,
                                data.flows.get_flow('evaporation', 'm3'))
        data.flows.set_flow('evaporation', evaporation_volume, 'm3')

        # Calculate total inflows and outflows
        total_inflow = (data.flows.get_flow('precipitation', 'm3') +
                       data.flows.get_flow('from_stormwater', 'm3') +
                       data.flows.get_flow('from_pervious', 'm3') +
                       data.flows.get_flow('from_groundwater', 'm3'))

        total_outflow = (data.flows.get_flow('evaporation', 'm3') +
                        data.flows.get_flow('to_groundwater', 'm3'))

        # Update storage
        new_storage = max(0, current_storage + total_inflow - total_outflow)

        # Check for overflow
        capacity = data.storage.get_capacity('m3')
        if new_storage > capacity:
            overflow = new_storage - capacity
            new_storage = capacity
            data.flows.set_flow('to_stormwater', overflow, 'm3')
        else:
            data.flows.set_flow('to_stormwater', 0, 'm3')

        data.storage.set_amount(new_storage, 'm3')
