from typing import Dict, Any, Tuple
import pandas as pd
from duwcm.data_structures import UrbanWaterData, PerviousData, PerviousFlowsData, Flow
from duwcm.functions import soil_selector

# Constants
SATURATED_PERMEABILITY_FACTOR = 10

class PerviousClass:
    """
    Calculates water balance for a pervious area.

    Inflows: Precipitation, irrigation, non-effective runoff from roof and pavement
    Outflows: Evaporation, overflow from pervious interception, infiltration to groundwater 
    """

    def __init__(self, params: Dict[str, Dict[str, Any]], soil_data: pd.DataFrame, et_data: pd.DataFrame):
        """
        Args:
            params (Dict[str, float]): Surface parameters
                area: Pervious area [m^2]
                roof_area: Roof area [m^2]
                pavement_area: Paved area [m^2]
                max_storage: Maximum storage capacity [mm]
                infiltration_capacity: Pervious infiltration capacity [mm/d]
                time_step: Time step [day]
                soil_type: Soil type []
                crop_type: Crop type []
            soil_matrix: Soil parameter matrix
            et_matrix: Evapotranspiration matrix

        Attributes:
            moisture_root_capacity: Root zone water capacity [mm]
            saturated_permeability: Saturated soil permeability [mm/d]
        """
        self.area = params['pervious']['area']
        self.roof_area = params['roof']['area']
        self.pavement_area = params['pavement']['area']
        self.time_step = params['general']['time_step']
        self.max_storage = params['pervious']['max_storage']
        self.infiltration_capacity = params['pervious']['infiltration_capacity']
        self.irrigation_factor = params['irrigation']['pervious']
        self.soil_type = params['soil']['soil_type']
        self.crop_type = params['soil']['crop_type']

        self.soil_params = soil_selector(soil_data, et_data, self.soil_type, self.crop_type)[0]
        self.moisture_root_capacity = self.soil_params['moist_cont_eq_rz[mm]']
        self.saturated_permeability = SATURATED_PERMEABILITY_FACTOR * self.soil_params['k_sat']

    def solve(self, forcing: pd.Series, previous_state: UrbanWaterData,
              current_state: UrbanWaterData) -> Tuple[PerviousData, PerviousFlowsData]:
        """
        Args:
            forcing (pd.DataFrame): Climate forcing data with columns:
                precipitation: Precipitation [mm]
                potential_evaporation: Potential evaporation [mm]
                irrigation: Irrigation on area (default: 0) [mm]
            previous_state (pd.DataFrame): State variables from the previous time step with columns:
                Vadose:
                    vadose_moisture: Moisture content in vadose zone [mm]
                Pavement:
                    previous_storage: Initial storage at current time step (t) [L]
            current_state (pd.DataFrame): Current state variables with columns:
                Roof:
                    roof_runoff: Non-effective runoff from roof area) [mm m^2]
                Pavement:
                    pavement_runoff: Non-effective runoff from pavement area [mm m^2]

        Returns:
            Dict[str, float]: Water balance components for the current time step
                inflow: Inflow from imprevious area [mm]
                infiltration_capacity: Infiltration capacity on pervious area [mm]
                time_factor: Time step fraction when interception storage is available [mm]
                evaporation: Evaporation [mm]
                infiltration: Infiltration to vadose zone [mm]
                overflow: Overflow from pervious interception [mm]
                storage: Final interception storage level (t+1) [mm]
                water_balance: Total water balance [L]
        """
        precipitation = forcing['precipitation']
        potential_evaporation = forcing['potential_evaporation']
        irrigation = forcing.get('pervious_irrigation', 0.0) * self.irrigation_factor

        previous_storage = previous_state.pervious.storage
        vadose_moisture = previous_state.vadose.moisture
        roof_runoff = current_state.roof.non_effective_runoff
        pavement_runoff = current_state.pavement.non_effective_runoff

        if self.area == 0:
            return self._zero_balance()

        inflow = (roof_runoff * self.roof_area +
                  pavement_runoff * self.pavement_area) / self.area
        current_storage = max(0.0, previous_storage + precipitation + inflow + irrigation)

        infiltration_capacity = min(self.time_step * self.infiltration_capacity,
                                    self.moisture_root_capacity - vadose_moisture +
                                    min(self.moisture_root_capacity - vadose_moisture,
                                        self.time_step * self.saturated_permeability)
                                    )

        time_factor = min(1.0, current_storage / (potential_evaporation + infiltration_capacity))
        evaporation = time_factor * potential_evaporation
        infiltration = time_factor * infiltration_capacity

        final_storage = min(self.max_storage, max(0.0,current_storage - evaporation - infiltration))
        overflow = max(0.0, (precipitation + inflow + irrigation) - (evaporation + infiltration) -
                       (final_storage - previous_storage))

        water_balance = ((precipitation + inflow + irrigation) -
                         (evaporation + infiltration + overflow) -
                         (final_storage - previous_storage)) * self.area

        pervious_data = PerviousData(
            inflow = inflow,
            infiltration_capacity = infiltration_capacity,
            time_factor = time_factor,
            evaporation = evaporation * self.area,
            infiltration = infiltration,
            overflow = overflow,
            storage = final_storage,
            water_balance = water_balance,
        )

        pervious_flows = PerviousFlowsData(flows=[
            Flow(
                source="atmosphere",
                destination="pervious",
                variable="precipitation",
                amount=precipitation * self.area,
                unit="L"
            ),
            Flow(
                source="irrigation_source",
                destination="pervious",
                variable="irrigation",
                amount=irrigation * self.area,
                unit="L"
            ),
            Flow(
                source="roof",
                destination="pervious",
                variable="non_effective_runoff",
                amount=roof_runoff * self.roof_area,
                unit="L"
            ),
            Flow(
                source="pavement",
                destination="pervious",
                variable="non_effective_runoff",
                amount=pavement_runoff * self.pavement_area,
                unit="L"
            ),
            Flow(
                source="pervious",
                destination="atmosphere",
                variable="evaporation",
                amount=evaporation * self.area,
                unit="L"
            ),
            Flow(
                source="pervious",
                destination="vadose",
                variable="infiltration",
                amount=infiltration * self.area,
                unit="L"
            ),
            Flow(
                source="pervious",
                destination="stormwater",
                variable="overflow",
                amount=overflow * self.area,
                unit="L"
            )
        ])

        return pervious_data, pervious_flows

    @staticmethod
    def _zero_balance() -> Tuple[PerviousData, PerviousFlowsData]:
        return PerviousData(
            inflow = 0.0,
            infiltration_capacity = 0.0,
            time_factor = 0.0,
            evaporation = 0.0,
            infiltration = 0.0,
            overflow = 0.0,
            storage = 0.0,
            water_balance = 0.0
        ), PerviousFlowsData(flows=[])