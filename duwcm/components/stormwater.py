from typing import Dict, Any
import pandas as pd
from duwcm.data_structures import UrbanWaterData, StormwaterData

class StormwaterClass:
    """
    Simulates storm water storage dynamics.

    Inflows: Precipitation, raintank runoff, pavement runoff, pervious runoff, upstream inflow
    Outflows: Flush, overflow, evaporation, wastewater inflow
    """
    def __init__(self, params: Dict[str, Dict[str, Any]]):
        """
        Args:
            params (Dict[str, Dict[str, Any]]): Stormwater storage parameters
                pavement_area: Area of pavement [m^2]
                pervious_area: Area of pervious surface [m^2]
                is_open: is the stormwater storage open for precipitation and evaporation
                area: Area of stormwater storage [m^2]
                capacity: Stormwater storage capacity [L]
                first_flush: Predefined first flush of stormwater storage [L]
                wastewater_runoff_ratio: Percentage of runoff that becomes inflow to wastewater system [%]
        """
        self.pavement_area = params['pavement']['area']
        self.pervious_area = params['pervious']['area']
        self.is_open = params['stormwater']['is_open']
        self.area = params['stormwater']['area']
        self.capacity = params['stormwater']['capacity']
        self.first_flush = params['stormwater']['first_flush']
        self.wastewater_runoff_ratio = params['stormwater']['wastewater_runoff_per'] / 100

    def solve(self, forcing: pd.Series, previous_state: UrbanWaterData,
              current_state: UrbanWaterData) -> StormwaterData:
        """
        Args:
            forcing (pd.DataFrame): Climate forcing data with columns:
                precipitation: Precipitation of the time step [mm]
                potential_evaporation: Potential evaporation of the time step [mm]
            previous_state (pd.DataFrame): State variables from the previous time step with columns:
                Stormwater:
                    intial_storage: Stormwater storage volume [L]
                    upstream_inflow: Stormwater and wastewater flow from upstream grid [L] (default: 0)
            current_state (pd.DataFrame): Current state variables with columns:
                Raintank:
                    raintank_runoff: Outflow from roof-rain tank system [L]
                Pavement:
                    pavement_runoff: Effective impervious surface runoff from pavement area [mm]
                Pervious:
                    pervious_overflow: Overflow from pervious area interception [mm]

        Returns:
            Dict[str, float]: Computed states and fluxes of storm water storage during current time step
                total_runoff: Total runoff [L]
                wastewater_inflow: Inflow of storm water to wastewater sewer system [L]
                runoff: Runoff to storm water system [L]
                first_flush: Actual first flush [L]
                inflow: Inflow to SWS, RUN - first flush + Precipitation if SWSop=1 [L]
                initial_storage: Storage volume in the beginning of the time step [L]
                evaporation: Evaporation volume if SWSop=1 [L]
                final_storage: SWS storage at the end of the time step [L]
                overflow: Overflow from SWS [L]
                sewer_inflow: Storm water sewer system inflow [L]
                water_balance: Water balance of SWS [L]
        """
        precipitation = forcing.get('precipitation', 0.0)
        potential_evaporation = forcing.get('potential_evaporation', 0.0)

        initial_storage = previous_state.stormwater.storage
        upstream_inflow = current_state.stormwater.upstream_inflow
        raintank_runoff = current_state.raintank.runoff_sewer
        pavement_runoff = current_state.pavement.effective_runoff
        pervious_overflow = current_state.pervious.overflow

        total_runoff = (raintank_runoff + pavement_runoff * self.pavement_area +
                        pervious_overflow * self.pervious_area + upstream_inflow)
        wastewater_inflow = self.wastewater_runoff_ratio * total_runoff
        runoff = total_runoff - wastewater_inflow

        if self.capacity == 0:
            return self._zero_balance(total_runoff, wastewater_inflow, upstream_inflow, runoff)

        first_flush = min(runoff, self.first_flush)
        inflow = runoff - first_flush + self.is_open * precipitation * self.area

        current_storage = min(self.capacity, max(0.0, initial_storage + inflow))
        evaporation = self.is_open * min(potential_evaporation * self.area, current_storage)
        final_storage = current_storage - evaporation
        overflow = max(0.0, initial_storage + inflow - final_storage)
        sewer_inflow = first_flush + overflow

        water_balance = inflow - (evaporation + overflow) - (final_storage - initial_storage)

        return StormwaterData(
            total_runoff=total_runoff,
            wastewater_inflow=wastewater_inflow,
            upstream_inflow=upstream_inflow,
            runoff=runoff,
            first_flush=first_flush,
            inflow=inflow,
            evaporation=evaporation,
            overflow=overflow,
            sewer_inflow=sewer_inflow,
            storage=final_storage,
            water_balance=water_balance
        )

    @staticmethod
    def _zero_balance(total_runoff: float, wastewater_inflow: float,
                      upstream_inflow: float, runoff: float) -> StormwaterData:
        return StormwaterData(
            total_runoff=total_runoff,
            wastewater_inflow=wastewater_inflow,
            upstream_inflow=upstream_inflow,
            runoff=runoff,
            first_flush=0.0,
            inflow=0.0,
            evaporation=0.0,
            overflow=0.0,
            sewer_inflow=runoff,
            storage=0.0,
            water_balance=0.0
        )