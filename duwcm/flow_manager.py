from dataclasses import dataclass, field
from typing import Dict, List, Union, Optional
from enum import Enum, auto, IntEnum
from collections import defaultdict

TO_METER = 0.001
TO_MM = 1000

class FlowProcess(Enum):
    """Physical processes affecting water movement"""
    PRECIPITATION = auto()
    EVAPORATION = auto()
    TRANSPIRATION = auto()
    INFILTRATION = auto()
    PERCOLATION = auto()
    RUNOFF = auto()
    SEEPAGE = auto()
    BASEFLOW = auto()

class WaterQuality(Enum):
    """Water quality/source classifications"""
    POTABLE = auto()      # Drinking water quality
    RAINWATER = auto()    # Direct precipitation collection
    STORMWATER = auto()   # Surface runoff collection
    GRAYWATER = auto()    # Lightly contaminated wastewater
    BLACKWATER = auto()   # Heavily contaminated wastewater
    TREATED = auto()      # Treated water (various levels possible)
    RAW = auto()          # Untreated water (groundwater, surface water)

class WaterUse(Enum):
    """End use classifications"""
    DOMESTIC = auto()     # Indoor residential use
    IRRIGATION = auto()   # Landscape/agricultural irrigation
    INDUSTRIAL = auto()   # Industrial/commercial processes
    ENVIRONMENTAL = auto() # Environmental flows/requirements
    LEAKAGE = auto()      # System losses
    OVERFLOW = auto()     # Excess discharge

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

        if value == float('inf'):
            return float('inf')
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
    _process: FlowProcess = field(default=None)
    _quality: WaterQuality = field(default=None)
    _use: WaterUse = field(default=None)
    _direction: FlowDirection = field(default=None)
    _area: Optional[float] = field(default=None)
    _volume_only: bool = field(default=False)
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
    def process(self) -> FlowProcess:
        """Get the flow type"""
        return self._process

    @process.setter
    def process(self, value: FlowProcess) -> None:
        """Set the flow type"""
        self._process = value

    @property
    def quality(self) -> WaterQuality:
        """Get the flow type"""
        return self._quality

    @quality.setter
    def quality(self, value: WaterQuality) -> None:
        """Set the flow type"""
        self._quality = value

    @property
    def use(self) -> WaterUse:
        """Get the flow type"""
        return self._use

    @use.setter
    def use(self, value: WaterUse) -> None:
        """Set the flow type"""
        self._use = value

    @property
    def direction(self) -> FlowDirection:
        """Get the flow direction"""
        return self._direction

    @direction.setter
    def direction(self, value: FlowDirection) -> None:
        """Set the flow direction"""
        self._direction = value

    def get_amount(self, unit: str) -> float:
        """Get flow amount in specified unit"""
        unit = WaterUnit(unit)
        if self._volume_only:
            if unit in [WaterUnit.MILLIMETER, WaterUnit.METER]:
                raise ValueError(f"Flow is volume-only. Cannot convert to {unit.value}")
            return WaterUnit.convert(self._amount, WaterUnit.CUBIC_METER, unit, area=1)
        return WaterUnit.convert(self._amount, WaterUnit.CUBIC_METER, unit, self._area)

    def set_amount(self, value: float, unit: str) -> None:
        """Set flow amount from specified unit"""
        unit = WaterUnit(unit)
        if self._volume_only:
            if unit in [WaterUnit.MILLIMETER, WaterUnit.METER]:
                raise ValueError(f"Flow is volume-only. Cannot convert from {unit.value}")
            self._amount = WaterUnit.convert(value, unit, WaterUnit.CUBIC_METER, area=1)
        else:
            self._amount = WaterUnit.convert(value, unit, WaterUnit.CUBIC_METER, self._area)
        if self.linked_flow is not None:
            self.linked_flow.set_amount_no_sync(self._amount)

    def set_amount_no_sync(self, value: float) -> None:
        """Internal method to set amount without triggering sync"""
        self._amount = value

    def set_area(self, area: float) -> None:
        """Set the area used for unit conversions"""
        self._area = area

    @property
    def volume_only(self) -> bool:
        """Get volume only flag"""
        return self._volume_only

    @volume_only.setter
    def volume_only(self, value: bool) -> None:
        """Set volume only flag"""
        self._volume_only = value

    def link(self, other_flow: 'Flow') -> None:
        """Link this flow to another flow for automatic synchronization"""
        self.linked_flow = other_flow
        other_flow.linked_flow = self

@dataclass
class MultiSourceFlow:
    """Flow that can accumulate from multiple sources. All amounts in m³."""
    _sources: List[Flow] = field(default_factory=list)
    _area: Optional[float] = field(default=None)
    _volume_only: bool = field(default=False)

    _process: FlowProcess = field(default=None)
    _quality: WaterQuality = field(default=None)
    _use: WaterUse = field(default=None)
    _direction: FlowDirection = None

    @property
    def amount(self) -> float:
        """Calculate total flow in m³ by summing all source amounts"""
        return sum(source.amount for source in self._sources)

    def get_amount(self, unit: str) -> float:
        """Get total flow in specified unit"""
        unit = WaterUnit(unit)
        if self._volume_only and unit in [WaterUnit.MILLIMETER, WaterUnit.METER]:
            raise ValueError(f"Flow is volume-only. Cannot convert to {unit.value}")
        if self._volume_only and unit in [WaterUnit.CUBIC_METER, WaterUnit.LITER]:
            return WaterUnit.convert(self.amount, WaterUnit.CUBIC_METER, unit, 1)
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

    @property
    def volume_only(self) -> bool:
        """Get volume only flag"""
        return self._volume_only

    @volume_only.setter
    def volume_only(self, value: bool) -> None:
        """Set volume only flag"""
        self._volume_only = value

    def reset_flows(self) -> None:
        """Reset flows - called during model updates"""
        for source in self._sources:
            source.amount = 0.0

    def get_amounts_by_quality(self) -> Dict[WaterQuality, float]:
        """Get breakdown of total flow by water quality"""
        quality_amounts = defaultdict(float)
        for source in self._sources:
            if source.quality:
                quality_amounts[source.quality] += source.amount
        return dict(quality_amounts)

    def get_amounts_by_use(self) -> Dict[WaterUse, float]:
        """Get breakdown of total flow by end use"""
        use_amounts = defaultdict(float)
        for source in self._sources:
            if source.use:
                use_amounts[source.use] += source.amount
        return dict(use_amounts)

    @property
    def direction(self) -> FlowDirection:
        """Get the flow direction based on sources' directions"""
        if self._direction is not None:
            return self._direction
        # Check if all sources have the same direction
        directions = {source.direction for source in self._sources}
        if len(directions) == 1:
            return next(iter(directions))
        if self._direction:
            return self._direction
        raise ValueError("MultiSourceFlow has sources with mixed directions and no explicit direction set")

    @direction.setter
    def direction(self, value: FlowDirection) -> None:
        """Set the flow direction"""
        self._direction = value

    @property
    def process(self) -> FlowProcess:
        """Get the flow type"""
        return self._process

    @process.setter
    def process(self, value: FlowProcess) -> None:
        """Set the flow type"""
        self._process = value

    @property
    def quality(self) -> WaterQuality:
        """Get the flow type"""
        return self._quality

    @quality.setter
    def quality(self, value: WaterQuality) -> None:
        """Set the flow type"""
        self._quality = value

    @property
    def use(self) -> WaterUse:
        """Get the flow type"""
        return self._use

    @use.setter
    def use(self, value: WaterUse) -> None:
        """Set the flow type"""
        self._use = value

@dataclass
class ComponentFlows:
    """Base class for all component flows"""
    _capacity: float = field(default=float('inf'))
    _area: Optional[float] = field(default=None)

    @property
    def remaining_capacity(self) -> float:
        """Calculate remaining capacity based on current total inflow"""
        return max(0, self._capacity - self.total_inflow)

    def set_capacity(self, capacity: float, unit: Optional[str] = None) -> None:
        """Set maximum flow capacity"""
        unit = unit or 'm3'
        if unit not in ['m3', 'L']:
            raise ValueError("Capacity unit must be 'm3' or 'L'")

        self._capacity = WaterUnit.convert(capacity, unit, WaterUnit.CUBIC_METER, area=1)

    def get_capacity(self, unit: Optional[str] = None) -> float:
        """Get maximum capacity in specified unit"""
        unit = unit or 'm3'
        if unit not in ['m3', 'L']:
            raise ValueError("Capacity unit must be 'm3' or 'L'")

        return WaterUnit.convert(self._capacity, WaterUnit.CUBIC_METER, unit, area=1)

    def set_flow(self, name: str, value: float, unit: Optional[str] = None) -> float:
        """
        Set flow amount by name with optional unit.
        Returns excess amount that couldn't be added due to capacity limits.
        """
        if not hasattr(self, name):
            raise ValueError(f"Invalid flow name: {name}")

        flow = getattr(self, name)
        if isinstance(flow, MultiSourceFlow):
            raise AttributeError(f"Cannot set amount directly for MultiSourceFlow '{name}'")

        # Convert input value to m³ at the start
        unit = unit or 'm3'
        # Use area=1 for volume-only flows
        conversion_area = 1 if flow.volume_only else self._area
        value_m3 = WaterUnit.convert(value, unit, WaterUnit.CUBIC_METER, conversion_area)

        # Get current flow in m³ for capacity calculation
        current_flow_m3 = flow.amount
        available_m3 = self._capacity + current_flow_m3 - self.get_total_inflow('m3')

        # Limit new value to available capacity
        value_m3 = min(value_m3, available_m3)
        excess_m3 = max(0, value_m3 - available_m3)

        if isinstance(flow, Flow):
            flow.set_amount(value_m3, 'm3')
        else:
            raise ValueError(f"Invalid flow type for {name}")

        # Convert excess back to original unit using same area logic
        return WaterUnit.convert(excess_m3, WaterUnit.CUBIC_METER, unit, conversion_area)

    def get_flow(self, name: str, unit: Optional[WaterUnit] = None) -> float:
        """Get flow amount by name in specified unit (defaults to m³)"""
        if not hasattr(self, name):
            return 0.0

        flow = getattr(self, name)
        if unit:
            return flow.get_amount(unit)
        return flow.amount

    def set_flow_area(self, name: str, area: float) -> None:
        """Set area for a specific flow"""
        if not hasattr(self, name):
            raise ValueError(f"Invalid flow name: {name}")

        flow = getattr(self, name)
        if isinstance(flow, Flow):
            flow.set_area(area)

    def set_areas(self, area: float) -> None:
        """Set area for all flows in the component"""
        self._area = area
        for attr_value in vars(self).values():
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

    @property
    def total_inflow(self) -> float:
        """Calculate total inflow in m³"""
        return sum(flow.amount for flow in vars(self).values()
                  if isinstance(flow, (Flow, MultiSourceFlow))
                  and flow.direction == FlowDirection.IN)

    @property
    def total_outflow(self) -> float:
        """Calculate total outflow in m³"""
        return sum(flow.amount for flow in vars(self).values()
                  if isinstance(flow, (Flow, MultiSourceFlow))
                  and flow.direction == FlowDirection.OUT)

    def get_total_inflow(self, unit: Optional[WaterUnit] = None) -> float:
        """Calculate total inflow in specified unit (defaults to m³)"""
        total = 0.0
        for name, flow in vars(self).items():
            if isinstance(flow, (Flow, MultiSourceFlow)) and flow.direction == FlowDirection.IN:
                total += flow.get_amount(unit) if unit else flow.amount
        return total

    def get_total_outflow(self, unit: Optional[WaterUnit] = None) -> float:
        """Calculate total outflow in specified unit (defaults to m³)"""
        total = 0.0
        for name, flow in vars(self).items():
            if isinstance(flow, (Flow, MultiSourceFlow)) and flow.direction == FlowDirection.OUT:
                total += flow.get_amount(unit) if unit else flow.amount
        return total

@dataclass
class RoofFlows(ComponentFlows):
    """
    Roof component flows tracking water movement on roof surfaces.

    Tracks:
    - Direct precipitation input
    - Irrigation application 
    - Evaporation loss
    - Runoff to raintanks (effective)
    - Runoff to pervious areas (non-effective)
    - Leakage to groundwater
    """
    # Environmental inputs
    precipitation: Flow = field(
        default_factory=lambda: Flow(
            _process=FlowProcess.PRECIPITATION,
            _quality=WaterQuality.RAINWATER,
            _use=WaterUse.ENVIRONMENTAL,
            _direction=FlowDirection.IN
        ))

    evaporation: Flow = field(
        default_factory=lambda: Flow(
            _process=FlowProcess.EVAPORATION,
            _quality=WaterQuality.RAW,
            _use=WaterUse.ENVIRONMENTAL,
            _direction=FlowDirection.OUT
        ))

    # Irrigation inputs
    from_demand: Flow = field(
        default_factory=lambda: Flow(
            _process=None,
            _quality=WaterQuality.TREATED,
            _use=WaterUse.IRRIGATION,
            _direction=FlowDirection.IN
        ))

    # Runoff outputs
    to_raintank: Flow = field(
        default_factory=lambda: Flow(
            _process=FlowProcess.RUNOFF,
            _quality=WaterQuality.RAINWATER,
            _use=WaterUse.OVERFLOW,
            _direction=FlowDirection.OUT
        ))

    to_pervious: Flow = field(
        default_factory=lambda: Flow(
            _process=FlowProcess.RUNOFF,
            _quality=WaterQuality.RAINWATER,
            _use=WaterUse.OVERFLOW,
            _direction=FlowDirection.OUT
        ))

    # Losses
    to_groundwater: Flow = field(
        default_factory=lambda: Flow(
            _process=FlowProcess.INFILTRATION,
            _quality=WaterQuality.TREATED,
            _use=WaterUse.LEAKAGE,
            _direction=FlowDirection.OUT
        ))

@dataclass
class RainTankFlows(ComponentFlows):
    """
    Raintank component flows tracking water storage and distribution.

    Tracks:
    - Direct precipitation (if tank is open)
    - Roof runoff collection
    - Evaporation loss (if tank is open)
    - Overflow distribution to pavement and stormwater
    """
    # Environmental inputs/outputs (for open tanks)
    precipitation: Flow = field(
        default_factory=lambda: Flow(
            _process=FlowProcess.PRECIPITATION,
            _quality=WaterQuality.RAINWATER,
            _use=WaterUse.ENVIRONMENTAL,
            _direction=FlowDirection.IN
        ))

    evaporation: Flow = field(
        default_factory=lambda: Flow(
            _process=FlowProcess.EVAPORATION,
            _quality=WaterQuality.RAINWATER,
            _use=WaterUse.ENVIRONMENTAL,
            _direction=FlowDirection.OUT
        ))

    # Collection inputs
    from_roof: Flow = field(
        default_factory=lambda: Flow(
            _process=FlowProcess.RUNOFF,
            _quality=WaterQuality.RAINWATER,
            _use=WaterUse.DOMESTIC,
            _direction=FlowDirection.IN
        ))

    # Distribution/overflow outputs
    to_pavement: Flow = field(
        default_factory=lambda: Flow(
            _process=FlowProcess.RUNOFF,
            _quality=WaterQuality.RAINWATER,
            _use=WaterUse.OVERFLOW,
            _direction=FlowDirection.OUT
        ))

    to_stormwater: Flow = field(
        default_factory=lambda: Flow(
            _process=FlowProcess.RUNOFF,
            _quality=WaterQuality.RAINWATER,
            _use=WaterUse.OVERFLOW,
            _direction=FlowDirection.OUT
        ))

    # Supply outputs (linked to demand)
    to_demand: Flow = field(
        default_factory=lambda: Flow(
            _process=None,
            _quality=WaterQuality.RAINWATER,
            _use=WaterUse.DOMESTIC,
            _direction=FlowDirection.OUT
        ))

@dataclass
class PavementFlows(ComponentFlows):
    """
    Pavement component flows tracking water movement on impervious surfaces.

    Tracks:
    - Direct precipitation input
    - Irrigation application
    - Raintank overflow input
    - Evaporation loss
    - Surface runoff distribution
    - Infiltration and leakage to groundwater
    """
    # Environmental inputs/outputs
    precipitation: Flow = field(
        default_factory=lambda: Flow(
            _process=FlowProcess.PRECIPITATION,
            _quality=WaterQuality.RAINWATER,
            _use=WaterUse.ENVIRONMENTAL,
            _direction=FlowDirection.IN
        ))

    evaporation: Flow = field(
        default_factory=lambda: Flow(
            _process=FlowProcess.EVAPORATION,
            _quality=WaterQuality.RAW,
            _use=WaterUse.ENVIRONMENTAL,
            _direction=FlowDirection.OUT
        ))

    # Managed inputs
    from_demand: Flow = field(
        default_factory=lambda: Flow(
            _process=None,
            _quality=WaterQuality.TREATED,
            _use=WaterUse.IRRIGATION,
            _direction=FlowDirection.IN
        ))

    from_raintank: Flow = field(
        default_factory=lambda: Flow(
            _process=FlowProcess.RUNOFF,
            _quality=WaterQuality.RAINWATER,
            _use=WaterUse.OVERFLOW,
            _direction=FlowDirection.IN
        ))

    # Surface runoff outputs
    to_pervious: Flow = field(
        default_factory=lambda: Flow(
            _process=FlowProcess.RUNOFF,
            _quality=WaterQuality.STORMWATER,
            _use=WaterUse.OVERFLOW,
            _direction=FlowDirection.OUT
        ))

    to_stormwater: Flow = field(
        default_factory=lambda: Flow(
            _process=FlowProcess.RUNOFF,
            _quality=WaterQuality.STORMWATER,
            _use=WaterUse.OVERFLOW,
            _direction=FlowDirection.OUT
        ))

    # Groundwater interactions
    to_groundwater_infiltration: Flow = field(
        default_factory=lambda: Flow(
            _process=FlowProcess.INFILTRATION,
            _quality=WaterQuality.STORMWATER,
            _use=WaterUse.ENVIRONMENTAL,
            _direction=FlowDirection.OUT
        ))

    to_groundwater_leakage: Flow = field(
        default_factory=lambda: Flow(
            _process=FlowProcess.INFILTRATION,
            _quality=WaterQuality.TREATED,
            _use=WaterUse.LEAKAGE,
            _direction=FlowDirection.OUT
        ))

@dataclass
class PerviousFlows(ComponentFlows):
    """
    Pervious component flows tracking water movement on permeable surfaces.

    Tracks:
    - Direct precipitation input
    - Irrigation application
    - Runoff inputs from impervious surfaces
    - Evaporation loss
    - Infiltration to vadose zone
    - Surface runoff to stormwater
    - Leakage to groundwater
    """
    # Environmental inputs/outputs
    precipitation: Flow = field(
        default_factory=lambda: Flow(
            _process=FlowProcess.PRECIPITATION,
            _quality=WaterQuality.RAINWATER,
            _use=WaterUse.ENVIRONMENTAL,
            _direction=FlowDirection.IN
        ))

    evaporation: Flow = field(
        default_factory=lambda: Flow(
            _process=FlowProcess.EVAPORATION,
            _quality=WaterQuality.RAW,
            _use=WaterUse.ENVIRONMENTAL,
            _direction=FlowDirection.OUT
        ))

    # Managed inputs
    from_demand: Flow = field(
        default_factory=lambda: Flow(
            _process=None,
            _quality=WaterQuality.TREATED,
            _use=WaterUse.IRRIGATION,
            _direction=FlowDirection.IN
        ))

    # Surface runoff inputs
    from_roof: Flow = field(
        default_factory=lambda: Flow(
            _process=FlowProcess.RUNOFF,
            _quality=WaterQuality.RAINWATER,
            _use=WaterUse.OVERFLOW,
            _direction=FlowDirection.IN
        ))

    from_pavement: Flow = field(
        default_factory=lambda: Flow(
            _process=FlowProcess.RUNOFF,
            _quality=WaterQuality.STORMWATER,
            _use=WaterUse.OVERFLOW,
            _direction=FlowDirection.IN
        ))

    # Subsurface outputs
    to_vadose: Flow = field(
        default_factory=lambda: Flow(
            _process=FlowProcess.INFILTRATION,
            _quality=WaterQuality.RAW,
            _use=WaterUse.ENVIRONMENTAL,
            _direction=FlowDirection.OUT
        ))

    to_groundwater: Flow = field(
        default_factory=lambda: Flow(
            _process=FlowProcess.INFILTRATION,
            _quality=WaterQuality.TREATED,
            _use=WaterUse.LEAKAGE,
            _direction=FlowDirection.OUT
        ))

    # Surface outputs
    to_stormwater: Flow = field(
        default_factory=lambda: Flow(
            _process=FlowProcess.RUNOFF,
            _quality=WaterQuality.STORMWATER,
            _use=WaterUse.OVERFLOW,
            _direction=FlowDirection.OUT
        ))

@dataclass
class VadoseFlows(ComponentFlows):
    """
    Vadose zone component flows tracking water movement in unsaturated soil.

    Tracks:
    - Infiltration from pervious surfaces
    - Transpiration loss through vegetation
    - Percolation to groundwater
    """
    # Environmental outputs
    transpiration: Flow = field(
        default_factory=lambda: Flow(
            _process=FlowProcess.TRANSPIRATION,
            _quality=WaterQuality.RAW,
            _use=WaterUse.ENVIRONMENTAL,
            _direction=FlowDirection.OUT
        ))

    # Subsurface inputs
    from_pervious: Flow = field(
        default_factory=lambda: Flow(
            _process=FlowProcess.INFILTRATION,
            _quality=WaterQuality.RAW,  # Mixed quality from surface inputs
            _use=WaterUse.ENVIRONMENTAL,
            _direction=FlowDirection.IN
        ))

    # Subsurface outputs
    to_groundwater: Flow = field(
        default_factory=lambda: Flow(
            _process=FlowProcess.PERCOLATION,
            _quality=WaterQuality.RAW,
            _use=WaterUse.ENVIRONMENTAL,
            _direction=FlowDirection.OUT
        ))

@dataclass
class GroundwaterFlows(ComponentFlows):
    """
    Groundwater component flows tracking water movement in saturated zone.

    Tracks:
    - Natural inflows from vadose zone percolation
    - Infiltration from surfaces (pavement)
    - Leakage inputs from infrastructure
    - Baseflow to surface water
    - Deep seepage losses
    - Infiltration to wastewater system
    """
    # Natural environmental outputs
    seepage: Flow = field(
        default_factory=lambda: Flow(
            _process=FlowProcess.SEEPAGE,
            _quality=WaterQuality.RAW,
            _use=WaterUse.ENVIRONMENTAL,
            _direction=FlowDirection.OUT
        ))

    baseflow: Flow = field(
        default_factory=lambda: Flow(
            _process=FlowProcess.BASEFLOW,
            _quality=WaterQuality.RAW,
            _use=WaterUse.ENVIRONMENTAL,
            _direction=FlowDirection.OUT
        ))

    # Infrastructure leakage inputs
    from_roof: Flow = field(
        default_factory=lambda: Flow(
            _process=FlowProcess.INFILTRATION,
            _quality=WaterQuality.TREATED,
            _use=WaterUse.LEAKAGE,
            _direction=FlowDirection.IN
        ))

    from_demand: Flow = field(
        default_factory=lambda: Flow(
            _process=FlowProcess.INFILTRATION,
            _quality=WaterQuality.TREATED,
            _use=WaterUse.LEAKAGE,
            _direction=FlowDirection.IN
        ))

    # Surface infiltration inputs
    from_pavement_infiltration: Flow = field(
        default_factory=lambda: Flow(
            _process=FlowProcess.INFILTRATION,
            _quality=WaterQuality.STORMWATER,
            _use=WaterUse.ENVIRONMENTAL,
            _direction=FlowDirection.IN
        ))

    from_pavement_leakage: Flow = field(
        default_factory=lambda: Flow(
            _process=FlowProcess.INFILTRATION,
            _quality=WaterQuality.TREATED,
            _use=WaterUse.LEAKAGE,
            _direction=FlowDirection.IN
        ))

    from_pervious: Flow = field(
        default_factory=lambda: Flow(
            _process=FlowProcess.INFILTRATION,
            _quality=WaterQuality.TREATED,
            _use=WaterUse.LEAKAGE,
            _direction=FlowDirection.IN
        ))

    # Natural subsurface inputs
    from_vadose: Flow = field(
        default_factory=lambda: Flow(
            _process=FlowProcess.PERCOLATION,
            _quality=WaterQuality.RAW,
            _use=WaterUse.ENVIRONMENTAL,
            _direction=FlowDirection.IN
        ))

    # Infrastructure interaction outputs
    to_wastewater: Flow = field(
        default_factory=lambda: Flow(
            _process=FlowProcess.INFILTRATION,
            _quality=WaterQuality.RAW,
            _use=WaterUse.LEAKAGE,
            _direction=FlowDirection.OUT
        ))

@dataclass
class StormwaterFlows(ComponentFlows):
    """
    Stormwater component flows tracking urban drainage system.

    Tracks:
    - Direct precipitation on open facilities
    - Surface runoff collection from urban surfaces
    - Evaporation from open facilities
    - Upstream drainage inputs
    - Downstream discharge
    - Combined sewer inputs to wastewater
    """
    # Environmental inputs/outputs (for open facilities)
    precipitation: Flow = field(
        default_factory=lambda: Flow(
            _process=FlowProcess.PRECIPITATION,
            _quality=WaterQuality.RAINWATER,
            _use=WaterUse.ENVIRONMENTAL,
            _direction=FlowDirection.IN
        ))

    evaporation: Flow = field(
        default_factory=lambda: Flow(
            _process=FlowProcess.EVAPORATION,
            _quality=WaterQuality.STORMWATER,
            _use=WaterUse.ENVIRONMENTAL,
            _direction=FlowDirection.OUT
        ))

    # Surface runoff inputs
    from_raintank: Flow = field(
        default_factory=lambda: Flow(
            _process=FlowProcess.RUNOFF,
            _quality=WaterQuality.RAINWATER,
            _use=WaterUse.OVERFLOW,
            _direction=FlowDirection.IN
        ))

    from_pavement: Flow = field(
        default_factory=lambda: Flow(
            _process=FlowProcess.RUNOFF,
            _quality=WaterQuality.STORMWATER,
            _use=WaterUse.OVERFLOW,
            _direction=FlowDirection.IN
        ))

    from_pervious: Flow = field(
        default_factory=lambda: Flow(
            _process=FlowProcess.RUNOFF,
            _quality=WaterQuality.STORMWATER,
            _use=WaterUse.OVERFLOW,
            _direction=FlowDirection.IN
        ))

    # Network flows
    from_upstream: MultiSourceFlow = field(
        default_factory=lambda: MultiSourceFlow(
            _process=FlowProcess.RUNOFF,
            _quality=WaterQuality.STORMWATER,
            _use=WaterUse.OVERFLOW,
            _direction=FlowDirection.IN
        ))

    to_downstream: Flow = field(
        default_factory=lambda: Flow(
            _process=FlowProcess.RUNOFF,
            _quality=WaterQuality.STORMWATER,
            _use=WaterUse.OVERFLOW,
            _direction=FlowDirection.OUT
        ))

    # Combined sewer output
    to_wastewater: Flow = field(
        default_factory=lambda: Flow(
            _process=None,
            _quality=WaterQuality.STORMWATER,
            _use=WaterUse.OVERFLOW,
            _direction=FlowDirection.OUT
        ))

@dataclass
class WastewaterFlows(ComponentFlows):
    """
    Wastewater component flows tracking sewage collection and transport.

    Tracks:
    - Domestic wastewater inputs
    - Groundwater infiltration
    - Combined sewer inputs from stormwater
    - Upstream collection inputs
    - Downstream transport
    """
    # Collection system inputs
    from_demand: Flow = field(
        default_factory=lambda: Flow(
            _process=None,
            _quality=WaterQuality.BLACKWATER,
            _use=WaterUse.DOMESTIC,
            _direction=FlowDirection.IN
        ))

    # Infrastructure interaction
    from_groundwater: Flow = field(
        default_factory=lambda: Flow(
            _process=FlowProcess.INFILTRATION,
            _quality=WaterQuality.RAW,
            _use=WaterUse.LEAKAGE,
            _direction=FlowDirection.IN
        ))

    # Combined sewer inputs
    from_stormwater: Flow = field(
        default_factory=lambda: Flow(
            _process=None,
            _quality=WaterQuality.STORMWATER,
            _use=WaterUse.OVERFLOW,
            _direction=FlowDirection.IN
        ))

    # Network flows
    from_upstream: MultiSourceFlow = field(
        default_factory=lambda: MultiSourceFlow(
            _process=None,
            _quality=WaterQuality.BLACKWATER,  # Mixed quality in reality
            _use=WaterUse.DOMESTIC,
            _direction=FlowDirection.IN
        ))

    to_downstream: Flow = field(
        default_factory=lambda: Flow(
            _process=None,
            _quality=WaterQuality.BLACKWATER,  # Mixed quality in reality
            _use=WaterUse.DOMESTIC,
            _direction=FlowDirection.OUT
        ))

#    # Optional: Treatment outputs (if treatment occurs locally)
#    to_reuse: Flow = field(
#        default_factory=lambda: Flow(
#            _process=None,
#            _quality=WaterQuality.TREATED,
#            _use=WaterUse.DOMESTIC,
#            _direction=FlowDirection.OUT
#        ))

@dataclass
class DemandFlows(ComponentFlows):
    """
    Demand component flows tracking water supply and distribution.

    Tracks:
    - Imported water supply
    - Alternative water supplies (rainwater, treated)
    - Distribution to end uses
    - Wastewater generation
    - System losses
    """
    # Primary supply
    imported_water: Flow = field(
        default_factory=lambda: Flow(
            _process=None,
            _quality=WaterQuality.POTABLE,
            _use=WaterUse.DOMESTIC,
            _direction=FlowDirection.IN,
            _volume_only=True
        ))

    # Alternative supplies
    from_raintank: Flow = field(
        default_factory=lambda: Flow(
            _process=None,
            _quality=WaterQuality.RAINWATER,
            _use=WaterUse.DOMESTIC,
            _direction=FlowDirection.IN,
            _volume_only=True
        ))

    # Distribution outputs
    to_wastewater: Flow = field(
        default_factory=lambda: Flow(
            _process=None,
            _quality=WaterQuality.BLACKWATER,
            _use=WaterUse.DOMESTIC,
            _direction=FlowDirection.OUT,
            _volume_only=True
        ))

    # Irrigation outputs
    to_roof: Flow = field(
        default_factory=lambda: Flow(
            _process=None,
            _quality=WaterQuality.TREATED,
            _use=WaterUse.IRRIGATION,
            _direction=FlowDirection.OUT,
            _volume_only=True
        ))

    to_pavement: Flow = field(
        default_factory=lambda: Flow(
            _process=None,
            _quality=WaterQuality.TREATED,
            _use=WaterUse.IRRIGATION,
            _direction=FlowDirection.OUT,
            _volume_only=True
        ))

    to_pervious: Flow = field(
        default_factory=lambda: Flow(
            _process=None,
            _quality=WaterQuality.TREATED,
            _use=WaterUse.IRRIGATION,
            _direction=FlowDirection.OUT,
            _volume_only=True
        ))

    # System losses
    to_groundwater: Flow = field(
        default_factory=lambda: Flow(
            _process=FlowProcess.INFILTRATION,
            _quality=WaterQuality.TREATED,
            _use=WaterUse.LEAKAGE,
            _direction=FlowDirection.OUT,
            _volume_only=True
        ))

@dataclass
class DemandInternalFlows(ComponentFlows):
    """
    Internal demand flows tracking detailed water use paths and quality transformations.

    Tracks pathways by water quality level (lowest to highest):
    - Graywater (GW): Lightly contaminated domestic wastewater
    - Non-potable (NP): Treated to non-drinking standards
    - Stormwater (SW): Collected urban runoff
    - Rainwater (RW): Direct precipitation collection
    - Potable (PO): Treated to drinking standards
    """
    # Graywater generation and use
    kitchen_to_graywater: Flow = field(
        default_factory=lambda: Flow(
            _process=None,
            _quality=WaterQuality.GRAYWATER,
            _use=WaterUse.DOMESTIC,
            _direction=FlowDirection.OUT,
            _volume_only=True
        ))

    bathroom_to_graywater: Flow = field(
        default_factory=lambda: Flow(
            _process=None,
            _quality=WaterQuality.GRAYWATER,
            _use=WaterUse.DOMESTIC,
            _direction=FlowDirection.OUT,
            _volume_only=True
        ))

    laundry_to_graywater: Flow = field(
        default_factory=lambda: Flow(
            _process=None,
            _quality=WaterQuality.GRAYWATER,
            _use=WaterUse.DOMESTIC,
            _direction=FlowDirection.OUT,
            _volume_only=True
        ))

    graywater_to_irrigation: Flow = field(
        default_factory=lambda: Flow(
            _process=None,
            _quality=WaterQuality.GRAYWATER,
            _use=WaterUse.IRRIGATION,
            _direction=FlowDirection.OUT,
            _volume_only=True
        ))
    graywater_to_wastewater: Flow = field(
        default_factory=lambda: Flow(
            _process=None,
            _quality=WaterQuality.GRAYWATER,
            _use=WaterUse.DOMESTIC,
            _direction=FlowDirection.OUT,
            _volume_only=True
        ))

    # Treated wastewater use
    wws_to_toilet: Flow = field(
        default_factory=lambda: Flow(
            _process=None,
            _quality=WaterQuality.TREATED,
            _use=WaterUse.DOMESTIC,
            _direction=FlowDirection.OUT,
            _volume_only=True
        ))

    wws_to_irrigation: Flow = field(
        default_factory=lambda: Flow(
            _process=None,
            _quality=WaterQuality.TREATED,
            _use=WaterUse.IRRIGATION,
            _direction=FlowDirection.OUT,
            _volume_only=True
        ))

    # Rainwater use
    rt_to_kitchen: Flow = field(
        default_factory=lambda: Flow(
            _process=None,
            _quality=WaterQuality.RAINWATER,
            _use=WaterUse.DOMESTIC,
            _direction=FlowDirection.OUT,
            _volume_only=True
        ))

    rt_to_bathroom: Flow = field(
        default_factory=lambda: Flow(
            _process=None,
            _quality=WaterQuality.RAINWATER,
            _use=WaterUse.DOMESTIC,
            _direction=FlowDirection.OUT,
            _volume_only=True
        ))

    rt_to_laundry: Flow = field(
        default_factory=lambda: Flow(
            _process=None,
            _quality=WaterQuality.RAINWATER,
            _use=WaterUse.DOMESTIC,
            _direction=FlowDirection.OUT,
            _volume_only=True
        ))

    rt_to_toilet: Flow = field(
        default_factory=lambda: Flow(
            _process=None,
            _quality=WaterQuality.RAINWATER,
            _use=WaterUse.DOMESTIC,
            _direction=FlowDirection.OUT,
            _volume_only=True
        ))

    rt_to_irrigation: Flow = field(
        default_factory=lambda: Flow(
            _process=None,
            _quality=WaterQuality.RAINWATER,
            _use=WaterUse.IRRIGATION,
            _direction=FlowDirection.OUT,
            _volume_only=True
        ))

    # Treated cluster wastewater use
    cwws_to_toilet: Flow = field(
        default_factory=lambda: Flow(
            _process=None,
            _quality=WaterQuality.TREATED,
            _use=WaterUse.DOMESTIC,
            _direction=FlowDirection.OUT,
            _volume_only=True
        ))

    cwws_to_irrigation: Flow = field(
        default_factory=lambda: Flow(
            _process=None,
            _quality=WaterQuality.TREATED,
            _use=WaterUse.IRRIGATION,
            _direction=FlowDirection.OUT,
            _volume_only=True
        ))

    cwws_to_publicir: Flow = field(
        default_factory=lambda: Flow(
            _process=None,
            _quality=WaterQuality.TREATED,
            _use=WaterUse.IRRIGATION,
            _direction=FlowDirection.OUT,
            _volume_only=True
        ))

    # Stormwater use
    sws_to_toilet: Flow = field(
        default_factory=lambda: Flow(
            _process=None,
            _quality=WaterQuality.STORMWATER,
            _use=WaterUse.DOMESTIC,
            _direction=FlowDirection.OUT,
            _volume_only=True
        ))

    sws_to_irrigation: Flow = field(
        default_factory=lambda: Flow(
            _process=None,
            _quality=WaterQuality.STORMWATER,
            _use=WaterUse.IRRIGATION,
            _direction=FlowDirection.OUT,
            _volume_only=True
        ))

    # Potable water use
    po_to_kitchen: Flow = field(
        default_factory=lambda: Flow(
            _process=None,
            _quality=WaterQuality.POTABLE,
            _use=WaterUse.DOMESTIC,
            _direction=FlowDirection.OUT,
            _volume_only=True
        ))

    po_to_bathroom: Flow = field(
        default_factory=lambda: Flow(
            _process=None,
            _quality=WaterQuality.POTABLE,
            _use=WaterUse.DOMESTIC,
            _direction=FlowDirection.OUT,
            _volume_only=True
        ))

    po_to_laundry: Flow = field(
        default_factory=lambda: Flow(
            _process=None,
            _quality=WaterQuality.POTABLE,
            _use=WaterUse.DOMESTIC,
            _direction=FlowDirection.OUT,
            _volume_only=True
        ))

    po_to_toilet: Flow = field(
        default_factory=lambda: Flow(
            _process=None,
            _quality=WaterQuality.POTABLE,
            _use=WaterUse.DOMESTIC,
            _direction=FlowDirection.OUT,
            _volume_only=True
        ))

    po_to_irrigation: Flow = field(
        default_factory=lambda: Flow(
            _process=None,
            _quality=WaterQuality.POTABLE,
            _use=WaterUse.IRRIGATION,
            _direction=FlowDirection.OUT,
            _volume_only=True
        ))
