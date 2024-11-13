from dataclasses import dataclass, field
from typing import Dict, List, Any
from duwcm.flow_manager import (
    RoofFlows, RainTankFlows, PavementFlows, PerviousFlows,
    VadoseFlows, GroundwaterFlows, StormwaterFlows,
    WastewaterFlows, DemandFlows, Flow
)

@dataclass
class Storage:
    """Storage state tracking"""
    amount: float = 0.0
    capacity: float = 0.0
    previous: float = 0.0  # Storage at previous timestep

    @property
    def change(self) -> float:
        """Calculate storage change from previous timestep"""
        return self.amount - self.previous

    def update(self) -> None:
        """Update previous storage with current amount"""
        self.previous = self.amount

@dataclass
class RoofData:
    """Roof component"""
    flows: RoofFlows = field(default_factory=RoofFlows)
    storage: Storage = field(default_factory=Storage)
    area: float = field(default=0, metadata={'unit': 'm^2'})
    effective_outflow: float = field(default=0.0, metadata={'unit': '%'})

@dataclass
class RainTankData:
    """Rain tank component"""
    flows: RainTankFlows = field(default_factory=RainTankFlows)
    storage: Storage = field(default_factory=Storage)
    area: float = field(default=0, metadata={'unit': 'm^2'})
    is_open: bool = field(default=False)
    install_ratio: float = field(default=0.0, metadata={'unit': '%'})
    effective_outflow: float = field(default=0.0, metadata={'unit': '%'})
    first_flush: float = field(default=0, metadata={'unit': 'L'})

@dataclass
class PavementData:
    """Pavement component"""
    flows: PavementFlows = field(default_factory=PavementFlows)
    storage: Storage = field(default_factory=Storage)
    area: float = field(default=0, metadata={'unit': 'm^2'})
    effective_outflow: float = field(default=0.0, metadata={'unit': '%'})
    infiltration_capacity: float = field(default=0.0, metadata={'unit': 'mm/d'})

@dataclass
class PerviousData:
    """Pervious surface component"""
    flows: PerviousFlows = field(default_factory=PerviousFlows)
    storage: Storage = field(default_factory=Storage)
    area: float = field(default=0, metadata={'unit': 'm^2'})
    infiltration_capacity: float = field(default=0, metadata={'unit': 'mm/d'})
    irrigation_factor: float = field(default=0, metadata={'unit': '-'})
    vadose_moisture: Storage = field(default_factory=Storage)

@dataclass
class VadoseData:
    """Vadose zone component"""
    flows: VadoseFlows = field(default_factory=VadoseFlows)
    moisture: Storage = field(default_factory=Storage)
    area: float = field(default=0, metadata={'unit': 'm^2'})
    equilibrium_moisture: float = field(default=0)
    transpiration_threshold: float = field(default=0)
    transpiration_factor: float = field(default=0)
    max_capillary: float = field(default=0)
    groundwater_level: Storage = field(default_factory=Storage)

@dataclass
class GroundwaterData:
    """Groundwater component"""
    flows: GroundwaterFlows = field(default_factory=GroundwaterFlows)
    water_level: Storage = field(default_factory=Storage)
    surface_water_level: Storage = field(default_factory=Storage)
    area: float = field(default=0, metadata={'unit': 'm^2'})
    leakage_rate: float = field(default=0.0, metadata={'unit': '%'})
    seepage_model: float = field(default=0.0, metadata={'unit': '-'})
    drainage_resistance: float = field(default=0.0, metadata={'unit': 'd'})
    seepage_resistance: float = field(default=0.0, metadata={'unit': 'd'})
    infiltration_recession: float = field(default=0.0, metadata={'unit': '-'})
    hydraulic_head: float = field(default=0.0, metadata={'unit': 'm-SL'})
    downward_seepage: float = field(default=0.0, metadata={'unit': 'mm/d'})

@dataclass
class StormwaterData:
    """Stormwater component"""
    flows: StormwaterFlows = field(default_factory=StormwaterFlows)
    storage: Storage = field(default_factory=Storage)
    area: float = field(default=0, metadata={'unit': 'm^2'})
    is_open: bool = field(default=False)
    first_flush: float = field(default=0, metadata={'unit': 'L'})

@dataclass
class WastewaterData:
    """Wastewater component"""
    cell_id: int = field(default=0)
    flows: WastewaterFlows = field(default_factory=WastewaterFlows)
    storage: Storage = field(default_factory=Storage)
    area: float = field(default=0, metadata={'unit': 'm^2'})

@dataclass
class DemandData:
    """Water demand component"""
    flows: DemandFlows = field(default_factory=DemandFlows)
    rt_storage: Storage = field(default_factory=Storage)  # Changed to Storage type
    rt_water_balance: float = field(default=0, metadata={'unit': 'L'})  # Rain tank water balance
    rt_domestic_demand: float = field(default=0, metadata={'unit': 'L'})  # Rain tank domestic demand
    rt_toilet_demand: float = field(default=0, metadata={'unit': 'L'})  # Rain tank toilet demand
    rt_irrigation_demand: float = field(default=0, metadata={'unit': 'L'})  # Rain tank irrigation demand
    wws_storage: float = field(default=0, metadata={'unit': 'L'})  # Wastewater storage

@dataclass
class ExternalData:
    """Container for external flow data"""
    flow: Flow = field(default_factory=Flow)


@dataclass
class UrbanWaterData:
    """Container for all urban water components"""
    roof: RoofData = field(default_factory=RoofData)
    raintank: RainTankData = field(default_factory=RainTankData)
    pavement: PavementData = field(default_factory=PavementData)
    pervious: PerviousData = field(default_factory=PerviousData)
    vadose: VadoseData = field(default_factory=VadoseData)
    groundwater: GroundwaterData = field(default_factory=GroundwaterData)
    stormwater: StormwaterData = field(default_factory=StormwaterData)
    wastewater: WastewaterData = field(default_factory=WastewaterData)
    demand: DemandData = field(default_factory=DemandData)

    # External components
    precipitation: ExternalData = field(default_factory=ExternalData)
    evaporation: ExternalData = field(default_factory=ExternalData)
    irrigation: ExternalData = field(default_factory=ExternalData)
    imported_water: ExternalData = field(default_factory=ExternalData)
    baseflow: ExternalData = field(default_factory=ExternalData)
    deep_seepage: ExternalData = field(default_factory=ExternalData)

    # Define components at class level
    COMPONENTS = [
        'roof', 'raintank', 'pavement', 'pervious', 'vadose',
        'groundwater', 'stormwater', 'demand', 'wastewater'
    ]

    # Define flow connections at class level
    FLOW_CONNECTIONS = {
        # Regular component flows
        ('roof', 'to_raintank'): ('raintank', 'from_roof'),
        ('roof', 'to_pervious'): ('pervious', 'from_roof'),
        ('roof', 'to_groundwater'): ('groundwater', 'from_roof'),
        ('raintank', 'to_pavement'): ('pavement', 'from_raintank'),
        ('raintank', 'to_stormwater'): ('stormwater', 'from_raintank'),
        ('pavement', 'to_pervious'): ('pervious', 'from_pavement'),
        ('pavement', 'to_groundwater_infiltration'): ('groundwater', 'from_pavement_infiltration'),
        ('pavement', 'to_groundwater_leakage'): ('groundwater', 'from_pavement_leakage'),
        ('pavement', 'to_stormwater'): ('stormwater', 'from_pavement'),
        ('pervious', 'to_vadose'): ('vadose', 'from_pervious'),
        ('pervious', 'to_groundwater'): ('groundwater', 'from_pervious'),
        ('pervious', 'to_stormwater'): ('stormwater', 'from_pervious'),
        ('vadose', 'to_groundwater'): ('groundwater', 'from_vadose'),
        ('groundwater', 'to_wastewater'): ('wastewater', 'from_groundwater'),
        ('stormwater', 'to_wastewater'): ('wastewater', 'from_stormwater'),
        ('demand', 'to_wastewater'): ('wastewater', 'from_demand'),
    }

    def __post_init__(self):
        """Link shared flows between components"""
        for (source_comp, source_flow), (target_comp, target_flow) in self.FLOW_CONNECTIONS.items():
            source = getattr(self, source_comp)
            target = getattr(self, target_comp)

            # For external components, link the Flow directly
            if isinstance(source, ExternalData):
                setattr(target.flows, target_flow, source.flow)
            elif isinstance(target, ExternalData):
                setattr(source.flows, source_flow, target.flow)
            # For regular components, link existing flows
            else:
                setattr(target.flows, target_flow, getattr(source.flows, source_flow))

        #Link shared variables between components
        self.pervious.vadose_moisture = self.vadose.moisture
        self.vadose.groundwater_level = self.groundwater.water_level
        self.demand.rt_storage = self.raintank.storage

    def validate_flows(self) -> Dict[str, List[str]]:
        """Validate flows between components"""
        issues = {
            'unlinked': [],    # Flows that should reference the same object but don't
            'mismatched': []  # Flows that have different amounts
        }

        # Check component links and amounts
        for (source_comp, source_flow), (target_comp, target_flow) in self.FLOW_CONNECTIONS.items():
            source = getattr(self, source_comp)
            target = getattr(self, target_comp)

            if isinstance(source, ExternalData) or isinstance(target, ExternalData):
                continue
            source_attr = getattr(source.flows, source_flow)
            target_attr = getattr(target.flows, target_flow)

            # Check if flows are properly linked
            if source_attr is not target_attr:
                issues['unlinked'].append(
                    f"{source_comp}.{source_flow} -> {target_comp}.{target_flow}"
                )

            # Check if amounts match
            elif abs(source_attr.amount - target_attr.amount) > 1e-10:
                issues['mismatched'].append(
                    f"{source_comp}.{source_flow}({source_attr.amount:.3f}) ≠ "
                    f"{target_comp}.{target_flow}({target_attr.amount:.3f})"
                )

        return issues

    def validate_storage(self) -> Dict[str, List[str]]:
        issues = {}

        # Iterate through all components
        for comp_name in self.COMPONENTS:
            component = getattr(self, comp_name)
            comp_issues = []

            # Get all attributes of the component
            for attr_name, attr_value in vars(component).items():
                # Check if attribute is a Storage instance
                if isinstance(attr_value, Storage):
                    # Check if storage exceeds capacity
                    if attr_value.amount > attr_value.capacity:
                        comp_issues.append(
                            f"{attr_name}: Storage ({attr_value.amount:.3f}) exceeds "
                            f"capacity ({attr_value.capacity:.3f})"
                        )

                    # Check for negative storage
                    if attr_value.amount < 0:
                        comp_issues.append(
                            f"{attr_name}: Negative storage: {attr_value.amount:.3f}"
                        )

            if comp_issues:
                issues[comp_name] = comp_issues

        return issues

    def validate_water_balance(self) -> Dict[str, Dict[str, float]]:
        balance_results = {}

        for comp_name in self.COMPONENTS:
            component = getattr(self, comp_name)
            flows = component.flows

            # Calculate inflows and outflows
            total_inflow = flows.get_total_inflow()
            total_outflow = flows.get_total_outflow()

            # Calculate total storage change across all Storage instances
            storage_changes = {}
            total_storage_change = 0

            for attr_name, attr_value in vars(component).items():
                if isinstance(attr_value, Storage):
                    change = attr_value.amount - attr_value.previous
                    storage_changes[attr_name] = change
                    total_storage_change += change

            # Calculate overall balance
            balance = total_inflow - total_outflow - total_storage_change

            balance_results[comp_name] = {
                'inflow': total_inflow,
                'outflow': total_outflow,
                'storage_changes': storage_changes,
                'total_storage_change': total_storage_change,
                'balance': balance
            }

        return balance_results

    def update_storage(self) -> None:
        """Update previous values for all Storage objects."""
        for comp_name in self.COMPONENTS:
            component = getattr(self, comp_name)
            for attr_value in vars(component).values():
                if isinstance(attr_value, Storage):
                    attr_value.update()

    def reset_flows(self) -> None:
        """Reset all flow amounts to zero"""
        for comp_name in self.COMPONENTS:
            comp_data = getattr(self, comp_name)
            comp_data.flows.reset_flows()

    def reset_storage(self) -> None:
        """Reset all Storage objects to initial values."""
        for comp_name in self.COMPONENTS:
            component = getattr(self, comp_name)
            for attr_value in vars(component).values():
                if isinstance(attr_value, Storage):
                    attr_value.amount = 0.0
                    attr_value.previous = 0.0

    def get_component(self, name: str) -> Any:
        """Get component by name."""
        if name not in self.COMPONENTS:
            raise ValueError(f"Unknown component: {name}")
        return getattr(self, name)

    def iter_components(self):
        """Iterate over all components."""
        for comp_name in self.COMPONENTS:
            yield comp_name, getattr(self, comp_name)

    def iter_storage_components(self):
        """Iterate over components that have Storage instances."""
        for comp_name in self.COMPONENTS:
            component = getattr(self, comp_name)
            storage_attrs = [
                attr_name for attr_name, attr_value in vars(component).items()
                if isinstance(attr_value, Storage)
            ]
            if storage_attrs:  # Only yield components that have Storage instances
                yield comp_name, component, storage_attrs