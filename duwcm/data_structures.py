from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Any, Union, Optional
from duwcm.flow_manager import (
    RoofFlows, RainTankFlows, PavementFlows, PerviousFlows,
    VadoseFlows, GroundwaterFlows, StormwaterFlows,
    WastewaterFlows, DemandFlows
)

TO_METER = 0.001
TO_MM = 1000

class StorageUnit(Enum):
    LITER = 'L'
    CUBIC_METER = 'm3'
    MILLIMETER = 'mm'
    METER = 'm'

    @staticmethod
    def convert(value: float, from_unit: Union['StorageUnit', str],
                to_unit: Union['StorageUnit', str],
                area: Optional[float] = None) -> float:
        """Convert between units using m³ as base unit."""
        if isinstance(from_unit, str):
            from_unit = StorageUnit(from_unit)
        if isinstance(to_unit, str):
            to_unit = StorageUnit(to_unit)

        if from_unit == to_unit:
            return value

        if not area:
            return 0.0

        # Convert to m³
        match from_unit:
            case StorageUnit.CUBIC_METER:
                value_m3 = value
            case StorageUnit.LITER:
                value_m3 = value * TO_METER
            case StorageUnit.MILLIMETER:
                value_m3 = value * area * TO_METER if area else ValueError("Area needed for mm")
            case StorageUnit.METER:
                value_m3 = value * area if area else ValueError("Area needed for m")

        # Convert from m³
        match to_unit:
            case StorageUnit.CUBIC_METER:
                return value_m3
            case StorageUnit.LITER:
                return value_m3 * TO_MM
            case StorageUnit.MILLIMETER:
                return value_m3 * TO_MM / area if area else ValueError("Area needed for mm")
            case StorageUnit.METER:
                return value_m3 / area if area else ValueError("Area needed for m")

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
    _default_unit: StorageUnit = StorageUnit.CUBIC_METER

    def get_amount(self, unit: Optional[StorageUnit] = None) -> float:
        """Get current storage amount in specified unit"""
        unit = unit or self._default_unit
        return StorageUnit.convert(self._amount, StorageUnit.CUBIC_METER, unit, self._area)

    def set_amount(self, value: float, unit: Optional[StorageUnit] = None) -> None:
        """Set current storage amount from specified unit"""
        unit = unit or self._default_unit
        self._amount = StorageUnit.convert(value, unit, StorageUnit.CUBIC_METER, self._area)

    def get_capacity(self, unit: Optional[StorageUnit] = None) -> float:
        """Get storage capacity in specified unit"""
        unit = unit or self._default_unit
        return StorageUnit.convert(self._capacity, StorageUnit.CUBIC_METER, unit, self._area)

    def set_capacity(self, value: float, unit: Optional[StorageUnit] = None) -> None:
        """Set storage capacity from specified unit"""
        unit = unit or self._default_unit
        self._capacity = StorageUnit.convert(value, unit, StorageUnit.CUBIC_METER, self._area)

    def get_previous(self, unit: Optional[StorageUnit] = None) -> float:
        """Get previous storage amount in specified unit"""
        unit = unit or self._default_unit
        return StorageUnit.convert(self._previous, StorageUnit.CUBIC_METER, unit, self._area)

    def set_previous(self, value: float, unit: Optional[StorageUnit] = None) -> None:
        """Set previous storage amount from specified unit"""
        unit = unit or self._default_unit
        self._previous = StorageUnit.convert(value, unit, StorageUnit.CUBIC_METER, self._area)

    def set_area(self, area: float) -> None:
        """Set the area used for unit conversions"""
        self._area = area

    def set_default_unit(self, unit: StorageUnit) -> None:
        """Set the default unit for this storage instance"""
        self._default_unit = unit

    def get_change(self, unit: Optional[StorageUnit] = None) -> float:
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
        _default_unit=StorageUnit.CUBIC_METER,
        _capacity=0.0
    ))
    area: float = field(default=0, metadata={'unit': 'm^2'})
    effective_outflow: float = field(default=0.0, metadata={'unit': '%'})

@dataclass
class RainTankData:
    """Rain tank component"""
    flows: RainTankFlows = field(default_factory=RainTankFlows)
    storage: Storage = field(default_factory=lambda: Storage(
        _default_unit=StorageUnit.CUBIC_METER,
        _capacity=0.0
    ))
    area: float = field(default=0, metadata={'unit': 'm^2'})
    is_open: bool = field(default=False)
    install_ratio: float = field(default=0.0, metadata={'unit': '%'})
    effective_outflow: float = field(default=0.0, metadata={'unit': '%'})
    first_flush: float = field(default=0, metadata={'unit': 'L'})

@dataclass
class PavementData:
    """Pavement component"""
    flows: PavementFlows = field(default_factory=PavementFlows)
    storage: Storage = field(default_factory=lambda: Storage(
        _default_unit=StorageUnit.CUBIC_METER,
        _capacity=0.0
    ))
    area: float = field(default=0, metadata={'unit': 'm^2'})
    effective_outflow: float = field(default=0.0, metadata={'unit': '%'})
    infiltration_capacity: float = field(default=0.0, metadata={'unit': 'mm/d'})

@dataclass
class PerviousData:
    """Pervious surface component"""
    flows: PerviousFlows = field(default_factory=PerviousFlows)
    storage: Storage = field(default_factory=lambda: Storage(
        _default_unit=StorageUnit.CUBIC_METER,
        _capacity=0.0
    ))
    area: float = field(default=0, metadata={'unit': 'm^2'})
    infiltration_capacity: float = field(default=0, metadata={'unit': 'mm/d'})
    irrigation_factor: float = field(default=0, metadata={'unit': '-'})
    vadose_moisture: Storage = field(default_factory=lambda: Storage(
        _default_unit=StorageUnit.MILLIMETER,
        _capacity=float('inf')
    ))

@dataclass
class VadoseData:
    """Vadose zone component"""
    flows: VadoseFlows = field(default_factory=VadoseFlows)
    moisture: Storage = field(default_factory=lambda: Storage(
        _default_unit=StorageUnit.MILLIMETER,
        _capacity=float('inf')
    ))
    area: float = field(default=0, metadata={'unit': 'm^2'})
    equilibrium_moisture: float = field(default=0)
    transpiration_threshold: float = field(default=0)
    transpiration_factor: float = field(default=0)
    max_capillary: float = field(default=0)
    groundwater_level: Storage = field(default_factory=lambda: Storage(
        _default_unit=StorageUnit.METER,
        _capacity=float('inf')
    ))

@dataclass
class GroundwaterData:
    """Groundwater component"""
    flows: GroundwaterFlows = field(default_factory=GroundwaterFlows)
    water_level: Storage = field(default_factory=lambda: Storage(
        _default_unit=StorageUnit.METER,
        _capacity=float('inf')
    ))
    surface_water_level: Storage = field(default_factory=lambda: Storage(
        _default_unit=StorageUnit.METER,
        _capacity=float('inf')
    ))
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
    storage: Storage = field(default_factory=lambda: Storage(
        _default_unit=StorageUnit.CUBIC_METER,
        _capacity=0.0
    ))
    area: float = field(default=0, metadata={'unit': 'm^2'})
    is_open: bool = field(default=False)
    first_flush: float = field(default=0, metadata={'unit': 'L'})

@dataclass
class WastewaterData:
    """Wastewater component"""
    flows: WastewaterFlows = field(default_factory=WastewaterFlows)
    storage: Storage = field(default_factory=lambda: Storage(
        _default_unit=StorageUnit.CUBIC_METER,
        _capacity=0.0
    ))
    area: float = field(default=0, metadata={'unit': 'm^2'})

@dataclass
class DemandData:
    """Water demand component"""
    flows: DemandFlows = field(default_factory=DemandFlows)
    rt_storage: Storage = field(default_factory=lambda: Storage(
        _default_unit=StorageUnit.CUBIC_METER,
        _capacity=0.0
    ))
    rt_water_balance: float = field(default=0, metadata={'unit': 'L'})
    rt_domestic_demand: float = field(default=0, metadata={'unit': 'L'})
    rt_toilet_demand: float = field(default=0, metadata={'unit': 'L'})
    rt_irrigation_demand: float = field(default=0, metadata={'unit': 'L'})
    wws_storage: float = field(default=0, metadata={'unit': 'L'})


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
        ('demand', 'to_roof'): ('roof', 'from_demand'),
        ('demand', 'to_pavement'): ('pavement', 'from_demand'),
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

            # Create references for two-way sync
            source_ref = source_flow_obj
            target_ref = target_flow_obj

            # Sync both get_flow and set_flow for both objects
            def make_get_flow(ref):
                return lambda: ref.amount

            def make_set_flow(ref):
                return lambda value: setattr(ref, 'amount', value)

            source_flow_obj.get_flow = make_get_flow(source_ref)
            source_flow_obj.set_flow = make_set_flow(target_ref)
            target_flow_obj.get_flow = make_get_flow(source_ref)
            target_flow_obj.set_flow = make_set_flow(source_ref)

        # Link shared variables between components
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
                    if attr_value.get_amount() > attr_value.get_capacity():
                        comp_issues.append(
                            f"{attr_name}: Storage ({attr_value.amount:.3f}) exceeds "
                            f"capacity ({attr_value.capacity:.3f})"
                        )

                    # Check for negative storage
                    if attr_value.get_amount() < 0:
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
                    change = attr_value.get_change('m3')
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