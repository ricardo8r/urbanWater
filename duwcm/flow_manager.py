from dataclasses import dataclass, field
from typing import List, Union, Optional
from enum import Enum, auto, IntEnum

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

@dataclass
class Flow:
    """Base class for a flow"""
    _amount: float = field(default=0.0)
    _type: FlowType = field(default=None)
    _direction: FlowDirection = field(default=None)
    linked_flow: Optional['Flow'] = field(default=None, repr=False)

    @property
    def amount(self) -> float:
        """Get the flow amount"""
        return self._amount

    @amount.setter
    def amount(self, value: float) -> None:
        """Set the flow amount and sync with linked flow"""
        self._amount = value
        if self.linked_flow is not None:
            self.linked_flow.set_amount_no_sync(value)

    def set_amount_no_sync(self, value: float) -> None:
        """Internal method to set amount without triggering sync"""
        self._amount = value

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

    def link(self, other_flow: 'Flow') -> None:
        """Link this flow to another flow for automatic synchronization"""
        self.linked_flow = other_flow
        other_flow.linked_flow = self


@dataclass
class MultiSourceFlow:
    """Flow that can accumulate from multiple sources"""
    type: FlowType = None
    direction: FlowDirection = None
    _sources: List[Flow] = field(default_factory=list)
    _amounts: List[float] = field(default_factory=list)

    @property
    def amount(self) -> float:
        """Calculate total flow by summing all source amounts"""
        # Update amounts from sources before summing
        self._amounts = [source.amount for source in self._sources]
        return sum(self._amounts)

    def add_source(self, source: Union[Flow, float]):
        """
        Add a source amount. Can accept either a Flow object or a float value.
        """
        if isinstance(source, Flow):
            self._sources.append(source)
            self._amounts.append(source.amount)
        else:
            # For backwards compatibility
            self._amounts.append(float(source))

    def remove_source(self, source: Union[Flow, float]):
        """
        Remove a source amount if it exists.
        """
        if isinstance(source, Flow):
            if source in self._sources:
                self._sources.remove(source)
                self._amounts = [s.amount for s in self._sources]
        else:
            value = float(source)
            if value in self._amounts:
                self._amounts.remove(value)

    def reset_flows(self):
        """Reset flows - called during model updates"""
        # Only reset the amounts list, keep the sources
        self._amounts = [0.0] * len(self._sources)

@dataclass
class ComponentFlows:
    """Base class for all component flows"""
    def get_flow(self, name: str) -> float:
        """Get flow amount by name"""
        if not hasattr(self, name):
            return 0.0

        flow = getattr(self, name)
        return flow.amount

    def set_flow(self, name: str, value: float) -> None:
        """Set flow amount by name"""
        if not hasattr(self, name):
            raise ValueError(f"Invalid flow name: {name}")

        flow = getattr(self, name)
        if isinstance(flow, MultiSourceFlow):
            raise AttributeError(f"Cannot set amount directly for MultiSourceFlow '{name}'. \
                                 Use add_source/remove_source instead.")
        if isinstance(flow, Flow):
            flow.amount = value
        else:
            raise ValueError(f"Invalid flow type for {name}")

    def reset_flows(self) -> None:
        """Reset all flows to zero"""
        for flow in vars(self).values():
            if isinstance(flow, Flow):
                flow.amount = 0
            elif isinstance(flow, MultiSourceFlow):
                flow.reset_flows()

    def get_total_inflow(self) -> float:
        """Calculate total inflow"""
        return sum(self.get_flow(name)
                  for name, flow in vars(self).items()
                  if isinstance(flow, (Flow, MultiSourceFlow))
                  and flow.direction == FlowDirection.IN)

    def get_total_outflow(self) -> float:
        """Calculate total outflow"""
        return sum(self.get_flow(name)
                  for name, flow in vars(self).items()
                  if isinstance(flow, (Flow, MultiSourceFlow))
                  and flow.direction == FlowDirection.OUT)

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
