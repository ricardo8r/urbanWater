from typing import Dict, Any, Tuple
from dataclasses import dataclass
import pandas as pd
from duwcm.data_structures import DemandData

# Constants
TO_METERS = 0.001

@dataclass
class GraywaterData:
    """
    Data variables for subsurface graywater.
    """
    demand: float = 0
    use: float = 0
    deficit: float = 0
    spillover: float = 0
    check: bool = False

@dataclass
class WastewaterData:
    """
    Data variables for wastewater.
    """
    demand: float = 0
    supply: float = 0
    use: float = 0
    deficit: float = 0
    spillover: float = 0
    storage: float = 0
    water_balance: float = 0
    check: bool = False

@dataclass
class RainTankData:
    """
    Data variables for rain tank.
    """
    demand: float = 0
    domestic_demand: float = 0
    toilet_demand: float = 0
    irrigation_demand: float = 0
    use: float = 0
    deficit: float = 0
    storage: float = 0
    water_balance: float = 0
    check: bool = False

class DemandClass:
    """
    Simulates the supply, demand, use, and deficit of SSG, WWS, and rain tank.
    Updates the water level and water balance of rain tank.
    """
    def __init__(self, params: Dict[str, Dict[str, Any]], demand_settings: pd.Series,
                 reuse_settings: pd.DataFrame, demand_data: DemandData):
        """
        Args:
            params (Dict[str, float]): System parameters
                number_houses: Number of houses in this cell
                wastewater_area: Area of onsite wastewater storage [m2]
                wastewater_capacity: Onsite wastewater storage capacity [L]
                wastewater_intial_storage: Initial storage of onsite wastewater [L]
                indoor_water_use: Daily indoor water use
            demand: Water demand of different indoor water use per block [L/day/block]
            setreuse: Setting of the supply and use priority (boolean)
        """
        self.demand_data = demand_data

        # Initialize wastewater storage parameters
        self.demand_data.area = params['reuse']['area'] * params['general']['number_houses']
        self.demand_data.flows.set_areas(self.demand_data.area)
        self.wastewater_capacity = params['reuse']['capacity'] * params['general']['number_houses']

        # Initialize other parameters
        raintank_total_ratio = params['general']['number_houses'] * params['raintank']['install_ratio'] / 100
        self.raintank_capacity = params['raintank']['capacity'] * raintank_total_ratio
        self.indoor_water_use = params['general']['indoor_water_use']
        self.leakage_rate = params['groundwater']['leakage_rate'] / 100
        self.irrigation_factor = params['irrigation']['pervious']

        # Initialize demand patterns
        self.setdemand = demand_settings * self.indoor_water_use / 100
        self.setreuse = reuse_settings
        self._initialize_demands()

    def _initialize_demands(self):
        """
        ssg_suply: Subsurface graywater irrigation suply [L]:
        raintank_suply: Max supply from rain tank [L]
        """
        self.ssg_supply = (self.setreuse.KforSSG * self.setdemand['K'].values[0] +
                           self.setreuse.BforSSG * self.setdemand['B'].values[0] +
                           self.setreuse.LforSSG * self.setdemand['L'].values[0])

        self.raintank_supply = (self.setreuse.RTforK * self.setdemand['K'].values[0] +
                                 self.setreuse.RTforB * self.setdemand['B'].values[0] +
                                 self.setreuse.RTforL * self.setdemand['L'].values[0])

        self.kitchen_demand = self.setdemand['K'].values[0]
        self.bathroom_demand = self.setdemand['B'].values[0]
        self.laundry_demand = self.setdemand['L'].values[0]
        self.toilet_demand = self.setdemand['T'].values[0]

    def solve(self, forcing: pd.Series) -> None:
        """
        Args:
           forcing (pd.DataFrame): Climate forcing data with columns:
                roof_irrigation: Irrigation demand on roof surface [mm]
                pavement_irrigation: Irrigation demand on pavement surface [mm]
                pervious_irrigation: Irrigation demand on pervious surface [mm]

        Returns:
            Dict[str, float]: Water balance components for the current time step:
                sgs_results: Subsurface graywater balance
                wws_results: Wastewater storage balance
                rt_results: Rain tank balance
                imported_water: Required imported water [L] 
        """
        data = self.demand_data

        roof_irrigation = data.flows.get_flow('to_roof', 'L')
        pavement_irrigation = data.flows.get_flow('to_pavement', 'L')
        pervious_irrigation = data.flows.get_flow('to_pervious', 'L')
        indoor_use_leakage = data.flows.get_flow('to_groundwater', 'L')
        total_irrigation = roof_irrigation + pavement_irrigation + pervious_irrigation

        # Use class's internal calculation methods
        ssg_irrigation, ssg_results = self._calculate_ssg(total_irrigation)
        wws_irrigation, wws_toilet, wws_results = self._calculate_wws(ssg_results, ssg_irrigation,
                                                                      data.wws_storage)
        rt_results = self._calculate_raintank(data.rt_storage.get_amount('L'), wws_toilet, wws_irrigation)

        imported_water = (rt_results.domestic_demand + rt_results.toilet_demand +
                         rt_results.irrigation_demand + indoor_use_leakage)

        # Update ReuseData state
        data.rt_storage.set_amount(rt_results.storage, 'L')
        data.rt_water_balance = rt_results.water_balance
        data.wws_storage = wws_results.storage
        data.rt_domestic_demand = rt_results.domestic_demand
        data.rt_toilet_demand = rt_results.toilet_demand
        data.rt_irrigation_demand = rt_results.irrigation_demand

        # Update flows
        data.flows.set_flow('imported_water', imported_water, 'L')
        data.flows.set_flow('to_wastewater', wws_results.spillover, 'L')

    def _calculate_ssg(self, total_irrigation: float) -> (float, GraywaterData):
        """
        Calculate the subsurface greywater irrigation
        """
        if self.ssg_supply == 0:
            ssg_result = GraywaterData(
                demand = 0,
                spillover = 0,
                use = 0,
                deficit = 0,
                check = True
            )
            irrigation_demand = total_irrigation
            return irrigation_demand, ssg_result

        use = min(self.ssg_supply, total_irrigation)
        spillover = max(0, self.ssg_supply - use)
        deficit = max(total_irrigation - use, 0)
        irrigation_demand = deficit

        ssg_result = GraywaterData(
            demand = total_irrigation,
            spillover = spillover,
            use = use,
            deficit = deficit,
            check = total_irrigation - irrigation_demand == use
        )
        return irrigation_demand, ssg_result

    def _calculate_wws(self, ssg_results: Dict[str, float], ssg_irrigation: float,
                       previous_storage: float) -> WastewaterData:
        """
        Calculate the wastewater treatment and storage 
        """
        inflow = (self.toilet_demand + ssg_results.spillover +
                  ((1 - self.setreuse.KforSSG) * self.kitchen_demand +
                   (1 - self.setreuse.BforSSG) * self.bathroom_demand +
                   (1 - self.setreuse.LforSSG) * self.laundry_demand))

        if self.wastewater_capacity == 0:
            irrigation_demand = ssg_irrigation
            toilet_demand = self.toilet_demand
            wws_result = WastewaterData(
                demand = 0.0,
                supply = 0.0,
                use = 0.0,
                deficit = 0.0,
                spillover = inflow,
                storage = 0.0,
                water_balance = 0.0,
                check = True
            )
            return irrigation_demand, toilet_demand, wws_result

        demand = (self.toilet_demand * self.setreuse.WWSforT +
                  ssg_irrigation * self.setreuse.WWSforIR)

        if demand == 0:
            wws_result = WastewaterData(
                demand = 0,
                supply = 0,
                use = 0,
                deficit = 0,
                spillover = max(previous_storage - self.wastewater_capacity, 0.0),
                storage = min(previous_storage, self.wastewater_capacity),
                water_balance = 0,
                check = True
            )
            irrigation_demand = ssg_irrigation
            toilet_demand = self.toilet_demand
            return irrigation_demand, toilet_demand, wws_result

        initial_storage = min(previous_storage + inflow, self.wastewater_capacity)
        use = min(initial_storage, demand)
        final_storage = initial_storage - use
        deficit = max(demand - use, 0)
        spillover = max(previous_storage + inflow - self.wastewater_capacity, 0)
        water_balance = inflow - (spillover + use) - (final_storage - previous_storage)

        toilet_demand, irrigation_demand = self._wastewater_reuse(use, ssg_irrigation)

        wws_result = WastewaterData(
            demand = demand,
            supply = inflow,
            use = use,
            deficit = deficit,
            spillover = spillover,
            storage = final_storage,
            water_balance = water_balance,
            check = (self.toilet_demand - toilet_demand) + (ssg_irrigation - irrigation_demand) == use
        )
        return irrigation_demand, toilet_demand, wws_result

    def _wastewater_reuse(self, use: float, irrigation_demand: float) -> Tuple[float, float]:
        if self.setreuse.WWSforT == 0 and self.setreuse.WWSforIR != 0:
            return self.toilet_demand, irrigation_demand - use
        if self.setreuse.WWSforT != 0 and self.setreuse.WWSforIR == 0:
            return self.toilet_demand - use, irrigation_demand
        if use < self.toilet_demand:
            return self.toilet_demand - use, irrigation_demand
        return 0, irrigation_demand - use + self.toilet_demand

    def _calculate_raintank(self, raintank_storage: float, wws_toilet: float,
                            wws_irrigation: float) -> RainTankData:
        """
        Calculate rain tank reuse 
        """
        if self.raintank_capacity == 0:
            return RainTankData(
                demand = 0.0,
                use = 0.0,
                storage = raintank_storage,
                deficit = 0.0,
                domestic_demand = self.kitchen_demand + self.bathroom_demand + self.laundry_demand,
                toilet_demand = wws_toilet,
                irrigation_demand = wws_irrigation,
                check = True
            )

        demand = (self.raintank_supply + wws_toilet * self.setreuse.RTforT +
                  wws_irrigation * self.setreuse.RTforIR)

        if demand == 0:
            return RainTankData(
                demand = 0.0,
                use = 0.0,
                storage = raintank_storage,
                deficit = 0.0,
                domestic_demand = self.kitchen_demand + self.bathroom_demand + self.laundry_demand,
                toilet_demand = wws_toilet,
                irrigation_demand = wws_irrigation,
                check = True
            )

        use = min(raintank_storage, demand)
        final_storage = raintank_storage - use
        deficit = max(demand - use, 0)

        domestic_demand = (self.kitchen_demand + self.bathroom_demand + self.laundry_demand -
                           min(self.raintank_supply, use))
        toilet_demand, irrigation_demand = self._raintank_use(use, wws_toilet, wws_irrigation)

        check = ((self.kitchen_demand + self.bathroom_demand + self.laundry_demand - domestic_demand) +
                 (toilet_demand - wws_toilet) + (irrigation_demand - wws_irrigation)) == use


        return RainTankData(
            demand = demand,
            use = use,
            storage = final_storage,
            deficit = deficit,
            domestic_demand = domestic_demand,
            toilet_demand = toilet_demand,
            irrigation_demand = irrigation_demand,
            check = check
        )

    def _raintank_use(self, use: float, wws_toilet: float, wws_irrigation: float) -> Tuple[float, float]:
        if self.setreuse.RTforT == 0:
            return wws_toilet, wws_irrigation - max(use - self.raintank_supply, 0)

        toilet_demand = wws_toilet - min(max(use - self.raintank_supply, 0), wws_toilet)
        irrigation_demand = wws_irrigation - max(use - self.raintank_supply - wws_toilet, 0)
        return toilet_demand, irrigation_demand