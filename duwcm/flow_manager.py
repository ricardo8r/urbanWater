from dataclasses import dataclass, field
from typing import List, Union, Optional
from enum import Enum, auto, IntEnum

TO_METER = 0.001
TO_MM = 1000

class FlowType(Enum):
    PRECIPITATION = auto()
    EVAPORATION = auto()
    TRANSPIRATION = auto()
    RUNOFF = auto()
    INFILTRATION = auto()
    LEAKAGE = auto()
    PERCOLATION = auto()
    BASEFLOW = auto()
    SEEPAGE = auto()
    IRRIGATION = auto()
    IMPORTED_WATER = auto()
    WASTEWATER = auto()

class FlowDirection(IntEnum):
    IN = 1
    OUT = 2

class WaterUnit(Enum):
    """Units for water volumes and depths"""
    CUBIC_METER = 'm3'  # Base unit
    MILLIMETER = 'mm'
    METER = 'm'
    LITER = 'L'

    @staticmethod
    def convert(value: float, from_unit: Union['WaterUnit', str],
                to_unit: Union['WaterUnit', str], area: Optional[float] = None) -> float:
        """Convert between water units using m³ as base unit."""
        if isinstance(from_unit, str):
            from_unit = WaterUnit(from_unit)
        if isinstance(to_unit, str):
            to_unit = WaterUnit(to_unit)

        if from_unit == to_unit:
            return value

        if not area:
            return 0.0

        # Convert to m³
        match from_unit:
            case WaterUnit.CUBIC_METER:
                value_m3 = value
            case WaterUnit.LITER:
                value_m3 = value * TO_METER
            case WaterUnit.MILLIMETER:
                value_m3 = value * area * TO_METER
            case WaterUnit.METER:
                value_m3 = value * area

        # Convert from m³
        match to_unit:
            case WaterUnit.CUBIC_METER:
                return value_m3
            case WaterUnit.LITER:
                return value_m3 * TO_MM
            case WaterUnit.MILLIMETER:
                return value_m3 * TO_MM / area
            case WaterUnit.METER:
                return value_m3 / area

@dataclass
class Flow:
    """Base class for a flow with amounts in m³"""
    _amount: float = field(default=0.0)
    _type: FlowType = field(default=None)
    _direction: FlowDirection = field(default=None)
    _area: Optional[float] = field(default=None)
    linked_flow: Optional['Flow'] = field(default=None, repr=False)

    @property
    def amount(self) -> float:
        """Get flow amount in m³"""
        return self._amount

    @amount.setter
    def amount(self, value: float) -> None:
        """Set flow amount in m³"""
        self._amount = value
        if self.linked_flow is not None:
            self.linked_flow.set_amount_no_sync(self._amount)

    @property
    def type(self) -> FlowType:
        """Get the flow type"""
        return self._type

    @type.setter
    def type(self, value: FlowType) -> None:
        """Set the flow type"""
        self._type = value

    @property
    def direction(self) -> FlowDirection:
        """Get the flow direction"""
        return self._direction

    @direction.setter
    def direction(self, value: FlowDirection) -> None:
        """Set the flow direction"""
        self._direction = value

    def get_amount(self, unit: WaterUnit) -> float:
        """Get flow amount in specified unit"""
        return WaterUnit.convert(self._amount, WaterUnit.CUBIC_METER, unit, self._area)

    def set_amount(self, value: float, unit: WaterUnit) -> None:
        """Set flow amount from specified unit"""
        self._amount = WaterUnit.convert(value, unit, WaterUnit.CUBIC_METER, self._area)
        if self.linked_flow is not None:
            self.linked_flow.set_amount_no_sync(self._amount)

    def set_amount_no_sync(self, value: float) -> None:
        """Internal method to set amount without triggering sync"""
        self._amount = value

    def set_area(self, area: float) -> None:
        """Set the area used for unit conversions"""
        self._area = area

    def link(self, other_flow: 'Flow') -> None:
        """Link this flow to another flow for automatic synchronization"""
        self.linked_flow = other_flow
        other_flow.linked_flow = self

@dataclass
class MultiSourceFlow:
    """Flow that can accumulate from multiple sources. All amounts in m³."""
    type: FlowType = None
    direction: FlowDirection = None
    _sources: List[Flow] = field(default_factory=list)
    _area: Optional[float] = field(default=None)

    @property
    def amount(self) -> float:
        """Calculate total flow in m³ by summing all source amounts"""
        return sum(source.amount for source in self._sources)

    def get_amount(self, unit: WaterUnit) -> float:
        """Get total flow in specified unit"""
        return WaterUnit.convert(self.amount, WaterUnit.CUBIC_METER, unit, self._area)

    def add_source(self, source: Flow) -> None:
        """Add a source flow"""
        if not isinstance(source, Flow):
            raise TypeError("Source must be a Flow object")
        self._sources.append(source)

    def remove_source(self, source: Flow) -> None:
        """Remove a source flow if it exists"""
        if source in self._sources:
            self._sources.remove(source)

    def set_area(self, area: float) -> None:
        """Set area for unit conversions"""
        self._area = area

    def reset_flows(self) -> None:
        """Reset flows - called during model updates"""
        for source in self._sources:
            source.amount = 0.0

@dataclass
class ComponentFlows:
    """Base class for all component flows"""
    def get_flow(self, name: str, unit: Optional[WaterUnit] = None) -> float:
        """Get flow amount by name in specified unit (defaults to m³)"""
        if not hasattr(self, name):
            return 0.0

        flow = getattr(self, name)
        if unit:
            return flow.get_amount(unit)
        return flow.amount

    def set_flow(self, name: str, value: float, unit: Optional[WaterUnit] = None) -> None:
        """Set flow amount by name with optional unit (defaults to m³)"""
        if not hasattr(self, name):
            raise ValueError(f"Invalid flow name: {name}")

        flow = getattr(self, name)
        if isinstance(flow, MultiSourceFlow):
            raise AttributeError(f"Cannot set amount directly for MultiSourceFlow '{name}'")
        if isinstance(flow, Flow):
            if unit:
                flow.set_amount(value, unit)
            else:
                flow.amount = value
        else:
            raise ValueError(f"Invalid flow type for {name}")

    def set_flow_area(self, name: str, area: float) -> None:
        """Set area for a specific flow"""
        if not hasattr(self, name):
            raise ValueError(f"Invalid flow name: {name}")

        flow = getattr(self, name)
        if isinstance(flow, Flow):
            flow.set_area(area)

    def set_areas(self, area: float) -> None:
        """Set area for all flows in the component"""
        for attr_name, attr_value in vars(self).items():
            if isinstance(attr_value, Flow):
                attr_value.set_area(area)
            elif isinstance(attr_value, MultiSourceFlow):
                attr_value.set_area(area)

    def reset_flows(self) -> None:
        """Reset all flows to zero"""
        for flow in vars(self).values():
            if isinstance(flow, Flow):
                flow.amount = 0
            elif isinstance(flow, MultiSourceFlow):
                flow.reset_flows()

    def get_total_inflow(self, unit: Optional[WaterUnit] = None) -> float:
        """Calculate total inflow in specified unit (defaults to m³)"""
        total = sum(self.get_flow(name)
                   for name, flow in vars(self).items()
                   if isinstance(flow, (Flow, MultiSourceFlow))
                   and flow.direction == FlowDirection.IN)

        if unit:
            return WaterUnit.convert(total, WaterUnit.CUBIC_METER, unit, None)
        return total

    def get_total_outflow(self, unit: Optional[WaterUnit] = None) -> float:
        """Calculate total outflow in specified unit (defaults to m³)"""
        total = sum(self.get_flow(name)
                   for name, flow in vars(self).items()
                   if isinstance(flow, (Flow, MultiSourceFlow))
                   and flow.direction == FlowDirection.OUT)

        if unit:
            return WaterUnit.convert(total, WaterUnit.CUBIC_METER, unit, None)
        return total

@dataclass
class RoofFlows(ComponentFlows):
    """Roof component flows"""
    # Environmental flows
    precipitation: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.PRECIPITATION, FlowDirection.IN, None))
    evaporation: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.EVAPORATION, FlowDirection.OUT, None))
    # Component flows
    from_demand: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.IRRIGATION, FlowDirection.IN, None))
    to_raintank: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.RUNOFF, FlowDirection.OUT, None))
    to_pervious: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.RUNOFF, FlowDirection.OUT, None))
    to_groundwater: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.LEAKAGE, FlowDirection.OUT, None))

@dataclass
class RainTankFlows(ComponentFlows):
    """Raintank component flows"""
    # Environmental flows
    precipitation: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.PRECIPITATION, FlowDirection.IN, None))
    evaporation: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.EVAPORATION, FlowDirection.OUT, None))
    # Component flows
    from_roof: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.RUNOFF, FlowDirection.IN, None))
    to_pavement: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.RUNOFF, FlowDirection.OUT, None))
    to_stormwater: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.RUNOFF, FlowDirection.OUT, None))

@dataclass
class PavementFlows(ComponentFlows):
    """Pavement component flows"""
    # Environmental flows
    precipitation: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.PRECIPITATION, FlowDirection.IN, None))
    evaporation: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.EVAPORATION, FlowDirection.OUT, None))
    # Component flows
    from_demand: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.IRRIGATION, FlowDirection.IN, None))
    from_raintank: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.RUNOFF, FlowDirection.IN, None))
    to_pervious: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.RUNOFF, FlowDirection.OUT, None))
    to_groundwater_infiltration: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.INFILTRATION, FlowDirection.OUT, None))
    to_groundwater_leakage: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.LEAKAGE, FlowDirection.OUT, None))
    to_stormwater: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.RUNOFF, FlowDirection.OUT, None))

@dataclass
class PerviousFlows(ComponentFlows):
    """Pervious flows"""
    # Environmental flows
    precipitation: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.PRECIPITATION, FlowDirection.IN, None))
    evaporation: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.EVAPORATION, FlowDirection.OUT, None))
    # Component flows
    from_demand: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.IRRIGATION, FlowDirection.IN, None))
    from_roof: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.RUNOFF, FlowDirection.IN, None))
    from_pavement: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.RUNOFF, FlowDirection.IN, None))
    to_vadose: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.INFILTRATION, FlowDirection.OUT, None))
    to_groundwater: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.LEAKAGE, FlowDirection.OUT, None))
    to_stormwater: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.RUNOFF, FlowDirection.OUT, None))

@dataclass
class VadoseFlows(ComponentFlows):
    """Vadose zone flows"""
    # Environmental flows
    transpiration: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.TRANSPIRATION, FlowDirection.OUT, None))
    # Component flows
    from_pervious: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.INFILTRATION, FlowDirection.IN, None))
    to_groundwater: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.PERCOLATION, FlowDirection.OUT, None))

@dataclass
class GroundwaterFlows(ComponentFlows):
    """Groundwater flows"""
    # Environmental flows
    seepage: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.SEEPAGE, FlowDirection.OUT, None))
    baseflow: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.BASEFLOW, FlowDirection.OUT, None))
    # Component flows
    from_roof: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.LEAKAGE, FlowDirection.IN, None))
    from_pavement_infiltration: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.INFILTRATION, FlowDirection.IN, None))
    from_pavement_leakage: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.LEAKAGE, FlowDirection.IN, None))
    from_pervious: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.LEAKAGE, FlowDirection.IN, None))
    from_vadose: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.PERCOLATION, FlowDirection.IN, None))
    from_demand: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.LEAKAGE, FlowDirection.IN, None))
    to_wastewater: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.INFILTRATION, FlowDirection.OUT, None))

@dataclass
class StormwaterFlows(ComponentFlows):
    """Stormwater flows"""
    # Environmental flows
    precipitation: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.PRECIPITATION, FlowDirection.IN, None))
    evaporation: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.EVAPORATION, FlowDirection.OUT, None))
    # Component flows
    from_raintank: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.RUNOFF, FlowDirection.IN, None))
    from_pavement: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.RUNOFF, FlowDirection.IN, None))
    from_pervious: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.RUNOFF, FlowDirection.IN, None))
    from_upstream: MultiSourceFlow = field(
        default_factory=lambda: MultiSourceFlow(FlowType.RUNOFF, FlowDirection.IN, [], []))
    to_downstream: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.RUNOFF, FlowDirection.OUT, None))
    to_wastewater: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.WASTEWATER, FlowDirection.OUT, None))

@dataclass
class WastewaterFlows(ComponentFlows):
    """Wastewater flows"""
    # Component flows
    from_groundwater: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.INFILTRATION, FlowDirection.IN, None))
    from_stormwater: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.WASTEWATER, FlowDirection.IN, None))
    from_demand: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.WASTEWATER, FlowDirection.IN, None))
    from_upstream: MultiSourceFlow = field(
        default_factory=lambda: MultiSourceFlow(FlowType.WASTEWATER, FlowDirection.IN, [], []))
    to_downstream: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.WASTEWATER, FlowDirection.OUT, None))

@dataclass
class DemandFlows(ComponentFlows):
    """Demand water flows"""
    # Environmental flows
    imported_water: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.IMPORTED_WATER, FlowDirection.IN, None))
    # Component flows
    to_wastewater: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.WASTEWATER, FlowDirection.OUT, None))
    to_roof: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.IRRIGATION, FlowDirection.OUT, None))
    to_pavement: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.IRRIGATION, FlowDirection.OUT, None))
    to_pervious: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.IRRIGATION, FlowDirection.OUT, None))
    to_groundwater: Flow = field(
        default_factory=lambda: Flow(0.0, FlowType.LEAKAGE, FlowDirection.OUT, None))
