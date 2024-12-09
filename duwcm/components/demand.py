from typing import Dict, Any, Tuple
from dataclasses import dataclass
import pandas as pd

from duwcm.data_structures import DemandData
from duwcm.flow_manager import WaterQuality, WaterUse

@dataclass
class WaterSource:
    """Water source with quality level and priority settings"""
    name: str
    quality: WaterQuality
    local: bool
    available_amount: float = 0.0

class DemandClass:
    """
    Simulates the supply, demand, use, and deficit of water resources.
    Handles water quality levels and fit-for-purpose allocation.
    """
    def __init__(self, params: Dict[str, Dict[str, Any]], demand_settings: pd.Series,
                 reuse_settings: pd.DataFrame, demand_data: DemandData):
        """
        Args:
            params: System parameters including areas and capacities
            demand_settings: Water demand settings for different uses
            reuse_settings: Water reuse configuration and priorities
            demand_data: Data structure for tracking flows and storage
        """
        self.demand_data = demand_data

        # Initialize wastewater storage parameters
        self.demand_data.area = params['reuse']['area'] * params['general']['number_houses']
        self.demand_data.flows.set_areas(self.demand_data.area)
        self.demand_data.ww_storage.set_capacity(params['reuse']['capacity'] * params['general']['number_houses'])

        # Initialize water demand patterns
        self.indoor_water_use = params['general']['indoor_water_use']
        self.kitchen_demand = demand_settings.kitchen * self.indoor_water_use / 100
        self.bathroom_demand = demand_settings.bathroom * self.indoor_water_use / 100
        self.toilet_demand = demand_settings.toilet * self.indoor_water_use / 100
        self.laundry_demand = demand_settings.laundry * self.indoor_water_use / 100

        # Initialize reuse settings
        self.setreuse = {
            'KforSSG': reuse_settings.kitchen_to_graywater / 100,
            'BforSSG': reuse_settings.bathroom_to_graywater / 100,
            'LforSSG': reuse_settings.laundry_to_graywater / 100,
            'RTforK': reuse_settings.raintank_to_kitchen / 100,
            'RTforB': reuse_settings.raintank_to_bathroom / 100,
            'RTforL': reuse_settings.raintank_to_laundry / 100,
            'RTforT': reuse_settings.raintank_to_toilet / 100,
            'RTforIR': reuse_settings.raintank_to_irrigation / 100,
            'WWSforT': reuse_settings.wastewater_to_toilet / 100,
            'WWSforIR': reuse_settings.wastewater_to_irrigation / 100
        }

        # Define water sources and their qualities
        self.sources = {
            'SSG': WaterSource('SSG', WaterQuality.GREYWATER, True),
            'WWS': WaterSource('WWS', WaterQuality.TREATED, True),
            'RT': WaterSource('RT', WaterQuality.RAINWATER, True),
            'cWWS': WaterSource('cWWS', WaterQuality.TREATED, False),
            'SWS': WaterSource('SWS', WaterQuality.STORMWATER, False),
            'PO': WaterSource('PO', WaterQuality.POTABLE, False)
        }

        # Define priority tables according to Table 4-8
        self.priority_table = {
            'K': ['RT', 'SWS', 'PO'],
            'S': ['RT', 'SWS', 'PO'],
            'L': ['RT', 'SWS', 'PO'],
            'T': ['SSG', 'WWS', 'RT', 'cWWS', 'SWS', 'PO'],
            'IR': ['SSG', 'WWS', 'RT', 'cWWS', 'SWS', 'PO'],
            'PIR': ['cWWS', 'SWS', 'PO']
        }

        # Calculate initial supply capacities
        self.ssg_supply = (self.setreuse['KforSSG'] * self.kitchen_demand +
                          self.setreuse['BforSSG'] * self.bathroom_demand +
                          self.setreuse['LforSSG'] * self.laundry_demand)

        self.raintank_supply = (self.setreuse['RTforK'] * self.kitchen_demand +
                               self.setreuse['RTforB'] * self.bathroom_demand +
                               self.setreuse['RTforL'] * self.laundry_demand)

    def solve(self, forcing: pd.Series) -> None:
        """
        Args:
           forcing (pd.DataFrame): Climate forcing data with columns:
                roof_irrigation: Irrigation demand on roof surface [mm]
                pavement_irrigation: Irrigation demand on pavement surface [mm]
                pervious_irrigation: Irrigation demand on pervious surface [mm]

        Returns:
            Dict[str, float]: Water balance components for the current time step:
                sgs_results: Subsurface graywater balance
                wws_results: Wastewater storage balance
                rt_results: Rain tank balance
                imported_water: Required imported water [L]  
        """
        data = self.demand_data

        # Calculate total irrigation demand upfront
        roof_irrigation = data.flows.get_flow('to_roof', 'L')
        pavement_irrigation = data.flows.get_flow('to_pavement', 'L')
        pervious_irrigation = data.flows.get_flow('to_pervious', 'L')
        total_irrigation = roof_irrigation + pavement_irrigation + pervious_irrigation

        # 1. Process Raintank allocations first
        rt_available = data.rt_storage.get_amount('L')
        # Kitchen allocation
        rt_to_kitchen = min(self.kitchen_demand * self.setreuse['RTforK'], rt_available)
        data.internal_flows.rt_to_kitchen.set_amount(rt_to_kitchen, 'L')
        rt_available -= rt_to_kitchen

        # Bathroom allocation
        rt_to_shower = min(self.bathroom_demand * self.setreuse['RTforB'], rt_available)
        data.internal_flows.rt_to_shower.set_amount(rt_to_shower, 'L')
        rt_available -= rt_to_shower

        # Laundry allocation
        rt_to_laundry = min(self.laundry_demand * self.setreuse['RTforL'], rt_available)
        data.internal_flows.rt_to_laundry.set_amount(rt_to_laundry, 'L')
        rt_available -= rt_to_laundry

        # Toilet allocation
        rt_to_toilet = min(self.toilet_demand * self.setreuse['RTforT'], rt_available)
        data.internal_flows.rt_to_toilet.set_amount(rt_to_toilet, 'L')
        rt_available -= rt_to_toilet

        # Irrigation allocation
        rt_to_irrigation = min(total_irrigation * self.setreuse['RTforIR'], rt_available)
        data.internal_flows.rt_to_irrigation.set_amount(rt_to_irrigation, 'L')
        rt_available -= rt_to_irrigation

        # Update raintank storage
        data.rt_storage.set_amount(rt_available, 'L')

        # Update total raintank to demand flow
        data.flows.set_flow('from_raintank',
            data.internal_flows.rt_to_kitchen.get_amount('L') +
            data.internal_flows.rt_to_shower.get_amount('L') +
            data.internal_flows.rt_to_laundry.get_amount('L') +
            data.internal_flows.rt_to_toilet.get_amount('L') +
            data.internal_flows.rt_to_irrigation.get_amount('L'),
            'L')

        # 2. Calculate greywater generation from total indoor use
        kitchen_to_grey = self.kitchen_demand * self.setreuse['KforSSG']
        shower_to_grey = self.bathroom_demand * self.setreuse['BforSSG']
        laundry_to_grey = self.laundry_demand * self.setreuse['LforSSG']

        data.internal_flows.kitchen_to_greywater.set_amount(kitchen_to_grey, 'L')
        data.internal_flows.shower_to_greywater.set_amount(shower_to_grey, 'L')
        data.internal_flows.laundry_to_greywater.set_amount(laundry_to_grey, 'L')

        total_greywater = kitchen_to_grey + shower_to_grey + laundry_to_grey
        grey_to_irrigation = min(total_irrigation, total_greywater)
        data.internal_flows.greywater_to_irrigation.set_amount(grey_to_irrigation, 'L')

        greywater_to_wws = total_greywater - grey_to_irrigation
        data.internal_flows.greywater_to_wastewater.set_amount(greywater_to_wws, 'L')

        # 3. Process wastewater treatment (WWS)
        total_wastewater = (self.kitchen_demand + self.bathroom_demand +
                            self.laundry_demand + self.toilet_demand)
        total_treated = total_wastewater - (kitchen_to_grey + shower_to_grey + laundry_to_grey)
        data.ww_storage.set_amount(min(data.ww_storage.get_capacity('L'),
                                       data.ww_storage.get_previous('L') + total_treated), 'L')

        remaining_toilet = (self.toilet_demand -
                            data.internal_flows.rt_to_toilet.get_amount('L'))
        remaining_irrigation = (total_irrigation -
                                data.internal_flows.rt_to_irrigation.get_amount('L') -
                                grey_to_irrigation)

        if data.ww_storage.get_capacity('L') > 0:
            wws_available = data.ww_storage.get_amount('L')

            # Allocate to toilet first
            wws_toilet_use = min(remaining_toilet * self.setreuse['WWSforT'], wws_available)
            wws_available -= wws_toilet_use

            # Then irrigation if any remaining
            wws_irrigation_use = min(remaining_irrigation * self.setreuse['WWSforIR'], wws_available)

            # Update storage and flows
            data.ww_storage.set_amount(wws_available - wws_irrigation_use, 'L')
            data.internal_flows.wws_to_toilet.set_amount(wws_toilet_use, 'L')
            data.internal_flows.wws_to_irrigation.set_amount(wws_irrigation_use, 'L')

        # 4. Calculate remaining demands that need potable water
        remaining_indoor = {
           'kitchen': self.kitchen_demand - data.internal_flows.rt_to_kitchen.get_amount('L'),
           'bathroom': self.bathroom_demand - data.internal_flows.rt_to_shower.get_amount('L'),
           'laundry': self.laundry_demand - data.internal_flows.rt_to_laundry.get_amount('L')
        }

        potable_indoor = sum(remaining_indoor.values())

        data.internal_flows.po_to_kitchen.set_amount(remaining_indoor['kitchen'], 'L')
        data.internal_flows.po_to_shower.set_amount(remaining_indoor['bathroom'], 'L')
        data.internal_flows.po_to_laundry.set_amount(remaining_indoor['laundry'], 'L')

        potable_toilet = (self.toilet_demand -
                         (data.internal_flows.rt_to_toilet.get_amount('L') +
                          data.internal_flows.wws_to_toilet.get_amount('L')))

        potable_irrigation = (total_irrigation -
                            (data.internal_flows.rt_to_irrigation.get_amount('L') +
                             data.internal_flows.greywater_to_irrigation.get_amount('L') +
                             data.internal_flows.wws_to_irrigation.get_amount('L')))

        data.internal_flows.po_to_toilet.set_amount(max(0, potable_toilet), 'L')
        data.internal_flows.po_to_irrigation.set_amount(max(0, potable_irrigation), 'L')

        # Calculate leakage and total imported water
        total_potable = (potable_indoor +
                        max(0, potable_toilet) +
                        max(0, potable_irrigation))
        leakage = data.flows.get_flow('to_groundwater', 'L')
        data.flows.set_flow('imported_water', total_potable + leakage, 'L')