from dataclasses import dataclass, field

@dataclass
class RoofData:
    evaporation: float = 0
    effective_runoff: float = 0
    non_effective_runoff: float = 0
    storage: float = 0
    water_balance: float = 0

@dataclass
class RainTankData:
    first_flush: float = 0
    inflow: float = 0
    overflow: float = 0
    evaporation: float = 0
    runoff_sewer: float = 0
    runoff_pavement: float = 0
    system_outflow: float = 0
    storage: float = 0
    water_balance: float = 0

@dataclass
class PavementData:
    inflow: float = 0
    evaporation: float = 0
    infiltration: float = 0
    effective_runoff: float = 0
    non_effective_runoff: float = 0
    storage: float = 0
    water_balance: float = 0

@dataclass
class PerviousData:
    inflow: float = 0
    infiltration_capacity: float = 0
    time_factor: float = 0
    evaporation: float = 0
    infiltration: float = 0
    overflow: float = 0
    storage: float = 0
    water_balance: float = 0

@dataclass
class VadoseData:
    transpiration_threshold: float = 0
    transpiration_factor: float = 0
    transpiration: float = 0
    equilibrium_moisture: float = 0
    max_capillary: float = 0
    percolation: float = 0
    moisture: float = 0
    water_balance: float = 0

@dataclass
class GroundwaterData:
    total_irrigation: float = 0
    leakage_depth: float = 0
    inflow: float = 0
    storage_coefficient: float = 0
    seepage: float = 0
    baseflow: float = 0
    pipe_infiltration: float = 0
    water_level: float = 0
    water_balance: float = 0

@dataclass
class StormwaterData:
    total_runoff: float = 0
    wastewater_inflow: float = 0
    upstream_inflow: float = 0
    stormwater_runoff: float = 0
    first_flush: float = 0
    inflow: float = 0
    evaporation: float = 0
    overflow: float = 0
    sewer_inflow: float = 0
    storage: float = 0
    water_balance: float = 0
    use: float = 0
    supply: float = 0

@dataclass
class WastewaterData:
    total_inflow: float = 0
    sewer_inflow: float = 0
    upstream_inflow: float = 0
    storage: float = 0
    water_balance: float = 0
    use: float = 0
    supply: float = 0

@dataclass
class ReuseData:
    ssg_demand: float = 0
    ssg_use: float = 0
    ssg_deficit: float = 0
    ssg_spillover: float = 0
    wws_demand: float = 0
    wws_supply: float = 0
    wws_use: float = 0
    wws_deficit: float = 0
    wws_spillover: float = 0
    wws_storage: float = 0
    wws_water_balance: float = 0
    rt_demand: float = 0
    rt_domestic_demand: float = 0
    rt_toilet_demand: float = 0
    rt_irrigation_demand: float = 0
    rt_use: float = 0
    rt_deficit: float = 0
    rt_storage: float = 0
    rt_water_balance: float = 0
    rt_first_flush: float = 0
    rt_inflow: float = 0
    rt_overflow: float = 0
    rt_evaporation: float = 0
    imported_water: float = 0

@dataclass
class UrbanWaterData:
    """
    Urban water model data. Default initialize to respective data classes
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