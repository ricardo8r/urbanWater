from typing import Dict, Any, Tuple
from dataclasses import dataclass
import pandas as pd
from duwcm.data_structures import DemandData

@dataclass
class ReuseConfig:
    """Configuration for water reuse settings"""
    kitchen_to_gray: float
    bathroom_to_gray: float
    laundry_to_gray: float
    rt_to_kitchen: float
    rt_to_bathroom: float
    rt_to_laundry: float
    rt_to_toilet: float
    rt_to_irrigation: float
    wws_to_toilet: float
    wws_to_irrigation: float

    @classmethod
    def from_settings(cls, settings: pd.Series) -> 'ReuseConfig':
        return cls(
            kitchen_to_gray=settings.kitchen_to_graywater / 100,
            bathroom_to_gray=settings.bathroom_to_graywater / 100,
            laundry_to_gray=settings.laundry_to_graywater / 100,
            rt_to_kitchen=settings.raintank_to_kitchen / 100,
            rt_to_bathroom=settings.raintank_to_bathroom / 100,
            rt_to_laundry=settings.raintank_to_laundry / 100,
            rt_to_toilet=settings.raintank_to_toilet / 100,
            rt_to_irrigation=settings.raintank_to_irrigation / 100,
            wws_to_toilet=settings.wastewater_to_toilet / 100,
            wws_to_irrigation=settings.wastewater_to_irrigation / 100
        )

class DemandClass:
    """Simulates water supply, demand, use, and deficit with quality-based allocation."""

    def __init__(self, params: Dict[str, Dict[str, Any]], demand_settings: pd.Series,
                 reuse_settings: pd.DataFrame, demand_data: DemandData):
        """Initialize demand management system."""
        self.demand_data = demand_data
        self.reuse_config = ReuseConfig.from_settings(reuse_settings)

        # Initialize storage and flows
        self.demand_data.area = params['reuse']['area'] * params['general']['number_houses']
        self.demand_data.flows.set_areas(self.demand_data.area)
        self.demand_data.ww_storage.set_capacity(
            params['reuse']['capacity'] * params['general']['number_houses']
        )

        # Initialize demands
        self.indoor_water_use = params['general']['indoor_water_use']
        self.demands = {
            'kitchen': demand_settings.kitchen * self.indoor_water_use / 100,
            'bathroom': demand_settings.bathroom * self.indoor_water_use / 100,
            'toilet': demand_settings.toilet * self.indoor_water_use / 100,
            'laundry': demand_settings.laundry * self.indoor_water_use / 100
        }

    def _allocate_source(self, demand: float, available: float, usage_factor: float) -> Tuple[float, float]:
        """Allocate water from a source based on demand and availability."""
        allocation = min(demand * usage_factor, available)
        return allocation, available - allocation

    def _process_raintank_allocations(self) -> None:
        """Process all raintank allocations."""
        data = self.demand_data
        if data.rt_storage.get_capacity('L') > 0:
            available = data.rt_storage.get_amount('L')

            # Allocate to each use type
            for use, rt_flow in [
                ('kitchen', 'rt_to_kitchen'),
                ('bathroom', 'rt_to_bathroom'),
                ('laundry', 'rt_to_laundry'),
                ('toilet', 'rt_to_toilet')
            ]:
                usage_factor = getattr(self.reuse_config, f'rt_to_{use}')
                allocation, available = self._allocate_source(
                    self.demands[use], available, usage_factor
                )
                getattr(data.internal_flows, rt_flow).set_amount(allocation, 'L')

            # Handle irrigation separately
            total_irrigation = sum(
                data.flows.get_flow(f'to_{surface}', 'L')
                for surface in ['roof', 'pavement', 'pervious']
            )
            allocation, available = self._allocate_source(
                total_irrigation, available, self.reuse_config.rt_to_irrigation
            )
            data.internal_flows.rt_to_irrigation.set_amount(allocation, 'L')
            data.rt_storage.set_amount(available, 'L')

    def _process_graywater_generation(self) -> None:
        """Process graywater generation and allocation."""
        data = self.demand_data

        # Generate graywater from each source
        graywater_flows = []
        for source, gray_factor in [
            ('kitchen', self.reuse_config.kitchen_to_gray),
            ('bathroom', self.reuse_config.bathroom_to_gray),
            ('laundry', self.reuse_config.laundry_to_gray)
        ]:
            flow = self.demands[source] * gray_factor
            flow_name = f"{source}_to_graywater"
            getattr(data.internal_flows, flow_name).set_amount(flow, 'L')
            graywater_flows.append(flow)

        total_graywater = sum(graywater_flows)
        total_irrigation = sum(
            data.flows.get_flow(f'to_{surface}', 'L')
            for surface in ['roof', 'pavement', 'pervious']
        )

        # Allocate graywater
        gray_to_irrigation = min(total_irrigation, total_graywater)
        data.internal_flows.graywater_to_irrigation.set_amount(gray_to_irrigation, 'L')
        data.internal_flows.graywater_to_wastewater.set_amount(
            total_graywater - gray_to_irrigation, 'L'
        )

    def _process_wastewater_treatment(self) -> None:
        """Process wastewater treatment and allocation."""
        data = self.demand_data

        # Calculate total wastewater and treatment
        total_wastewater = sum(self.demands.values())
        graywater_total = sum(
            getattr(data.internal_flows, f"{src}_to_graywater").get_amount('L')
            for src in ['kitchen', 'bathroom', 'laundry']
        )
        total_treated = total_wastewater - graywater_total

        if data.ww_storage.get_capacity('L') > 0:
            # Update storage
            data.ww_storage.set_amount(
                min(data.ww_storage.get_capacity('L'),
                    data.ww_storage.get_previous('L') + total_treated),
                'L'
            )

            available = data.ww_storage.get_amount('L')

            # Allocate to toilet
            remaining_toilet = (self.demands['toilet'] -
                              data.internal_flows.rt_to_toilet.get_amount('L'))
            allocation, available = self._allocate_source(
                remaining_toilet, available, self.reuse_config.wws_to_toilet
            )
            data.internal_flows.wws_to_toilet.set_amount(allocation, 'L')

            # Allocate to irrigation
            total_irrigation = sum(
                data.flows.get_flow(f'to_{surface}', 'L')
                for surface in ['roof', 'pavement', 'pervious']
            )
            remaining_irrigation = (
                total_irrigation -
                data.internal_flows.rt_to_irrigation.get_amount('L') -
                data.internal_flows.graywater_to_irrigation.get_amount('L')
            )
            allocation, available = self._allocate_source(
                remaining_irrigation, available, self.reuse_config.wws_to_irrigation
            )
            data.internal_flows.wws_to_irrigation.set_amount(allocation, 'L')
            data.ww_storage.set_amount(available, 'L')
            overflow = data.flows.set_flow('to_wastewater', total_treated - data.ww_storage.get_amount('L'), 'L')
            if overflow > 0:
                raise ValueError(f"Overflow in domestic sewerage: {overflow}")

        else:
            overflow = data.flows.set_flow('to_wastewater', total_treated, 'L')
            if overflow > 0:
                raise ValueError(f"Overflow in domestic sewerage: {overflow}")

    def _process_potable_demands(self) -> None:
        """Process remaining demands requiring potable water."""
        data = self.demand_data

        # Calculate remaining indoor demands
        for use, rt_flow, po_flow in [
            ('kitchen', 'rt_to_kitchen', 'po_to_kitchen'),
            ('bathroom', 'rt_to_bathroom', 'po_to_bathroom'),
            ('laundry', 'rt_to_laundry', 'po_to_laundry')
        ]:
            remaining = (
                self.demands[use] -
                getattr(data.internal_flows, rt_flow).get_amount('L')
            )
            getattr(data.internal_flows, po_flow).set_amount(remaining, 'L')

        # Calculate remaining toilet demand
        remaining_toilet = (
            self.demands['toilet'] -
            data.internal_flows.rt_to_toilet.get_amount('L') -
            data.internal_flows.wws_to_toilet.get_amount('L')
        )
        data.internal_flows.po_to_toilet.set_amount(max(0, remaining_toilet), 'L')

        # Calculate remaining irrigation demand
        total_irrigation = sum(
            data.flows.get_flow(f'to_{surface}', 'L')
            for surface in ['roof', 'pavement', 'pervious']
        )
        remaining_irrigation = (
            total_irrigation -
            data.internal_flows.rt_to_irrigation.get_amount('L') -
            data.internal_flows.graywater_to_irrigation.get_amount('L') -
            data.internal_flows.wws_to_irrigation.get_amount('L')
        )
        data.internal_flows.po_to_irrigation.set_amount(max(0, remaining_irrigation), 'L')

        # Calculate total imported water including leakage
        total_potable = (
            sum(
                getattr(data.internal_flows, f"po_to_{use}").get_amount('L')
                for use in ['kitchen', 'bathroom', 'laundry', 'toilet']
            ) +
            max(0, remaining_irrigation)
        )
        leakage = data.flows.get_flow('to_groundwater', 'L')
        data.flows.set_flow('imported_water', total_potable + leakage, 'L')

    def solve(self, forcing: pd.Series) -> None:
        """Solve water demand allocation for the current timestep."""
        self._process_raintank_allocations()
        self._process_graywater_generation()
        self._process_wastewater_treatment()
        self._process_potable_demands()