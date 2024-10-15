from dataclasses import dataclass, field
from typing import List

@dataclass
class RoofData:
    irrigation: float = field(default=0, metadata={'unit': 'mm'})
    evaporation: float = field(default=0, metadata={'unit': 'L'})
    effective_runoff: float = field(default=0, metadata={'unit': 'mm'})
    non_effective_runoff: float = field(default=0, metadata={'unit': 'mm'})
    storage: float = field(default=0, metadata={'unit': 'mm'})
    water_balance: float = field(default=0, metadata={'unit': 'L'})

@dataclass
class RainTankData:
    first_flush: float = field(default=0, metadata={'unit': 'L'})
    inflow: float = field(default=0, metadata={'unit': 'L'})
    overflow: float = field(default=0, metadata={'unit': 'L'})
    evaporation: float = field(default=0, metadata={'unit': 'L'})
    runoff_stormwater: float = field(default=0, metadata={'unit': 'L'})
    runoff_pavement: float = field(default=0, metadata={'unit': 'L'})
    system_outflow: float = field(default=0, metadata={'unit': 'L'})
    storage: float = field(default=0, metadata={'unit': 'L'})
    water_balance: float = field(default=0, metadata={'unit': 'L'})

@dataclass
class PondData:
    #inflow: float = field(default=0, metadata={'unit': 'mm'})
    evaporation: float = field(default=0, metadata={'unit': 'L'})
    infiltration: float = field(default=0, metadata={'unit': 'mm'})
    overflow: float = field(default=0, metadata={'unit': 'mm'})
    storage: float = field(default=0, metadata={'unit': 'mm'})
    water_balance: float = field(default=0, metadata={'unit': 'L'})

@dataclass
class PavementData:
    inflow: float = field(default=0, metadata={'unit': 'mm'})
    evaporation: float = field(default=0, metadata={'unit': 'L'})
    infiltration: float = field(default=0, metadata={'unit': 'mm'})
    effective_runoff: float = field(default=0, metadata={'unit': 'mm'})
    non_effective_runoff: float = field(default=0, metadata={'unit': 'mm'})
    storage: float = field(default=0, metadata={'unit': 'mm'})
    water_balance: float = field(default=0, metadata={'unit': 'L'})

@dataclass
class PerviousData:
    inflow: float = field(default=0, metadata={'unit': 'mm'})
    infiltration_capacity: float = field(default=0, metadata={'unit': 'mm'})
    time_factor: float = field(default=0, metadata={'unit': '-'})
    evaporation: float = field(default=0, metadata={'unit': 'L'})
    infiltration: float = field(default=0, metadata={'unit': 'mm'})
    overflow: float = field(default=0, metadata={'unit': 'mm'})
    storage: float = field(default=0, metadata={'unit': 'mm'})
    water_balance: float = field(default=0, metadata={'unit': 'L'})

@dataclass
class VadoseData:
    transpiration_threshold: float = field(default=0, metadata={'unit': 'mm'})
    transpiration_factor: float = field(default=0, metadata={'unit': '-'})
    transpiration: float = field(default=0, metadata={'unit': 'mm'})
    equilibrium_moisture: float = field(default=0, metadata={'unit': 'mm'})
    max_capillary: float = field(default=0, metadata={'unit': 'mm/d'})
    percolation: float = field(default=0, metadata={'unit': 'mm'})
    moisture: float = field(default=0, metadata={'unit': 'mm'})
    water_balance: float = field(default=0, metadata={'unit': 'L'})

@dataclass
class GroundwaterData:
    total_irrigation: float = field(default=0, metadata={'unit': 'L'})
    leakage: float = field(default=0, metadata={'unit': 'mm'})
    inflow: float = field(default=0, metadata={'unit': 'mm'})
    storage_coefficient: float = field(default=0, metadata={'unit': '-'})
    seepage: float = field(default=0, metadata={'unit': 'L'})
    baseflow: float = field(default=0, metadata={'unit': 'L'})
    pipe_infiltration: float = field(default=0, metadata={'unit': 'L'})
    water_level: float = field(default=0, metadata={'unit': 'm'})
    surface_water_level: float = field(default=0, metadata={'unit': 'm'})
    water_balance: float = field(default=0, metadata={'unit': 'L'})

@dataclass
class StormwaterData:
    total_runoff: float = field(default=0, metadata={'unit': 'L'})
    combined_sewer_inflow: float = field(default=0, metadata={'unit': 'L'})
    upstream_inflow: float = field(default=0, metadata={'unit': 'L'})
    runoff: float = field(default=0, metadata={'unit': 'L'})
    first_flush: float = field(default=0, metadata={'unit': 'L'})
    inflow: float = field(default=0, metadata={'unit': 'L'})
    evaporation: float = field(default=0, metadata={'unit': 'L'})
    overflow: float = field(default=0, metadata={'unit': 'L'})
    runoff_sewer: float = field(default=0, metadata={'unit': 'L'})
    storage: float = field(default=0, metadata={'unit': 'L'})
    water_balance: float = field(default=0, metadata={'unit': 'L'})

@dataclass
class WastewaterData:
    total_inflow: float = field(default=0, metadata={'unit': 'L'})
    discharge: float = field(default=0, metadata={'unit': 'L'})
    upstream_inflow: float = field(default=0, metadata={'unit': 'L'})
    storage: float = field(default=0, metadata={'unit': 'L'})
    water_balance: float = field(default=0, metadata={'unit': 'L'})

@dataclass
class ReuseData:
    ssg_demand: float = field(default=0, metadata={'unit': 'L'})
    ssg_use: float = field(default=0, metadata={'unit': 'L'})
    ssg_deficit: float = field(default=0, metadata={'unit': 'L'})
    ssg_spillover: float = field(default=0, metadata={'unit': 'L'})
    wws_demand: float = field(default=0, metadata={'unit': 'L'})
    wws_supply: float = field(default=0, metadata={'unit': 'L'})
    wws_use: float = field(default=0, metadata={'unit': 'L'})
    wws_deficit: float = field(default=0, metadata={'unit': 'L'})
    wws_spillover: float = field(default=0, metadata={'unit': 'L'})
    wws_storage: float = field(default=0, metadata={'unit': 'L'})
    wws_water_balance: float = field(default=0, metadata={'unit': 'L'})
    rt_demand: float = field(default=0, metadata={'unit': 'L'})
    rt_domestic_demand: float = field(default=0, metadata={'unit': 'L'})
    rt_toilet_demand: float = field(default=0, metadata={'unit': 'L'})
    rt_irrigation_demand: float = field(default=0, metadata={'unit': 'L'})
    rt_use: float = field(default=0, metadata={'unit': 'L'})
    rt_deficit: float = field(default=0, metadata={'unit': 'L'})
    rt_storage: float = field(default=0, metadata={'unit': 'L'})
    rt_water_balance: float = field(default=0, metadata={'unit': 'L'})
    rt_first_flush: float = field(default=0, metadata={'unit': 'L'})
    rt_inflow: float = field(default=0, metadata={'unit': 'L'})
    rt_overflow: float = field(default=0, metadata={'unit': 'L'})
    rt_evaporation: float = field(default=0, metadata={'unit': 'L'})
    imported_water: float = field(default=0, metadata={'unit': 'L'})

@dataclass
class UrbanWaterData:
    """
    Urban water model data for state variables. Default initialize to respective data classes
    """
    roof: RoofData = field(default_factory=RoofData)
    raintank: RainTankData = field(default_factory=RainTankData)
    pavement: PavementData = field(default_factory=PavementData)
    pervious: PerviousData = field(default_factory=PerviousData)
    vadose: VadoseData = field(default_factory=VadoseData)
    groundwater: GroundwaterData = field(default_factory=GroundwaterData)
    stormwater: StormwaterData = field(default_factory=StormwaterData)
    wastewater: WastewaterData = field(default_factory=WastewaterData)
    reuse: ReuseData = field(default_factory=ReuseData)


@dataclass
class Flow:
    source: str
    destination: str
    variable: str
    amount: float = 0
    unit: str = 'L'

@dataclass
class ComponentFlows:
    flows: List[Flow] = field(default_factory=list)

@dataclass
class RoofFlowsData(ComponentFlows):
    pass

@dataclass
class RainTankFlowsData(ComponentFlows):
    pass

@dataclass
class PavementFlowsData(ComponentFlows):
    pass

@dataclass
class PerviousFlowsData(ComponentFlows):
    pass

@dataclass
class VadoseFlowsData(ComponentFlows):
    pass

@dataclass
class GroundwaterFlowsData(ComponentFlows):
    pass

@dataclass
class StormwaterFlowsData(ComponentFlows):
    pass

@dataclass
class WastewaterFlowsData(ComponentFlows):
    pass

@dataclass
class ReuseFlowsData(ComponentFlows):
    pass

@dataclass
class UrbanWaterFlowsData:
    """
    Urban water model data for flow tracking
    """
    roof: ComponentFlows = field(default_factory=ComponentFlows)
    raintank: ComponentFlows = field(default_factory=ComponentFlows)
    pavement: ComponentFlows = field(default_factory=ComponentFlows)
    pervious: ComponentFlows = field(default_factory=ComponentFlows)
    vadose: ComponentFlows = field(default_factory=ComponentFlows)
    groundwater: ComponentFlows = field(default_factory=ComponentFlows)
    stormwater: ComponentFlows = field(default_factory=ComponentFlows)
    wastewater: ComponentFlows = field(default_factory=ComponentFlows)
    reuse: ComponentFlows = field(default_factory=ComponentFlows)