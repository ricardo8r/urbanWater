from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Any, Union, Optional

from duwcm.utils import BaseUnit
from duwcm.flow_manager import (
    Flow, MultiSourceFlow,
    RoofFlows, RainTankFlows, ImperviousFlows, PerviousFlows,
    VadoseFlows, GroundwaterFlows, StormwaterFlows,
    SewerageFlows, DemandFlows, DemandInternalFlows
)

@dataclass
class Storage:
    """
    Storage state tracking with unit conversion support.
    All internal storage is kept in liters for consistency.
    """
    _amount: float = 0.0
    _capacity: float = 0.0
    _previous: float = 0.0
    _area: Optional[float] = None
    _default_unit: BaseUnit = BaseUnit.CUBIC_METER

    def get_amount(self, unit: Optional[BaseUnit] = None) -> float:
        """Get current storage amount in specified unit"""
        unit = unit or self._default_unit
        return BaseUnit.convert(self._amount, BaseUnit.CUBIC_METER, unit, self._area)

    def set_amount(self, value: float, unit: Optional[BaseUnit] = None) -> None:
        """Set current storage amount from specified unit"""
        unit = unit or self._default_unit
        self._amount = BaseUnit.convert(value, unit, BaseUnit.CUBIC_METER, self._area)

    def get_capacity(self, unit: Optional[BaseUnit] = None) -> float:
        """Get storage capacity in specified unit"""
        unit = unit or self._default_unit
        return BaseUnit.convert(self._capacity, BaseUnit.CUBIC_METER, unit, self._area)

    def set_capacity(self, value: float, unit: Optional[BaseUnit] = None) -> None:
        """Set storage capacity from specified unit"""
        unit = unit or self._default_unit
        self._capacity = BaseUnit.convert(value, unit, BaseUnit.CUBIC_METER, self._area)

    def get_previous(self, unit: Optional[BaseUnit] = None) -> float:
        """Get previous storage amount in specified unit"""
        unit = unit or self._default_unit
        return BaseUnit.convert(self._previous, BaseUnit.CUBIC_METER, unit, self._area)

    def set_previous(self, value: float, unit: Optional[BaseUnit] = None) -> None:
        """Set previous storage amount from specified unit"""
        unit = unit or self._default_unit
        self._previous = BaseUnit.convert(value, unit, BaseUnit.CUBIC_METER, self._area)

    def set_area(self, area: float) -> None:
        """Set the area used for unit conversions"""
        self._area = area

    def set_default_unit(self, unit: BaseUnit) -> None:
        """Set the default unit for this storage instance"""
        self._default_unit = unit

    def get_change(self, unit: Optional[BaseUnit] = None) -> float:
        """Calculate storage change from previous timestep in specified unit"""
        unit = unit or self._default_unit
        return self.get_amount(unit) - self.get_previous(unit)

    def update(self) -> None:
        """Update previous storage with current amount"""
        self._previous = self._amount


@dataclass
class RoofData:
    """Roof component"""
    flows: RoofFlows = field(default_factory=RoofFlows)
    storage: Storage = field(default_factory=lambda: Storage(
        _default_unit=BaseUnit.CUBIC_METER,
        _capacity=0.0
    ))
    area: float = field(default=0, metadata={'unit': 'm^2'})
    effective_outflow: float = field(default=0.0, metadata={'unit': '%'})

@dataclass
class RainTankData:
    """Rain tank component"""
    flows: RainTankFlows = field(default_factory=RainTankFlows)
    storage: Storage = field(default_factory=lambda: Storage(
        _default_unit=BaseUnit.CUBIC_METER,
        _capacity=0.0
    ))
    area: float = field(default=0, metadata={'unit': 'm^2'})
    is_open: bool = field(default=False)
    install_ratio: float = field(default=0.0, metadata={'unit': '%'})
    effective_outflow: float = field(default=0.0, metadata={'unit': '%'})
    first_flush: float = field(default=0, metadata={'unit': 'L'})

@dataclass
class ImperviousData:
    """Imperviouys component"""
    flows: ImperviousFlows = field(default_factory=ImperviousFlows)
    storage: Storage = field(default_factory=lambda: Storage(
        _default_unit=BaseUnit.CUBIC_METER,
        _capacity=0.0
    ))
    area: float = field(default=0, metadata={'unit': 'm^2'})
    effective_outflow: float = field(default=0.0, metadata={'unit': '%'})

@dataclass
class PerviousData:
    """Pervious surface component"""
    flows: PerviousFlows = field(default_factory=PerviousFlows)
    storage: Storage = field(default_factory=lambda: Storage(
        _default_unit=BaseUnit.CUBIC_METER,
        _capacity=0.0
    ))
    area: float = field(default=0, metadata={'unit': 'm^2'})
    infiltration_capacity: float = field(default=0, metadata={'unit': 'mm/d'})
    irrigation_factor: float = field(default=0, metadata={'unit': '-'})
    vadose_moisture: Storage = field(default_factory=lambda: Storage(
        _default_unit=BaseUnit.MILLIMETER,
        _capacity=float('inf')
    ))

@dataclass
class VadoseData:
    """Vadose zone component"""
    flows: VadoseFlows = field(default_factory=VadoseFlows)
    moisture: Storage = field(default_factory=lambda: Storage(
        _default_unit=BaseUnit.MILLIMETER,
        _capacity=float('inf')
    ))
    area: float = field(default=0, metadata={'unit': 'm^2'})
    equilibrium_moisture: float = field(default=0)
    transpiration_threshold: float = field(default=0)
    transpiration_factor: float = field(default=0)
    max_capillary: float = field(default=0)
    groundwater_level: Storage = field(default_factory=lambda: Storage(
        _default_unit=BaseUnit.METER,
        _capacity=float('inf')
    ))

@dataclass
class GroundwaterData:
    """Groundwater component"""
    flows: GroundwaterFlows = field(default_factory=GroundwaterFlows)
    water_level: Storage = field(default_factory=lambda: Storage(
        _default_unit=BaseUnit.METER,
        _capacity=float('inf')
    ))
    surface_water_level: Storage = field(default_factory=lambda: Storage(
        _default_unit=BaseUnit.METER,
        _capacity=float('inf')
    ))
    area: float = field(default=0, metadata={'unit': 'm^2'})
    storage_coefficient: float = field(default=0.0, metadata={'unit': '-'})

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
    storage: Storage = field(default_factory=lambda: Storage(
        _default_unit=BaseUnit.CUBIC_METER,
        _capacity=0.0
    ))
    area: float = field(default=0, metadata={'unit': 'm^2'})
    is_open: bool = field(default=False)
    first_flush: float = field(default=0, metadata={'unit': 'L'})

@dataclass
class SewerageData:
    """Sewerage component"""
    flows: SewerageFlows = field(default_factory=SewerageFlows)
    storage: Storage = field(default_factory=lambda: Storage(
        _default_unit=BaseUnit.CUBIC_METER,
        _capacity=0.0
    ))
    area: float = field(default=0, metadata={'unit': 'm^2'})

@dataclass
class DemandData:
    """Water demand component"""
    flows: DemandFlows = field(default_factory=DemandFlows)
    internal_flows: DemandInternalFlows = field(default_factory=DemandInternalFlows)
    area: float = field(default=0, metadata={'unit': 'm^2'})
    rt_storage: Storage = field(default_factory=lambda: Storage(
        _default_unit=BaseUnit.CUBIC_METER,
        _capacity=0.0
    ))
    ww_storage: Storage = field(default_factory=lambda: Storage(
        _default_unit=BaseUnit.CUBIC_METER,
        _capacity=0.0
    ))


@dataclass
class UrbanWaterData:
    """Container for all urban water components"""
    roof: RoofData = field(default_factory=RoofData)
    raintank: RainTankData = field(default_factory=RainTankData)
    impervious: ImperviousData = field(default_factory=ImperviousData)
    pervious: PerviousData = field(default_factory=PerviousData)
    vadose: VadoseData = field(default_factory=VadoseData)
    groundwater: GroundwaterData = field(default_factory=GroundwaterData)
    stormwater: StormwaterData = field(default_factory=StormwaterData)
    sewerage: SewerageData = field(default_factory=SewerageData)
    demand: DemandData = field(default_factory=DemandData)

    # Define components at class level
    COMPONENTS = [
        'roof', 'raintank', 'impervious', 'pervious', 'vadose',
        'groundwater', 'demand', 'stormwater', 'sewerage'
    ]

    # Define flow connections at class level
    FLOW_CONNECTIONS = {
        # Regular component flows
        ('roof', 'to_raintank'): ('raintank', 'from_roof'),
        ('roof', 'to_pervious'): ('pervious', 'from_roof'),
        ('roof', 'to_stormwater'): ('stormwater', 'from_roof'),
        ('raintank', 'to_impervious'): ('impervious', 'from_raintank'),
        ('raintank', 'to_stormwater'): ('stormwater', 'from_raintank'),
        ('raintank', 'to_demand'): ('demand', 'from_raintank'),
        ('impervious', 'to_pervious'): ('pervious', 'from_impervious'),
        ('impervious', 'to_stormwater'): ('stormwater', 'from_impervious'),
        ('pervious', 'to_vadose'): ('vadose', 'from_pervious'),
        ('pervious', 'to_stormwater'): ('stormwater', 'from_pervious'),
        ('vadose', 'to_groundwater'): ('groundwater', 'from_vadose'),
        ('groundwater', 'to_sewerage'): ('sewerage', 'from_groundwater'),
        ('stormwater', 'to_sewerage'): ('sewerage', 'from_stormwater'),
        ('demand', 'to_sewerage'): ('sewerage', 'from_demand'),
        ('demand', 'to_stormwater'): ('stormwater', 'from_demand'),
        ('demand', 'to_roof'): ('roof', 'from_demand'),
        ('demand', 'to_impervious'): ('impervious', 'from_demand'),
        ('demand', 'to_pervious'): ('pervious', 'from_demand'),
        ('demand', 'to_groundwater'): ('groundwater', 'from_demand'),
    }

    def __post_init__(self):
        """Link shared flows between components while preserving flow directions"""
        for (source_comp, source_flow), (target_comp, target_flow) in self.FLOW_CONNECTIONS.items():
            source = getattr(self, source_comp)
            target = getattr(self, target_comp)

            # Get the flow objects
            source_flow_obj = getattr(source.flows, source_flow)
            target_flow_obj = getattr(target.flows, target_flow)

            # Link the flows
            source_flow_obj.link(target_flow_obj)

        # Link shared variables between components
        self.pervious.vadose_moisture = self.vadose.moisture
        self.vadose.groundwater_level = self.groundwater.water_level
        self.demand.rt_storage = self.raintank.storage

    def validate_flows(self) -> Dict[str, List[str]]:
        """Validate flows between components"""
        issues = {
            'unlinked': [],    # Flows that should reference the same object but don't
            'mismatched': []   # Flows that have different amounts
        }

        for (source_comp, source_flow), (target_comp, target_flow) in self.FLOW_CONNECTIONS.items():
            source = getattr(self, source_comp)
            target = getattr(self, target_comp)

            source_attr = getattr(source.flows, source_flow)
            target_attr = getattr(target.flows, target_flow)

            # Validate MultiSourceFlow connections
            if isinstance(source_attr, MultiSourceFlow):
                if not isinstance(target_attr, MultiSourceFlow):
                    issues['unlinked'].append(
                        f"{source_comp}.{source_flow} -> {target_comp}.{target_flow} (type mismatch)"
                    )
                    continue

                # Both are MultiSourceFlow, check their linkage
                if target_attr not in source_attr.linked_sources:
                    issues['unlinked'].append(
                        f"{source_comp}.{source_flow} -> {target_comp}.{target_flow}"
                    )
                elif abs(source_attr.amount - target_attr.amount) > 1e-10:
                    issues['mismatched'].append(
                        f"{source_comp}.{source_flow}({source_attr.amount:.3f}) ≠ "
                        f"{target_comp}.{target_flow}({target_attr.amount:.3f})"
                    )

            # Validate regular Flow connections
            elif isinstance(source_attr, Flow):
                if not isinstance(target_attr, Flow):
                    issues['unlinked'].append(
                        f"{source_comp}.{source_flow} -> {target_comp}.{target_flow} (type mismatch)"
                    )
                    continue

                # Both are Flow, check their linkage
                if source_attr.linked_flow is not target_attr:
                    issues['unlinked'].append(
                        f"{source_comp}.{source_flow} -> {target_comp}.{target_flow}"
                    )
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
                    if attr_value.get_amount() > attr_value.get_capacity()*1.001:
                        comp_issues.append(
                            f"{attr_name}: Storage ({attr_value.get_amount('m3'):.3f}) exceeds "
                            f"capacity ({attr_value.get_capacity('m3'):.3f})"
                        )

                    # Check for negative storage
                    if attr_value.get_amount() < 0:
                        comp_issues.append(
                            f"{attr_name}: Negative storage: {attr_value.get_amount('m3'):.3f}"
                        )

            if comp_issues:
                issues[comp_name] = comp_issues

        return issues

    def validate_water_balance(self, include_components: Optional[List[str]] = None,
                         skip_components: Optional[List[str]] = None) -> Dict[str, Dict[str, Any]]:
        balance_results = {}

        components_to_validate = set(self.COMPONENTS)
        if include_components is not None:
            components_to_validate = set(include_components)
        if skip_components is not None:
            components_to_validate -= set(skip_components)

        for comp_name in components_to_validate:
            component = getattr(self, comp_name)
            flows = component.flows

            # Track all flows by name
            inflows = {}
            outflows = {}

            # Categorize each flow by its name
            for flow_name, flow in vars(flows).items():
                if not hasattr(flow, 'direction'):
                    continue

                amount = flow.get_amount('m3')
                if flow.direction == 1:  # Inflow
                    inflows[flow_name] = amount
                else:  # Outflow
                    outflows[flow_name] = amount

            # Calculate storage changes with more detail
            storage_changes = {}
            total_storage_change = 0
            skip_storages = {
                'pervious': {'vadose_moisture'},
                'vadose': {'groundwater_level'},
                'demand': {'rt_storage'}
            }.get(comp_name, set())

            for attr_name, attr_value in vars(component).items():
                if isinstance(attr_value, Storage) and attr_name not in skip_storages:
                    change = attr_value.get_change('m3')
                    if comp_name == 'groundwater':
                        if attr_name == 'water_level':
                            change *= component.storage_coefficient
                        change = -1 * change
                    storage_changes[attr_name] = change
                    total_storage_change += change

            balance_results[comp_name] = {
                'inflows': inflows,
                'outflows': outflows,
                'storage_changes': storage_changes,
                'total_storage_change': total_storage_change,
                'total_inflow': sum(inflows.values()),
                'total_outflow': sum(outflows.values()),
                'balance': sum(inflows.values()) - sum(outflows.values()) - total_storage_change
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
                    attr_value.set_amount(0.0)
                    attr_value.set_previous(0.0)

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