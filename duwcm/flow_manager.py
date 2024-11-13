from dataclasses import dataclass, field
from typing import List, Union
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
    amount: float = 0.0
    type: FlowType = None
    direction: FlowDirection = None

    def get_flow(self):
        """Get the flow amount"""
        return self.amount

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

    def get_flow(self) -> float:
        """Get the flow amount"""
        return self.amount

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
        # Handle both regular Flow and MultiSourceFlow
        if isinstance(flow, (Flow, MultiSourceFlow)):
            return flow.get_flow()
        return 0.0

    def set_flow(self, name: str, amount: float) -> None:
        """Set flow amount by name"""
        if not hasattr(self, name):
            raise ValueError(f"Invalid flow name: {name}")

        flow = getattr(self, name)
        if isinstance(flow, MultiSourceFlow):
            raise AttributeError(f"Cannot set amount directly for MultiSourceFlow '{name}'. Use add_source/remove_source instead.")
        if isinstance(flow, Flow):
            flow.amount = amount
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
        default_factory=lambda: Flow(type=FlowType.PRECIPITATION, direction=FlowDirection.IN))
    irrigation: Flow = field(
        default_factory=lambda: Flow(type=FlowType.IRRIGATION, direction=FlowDirection.IN))
    evaporation: Flow = field(
        default_factory=lambda: Flow(type=FlowType.EVAPORATION, direction=FlowDirection.OUT))
    # Component flows
    to_raintank: Flow = field(
        default_factory=lambda: Flow(type=FlowType.RUNOFF, direction=FlowDirection.OUT))
    to_pervious: Flow = field(
        default_factory=lambda: Flow(type=FlowType.RUNOFF, direction=FlowDirection.OUT))
    to_groundwater: Flow = field(
        default_factory=lambda: Flow(type=FlowType.LEAKAGE, direction=FlowDirection.OUT))

@dataclass
class RainTankFlows(ComponentFlows):
    """Raintank component flows"""
    # Environmental flows
    precipitation: Flow = field(
        default_factory=lambda: Flow(type=FlowType.PRECIPITATION, direction=FlowDirection.IN))
    evaporation: Flow = field(
        default_factory=lambda: Flow(type=FlowType.EVAPORATION, direction=FlowDirection.OUT))
    # Component flows
    from_roof: Flow = field(
        default_factory=lambda: Flow(type=FlowType.RUNOFF, direction=FlowDirection.IN))
    to_pavement: Flow = field(
        default_factory=lambda: Flow(type=FlowType.RUNOFF, direction=FlowDirection.OUT))
    to_stormwater: Flow = field(
        default_factory=lambda: Flow(type=FlowType.RUNOFF, direction=FlowDirection.OUT))

@dataclass
class PavementFlows(ComponentFlows):
    """Pavement component flows"""
    # Environmental flows
    precipitation: Flow = field(
        default_factory=lambda: Flow(type=FlowType.PRECIPITATION, direction=FlowDirection.IN))
    irrigation: Flow = field(
        default_factory=lambda: Flow(type=FlowType.IRRIGATION, direction=FlowDirection.IN))
    evaporation: Flow = field(
        default_factory=lambda: Flow(type=FlowType.EVAPORATION, direction=FlowDirection.OUT))
    # Component flows
    from_raintank: Flow = field(
        default_factory=lambda: Flow(type=FlowType.RUNOFF, direction=FlowDirection.IN))
    to_pervious: Flow = field(
        default_factory=lambda: Flow(type=FlowType.RUNOFF, direction=FlowDirection.OUT))
    to_groundwater_infiltration: Flow = field(
        default_factory=lambda: Flow(type=FlowType.INFILTRATION, direction=FlowDirection.OUT))
    to_groundwater_leakage: Flow = field(
        default_factory=lambda: Flow(type=FlowType.LEAKAGE, direction=FlowDirection.OUT))
    to_stormwater: Flow = field(
        default_factory=lambda: Flow(type=FlowType.RUNOFF, direction=FlowDirection.OUT))

@dataclass
class PerviousFlows(ComponentFlows):
    """Pervious flows"""
    # Environmental flows
    precipitation: Flow = field(
        default_factory=lambda: Flow(type=FlowType.PRECIPITATION, direction=FlowDirection.IN))
    irrigation: Flow = field(
        default_factory=lambda: Flow(type=FlowType.IRRIGATION, direction=FlowDirection.IN))
    evaporation: Flow = field(
        default_factory=lambda: Flow(type=FlowType.EVAPORATION, direction=FlowDirection.OUT))
    # Component flows
    from_roof: Flow = field(
        default_factory=lambda: Flow(type=FlowType.RUNOFF, direction=FlowDirection.IN))
    from_pavement: Flow = field(
        default_factory=lambda: Flow(type=FlowType.RUNOFF, direction=FlowDirection.IN))
    to_vadose: Flow = field(
        default_factory=lambda: Flow(type=FlowType.INFILTRATION, direction=FlowDirection.OUT))
    to_groundwater: Flow = field(
        default_factory=lambda: Flow(type=FlowType.LEAKAGE, direction=FlowDirection.OUT))
    to_stormwater: Flow = field(
        default_factory=lambda: Flow(type=FlowType.RUNOFF, direction=FlowDirection.OUT))

@dataclass
class VadoseFlows(ComponentFlows):
    """Vadose zone flows"""
    # Environmental flows
    transpiration: Flow = field(
        default_factory=lambda: Flow(type=FlowType.TRANSPIRATION, direction=FlowDirection.OUT))
    # Component flows
    from_pervious: Flow = field(
        default_factory=lambda: Flow(type=FlowType.INFILTRATION, direction=FlowDirection.IN))
    to_groundwater: Flow = field(
        default_factory=lambda: Flow(type=FlowType.PERCOLATION, direction=FlowDirection.OUT))

@dataclass
class GroundwaterFlows(ComponentFlows):
    """Groundwater flows"""
    # Environmental flows
    seepage: Flow = field(
        default_factory=lambda: Flow(type=FlowType.SEEPAGE, direction=FlowDirection.OUT))
    baseflow: Flow = field(
        default_factory=lambda: Flow(type=FlowType.BASEFLOW, direction=FlowDirection.OUT))
    # Component flows
    from_roof: Flow = field(
        default_factory=lambda: Flow(type=FlowType.LEAKAGE, direction=FlowDirection.IN))
    from_pavement_infiltration: Flow = field(
        default_factory=lambda: Flow(type=FlowType.INFILTRATION, direction=FlowDirection.IN))
    from_pavement_leakage: Flow = field(
        default_factory=lambda: Flow(type=FlowType.LEAKAGE, direction=FlowDirection.IN))
    from_pervious: Flow = field(
        default_factory=lambda: Flow(type=FlowType.LEAKAGE, direction=FlowDirection.IN))
    from_vadose: Flow = field(
        default_factory=lambda: Flow(type=FlowType.PERCOLATION, direction=FlowDirection.IN))
    to_wastewater: Flow = field(
        default_factory=lambda: Flow(type=FlowType.INFILTRATION, direction=FlowDirection.OUT))

@dataclass
class StormwaterFlows(ComponentFlows):
    """Stormwater flows"""
    # Environmental flows
    precipitation: Flow = field(
        default_factory=lambda: Flow(type=FlowType.PRECIPITATION, direction=FlowDirection.IN))
    evaporation: Flow = field(
        default_factory=lambda: Flow(type=FlowType.EVAPORATION, direction=FlowDirection.OUT))
    # Component flows
    from_raintank: Flow = field(
        default_factory=lambda: Flow(type=FlowType.RUNOFF, direction=FlowDirection.IN))
    from_pavement: Flow = field(
        default_factory=lambda: Flow(type=FlowType.RUNOFF, direction=FlowDirection.IN))
    from_pervious: Flow = field(
        default_factory=lambda: Flow(type=FlowType.RUNOFF, direction=FlowDirection.IN))
    from_upstream: MultiSourceFlow = field(
        default_factory=lambda: MultiSourceFlow(type=FlowType.RUNOFF, direction=FlowDirection.IN))
    to_downstream: Flow = field(
        default_factory=lambda: Flow(type=FlowType.RUNOFF, direction=FlowDirection.OUT))
    to_wastewater: Flow = field(
        default_factory=lambda: Flow(type=FlowType.WASTEWATER, direction=FlowDirection.OUT))

@dataclass
class WastewaterFlows(ComponentFlows):
    """Wastewater flows"""
    # Component flows
    from_groundwater: Flow = field(
        default_factory=lambda: Flow(type=FlowType.INFILTRATION, direction=FlowDirection.IN))
    from_stormwater: Flow = field(
        default_factory=lambda: Flow(type=FlowType.WASTEWATER, direction=FlowDirection.IN))
    from_demand: Flow = field(
        default_factory=lambda: Flow(type=FlowType.WASTEWATER, direction=FlowDirection.IN))
    from_upstream: MultiSourceFlow = field(
        default_factory=lambda: MultiSourceFlow(type=FlowType.WASTEWATER, direction=FlowDirection.IN))
    to_downstream: Flow = field(
        default_factory=lambda: Flow(type=FlowType.WASTEWATER, direction=FlowDirection.OUT))

@dataclass
class DemandFlows(ComponentFlows):
    """Demand water flows"""
    # Environmental flows
    imported_water: Flow = field(
        default_factory=lambda: Flow(type=FlowType.IMPORTED_WATER, direction=FlowDirection.IN))
    # Component flows
    to_wastewater: Flow = field(
        default_factory=lambda: Flow(type=FlowType.WASTEWATER, direction=FlowDirection.OUT))
