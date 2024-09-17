from typing import Dict, Any
import pandas as pd
from duwcm.data_structures import UrbanWaterData, WastewaterData

class WastewaterClass:
    """
    Simulates cluster wastewater storage dynamics.

    Inflows: Stormwater, reuse, upstream and infiltration
    Outflows: Sewer
    """
    def __init__(self, params: Dict[str, Dict[str, Any]]):
        """
        Args:
            params (Dict[str, float]): System parameters
                groundwater_area: Area of groundwater storage [m^2]
                cluster_storage_capacity: Wastewater storage capacity [L]
        """
        self.groundwater_area = params['groundwater']['area']
        self.area = params['wastewater']['area']
        self.cluster_storage_capacity = params['wastewater']['capacity']

    def solve(self, forcing: pd.Series, previous_state: UrbanWaterData,
              current_state: UrbanWaterData) -> WastewaterData:
        """
        Calculate the states and fluxes on wastewater storage during current time step.

        Args:
            forcing (pd.DataFrame): Climate forcing data with columns:
            previous_state (pd.DataFrame): State variables from the previous time step with columns:
                previous_storage: WWS storage at the end of previous time step [L]
                upstream_inflow: Wastewater sewer system flow from upstream grid [L] (default: 0)
            current_state (pd.DataFrame): Current state variables with columns:
                reuse_outflow: Outflow from onsite wastewater storage [L]
                infiltration: Infiltration from groundwater to wastewater pipe [mm]
                stormwater_inflow: Inflow of stormwater to wastewater sewer system [L]

        Returns:
            Dict[str, float]: Computed states and fluxes of wastewater storage during current time step
                inflow: Inflow to wastewater system [L]
                upstream_inflow: Wastewater sewer system flow from upstream grid [L]
                sewer_inflow: Wastewater sewer system inflow [L]
                storage: Wastewater storage at the end of the time step [L]
                water_balance: Water balance [L]
        """
        previous_storage = previous_state.wastewater.storage

        upstream_inflow = current_state.wastewater.upstream_inflow
        stormwater_inflow = current_state.stormwater.wastewater_inflow
        infiltration = current_state.groundwater.pipe_infiltration
        reuse_outflow = current_state.reuse.wws_spillover


        total_inflow = (reuse_outflow + infiltration * self.groundwater_area +
                        stormwater_inflow + upstream_inflow)

        if self.cluster_storage_capacity == 0:
            return self._zero_balance(upstream_inflow, total_inflow)

        final_storage = min(self.cluster_storage_capacity, previous_storage + total_inflow)
        sewer_inflow = max(0.0, total_inflow - (final_storage - previous_storage))
        water_balance = total_inflow - sewer_inflow - (final_storage - previous_storage)

        return WastewaterData(
            total_inflow = total_inflow,
            sewer_inflow = sewer_inflow,
            upstream_inflow = upstream_inflow,
            storage = final_storage,
            water_balance = water_balance
        )

    @staticmethod
    def _zero_balance(upstream_inflow: float, total_inflow: float) -> WastewaterData:
        return WastewaterData(
            total_inflow = 0.0,
            sewer_inflow = total_inflow,
            upstream_inflow = upstream_inflow,
            storage = 0.0,
            water_balance = 0.0
        )