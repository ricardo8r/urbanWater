from typing import Dict, Any, Tuple
from dataclasses import dataclass
import pandas as pd
from duwcm.data_structures import UrbanWaterData, ReuseData, ReuseFlowsData, Flow

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

class ReuseClass:
    """
    Simulates the supply, demand, use, and deficit of SSG, WWS, and rain tank.
    Updates the water level and water balance of rain tank.
    """
    def __init__(self, params: Dict[str, Dict[str, Any]], demand: pd.Series, setreuse: pd.DataFrame):
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
        raintank_total_ratio = params['general']['number_houses'] * params['raintank']['install_ratio'] / 100
        self.raintank_capacity = params['raintank']['capacity'] * raintank_total_ratio

        self.roof_area = params['roof']['area']
        self.pavement_area = params['pavement']['area']
        self.pervious_area = params['pervious']['area']
        self.groundwater_area = params['groundwater']['area']
        self.wastewater_area = params['reuse']['area'] * params['general']['number_houses']
        self.wastewater_capacity = params['reuse']['capacity'] * params['general']['number_houses']
        self.indoor_water_use = params['general']['indoor_water_use']

        self.irrigation_factor = params['irrigation']['pervious']
        self.demand = demand * self.indoor_water_use / 100
        self.setreuse = setreuse
        self._initialize_demands()


    def _initialize_demands(self):
        """
        ssg_suply: Subsurface graywater irrigation suply [L]:
        raintank_suply: Max supply from rain tank [L]
        """
        self.ssg_supply = (self.setreuse.KforSSG * self.demand['K'].values[0] +
                           self.setreuse.BforSSG * self.demand['B'].values[0] +
                           self.setreuse.LforSSG * self.demand['L'].values[0])

        self.raintank_supply = (self.setreuse.RTforK * self.demand['K'].values[0] +
                                 self.setreuse.RTforB * self.demand['B'].values[0] +
                                 self.setreuse.RTforL * self.demand['L'].values[0])

        self.kitchen_demand = self.demand['K'].values[0]
        self.bathroom_demand = self.demand['B'].values[0]
        self.laundry_demand = self.demand['L'].values[0]
        self.toilet_demand = self.demand['T'].values[0]

    def solve(self, forcing: pd.Series, previous_state: UrbanWaterData,
              current_state: UrbanWaterData) -> Tuple[ReuseData, ReuseFlowsData]:
        """
        Args:
            forcing (pd.DataFrame): Climate forcing data with columns:
                roof_irrigation: Irrigation demand on roof surface [mm]
                pavement_irrigation: Irrigation demand on pavement surface [mm]
                pervious_irrigation: Irrigation demand on pervious surface [mm]
            previous_state (pd.DataFrame): State variables from the previous time step with columns:
                Reuse:
                    previous_storage: Initial storage at the current time step (t) [L]
            current_state (pd.DataFrame): Current state variables with columns:
                Rain tank:
                    raintank_storage: Rain tank amount in this time step from the RainTank object [L]
                    raintank_balance: Water balance check of RT (from RainTank object) [L]
                Groundwater:
                    leakage: Leakage rate [mm]

        Returns:
            Dict[str, float]: Water balance components for the current time step:
                sgs_results: Subsurface graywater balance
                wws_results: Wastewater storage balance
                rt_results: Rain tank balance
                imported_water: Required imported water [L] 
        """
        roof_irrigation = forcing.get('roof_irrigation', 0.0)
        pavement_irrigation = forcing.get('pavement_irrigation', 0.0)
        pervious_irrigation = forcing.get('pervious_irrigation', 0.0) * self.irrigation_factor

        previous_storage = previous_state.reuse.wws_storage

        raintank_storage = current_state.raintank.storage
        raintank_balance = current_state.raintank.water_balance
        leakage = current_state.groundwater.leakage

        total_irrigation = (roof_irrigation * self.roof_area +
                            pavement_irrigation * self.pavement_area +
                            pervious_irrigation * self.pervious_area)

        ssg_irrigation, ssg_results = self._calculate_ssg(total_irrigation)
        wws_irrigation, wws_toilet, wws_results = self._calculate_wws(ssg_results, ssg_irrigation, previous_storage)
        rt_results = self._calculate_raintank(raintank_balance, raintank_storage, wws_toilet, wws_irrigation)

        imported_water = (rt_results.domestic_demand + rt_results.toilet_demand +
                          rt_results.irrigation_demand + leakage * self.groundwater_area)

        reuse_data = ReuseData(
            ssg_demand=ssg_results.demand,
            ssg_use=ssg_results.use,
            ssg_deficit=ssg_results.deficit,
            ssg_spillover=ssg_results.spillover,

            wws_demand=wws_results.demand,
            wws_supply=wws_results.supply,
            wws_use=wws_results.use,
            wws_deficit=wws_results.deficit,
            wws_spillover=wws_results.spillover,
            wws_storage=wws_results.storage,
            wws_water_balance=wws_results.water_balance,

            rt_demand=rt_results.demand,
            rt_domestic_demand=rt_results.domestic_demand,
            rt_toilet_demand=rt_results.toilet_demand,
            rt_irrigation_demand=rt_results.irrigation_demand,
            rt_use=rt_results.use,
            rt_deficit=rt_results.deficit,
            rt_storage=rt_results.storage,
            rt_water_balance=rt_results.water_balance,

            imported_water=imported_water
        )

        reuse_flows = ReuseFlowsData(flows=[
            Flow(
                source="external",
                destination="reuse",
                variable="imported_water",
                amount=imported_water,
                unit="L"
            )
        ])

        return reuse_data, reuse_flows

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

    def _calculate_raintank(self, raintank_balance: float, raintank_storage: float,
                            wws_toilet: float, wws_irrigation: float) -> RainTankData:
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
                water_balance = raintank_balance,
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
                water_balance = raintank_balance,
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

        water_balance = raintank_balance - use + (raintank_storage - final_storage)

        return RainTankData(
            demand = demand,
            use = use,
            storage = final_storage,
            deficit = deficit,
            domestic_demand = domestic_demand,
            toilet_demand = toilet_demand,
            irrigation_demand = irrigation_demand,
            water_balance = water_balance,
            check = check
        )

    def _raintank_use(self, use: float, wws_toilet: float, wws_irrigation: float) -> Tuple[float, float]:
        if self.setreuse.RTforT == 0:
            return wws_toilet, wws_irrigation - max(use - self.raintank_supply, 0)

        toilet_demand = wws_toilet - min(max(use - self.raintank_supply, 0), wws_toilet)
        irrigation_demand = wws_irrigation - max(use - self.raintank_supply - wws_toilet, 0)
        return toilet_demand, irrigation_demand