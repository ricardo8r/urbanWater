from typing import Dict, Any, Tuple
import pandas as pd
from duwcm.data_structures import PerviousData
from duwcm.functions import soil_selector

# Constants
SATURATED_PERMEABILITY_FACTOR = 10

class PerviousClass:
    """
    Calculates water balance for a pervious area.

    Inflows: Precipitation, irrigation, non-effective runoff from roof and pavement
    Outflows: Evaporation, overflow from pervious interception, infiltration to groundwater 
    """

    def __init__(self, params: Dict[str, Dict[str, Any]], soil_data: pd.DataFrame,
                 et_data: pd.DataFrame, pervious_data: PerviousData):
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
        self.pervious_data = pervious_data
        self.pervious_data.area = params['pervious']['area']
        self.pervious_data.storage.capacity = params['pervious']['max_storage']
        self.pervious_data.infiltration_capacity = params['pervious']['infiltration_capacity']
        self.pervious_data.irrigation_factor = params['irrigation']['pervious']

        self.roof_area = params['roof']['area']
        self.pavement_area = params['pavement']['area']
        self.time_step = params['general']['time_step']
        self.leakage_rate = params['groundwater']['leakage_rate'] / 100

        # Get soil parameters
        soil_params = soil_selector(soil_data, et_data,
                                  params['soil']['soil_type'],
                                  params['soil']['crop_type'])[0]
        self.moisture_root_capacity = soil_params['moist_cont_eq_rz[mm]']
        self.saturated_permeability = 10 * soil_params['k_sat']

    def solve(self, forcing: pd.Series) -> None:
        """
        Args:
            forcing (pd.DataFrame): Climate forcing data with columns:
                precipitation: Precipitation [mm]
                potential_evaporation: Potential evaporation [mm]
                irrigation: Irrigation on area (default: 0) [mm]

        Updates pervious_data with:
            storage: Final interception storage level (t+1) [mm]
        Updates flows with:
            precipitation: Precipitation on pervious area [mm*m^2]
            irrigation: Irrigation on pervious area [mm*m^2]
            from_roof: Non-effective runoff from roof area [mm*m^2]
            from_pavement: Non-effective runoff from pavement area [mm*m^2]
            evaporation: Evaporation from pervious area [mm*m^2]
            to_vadose: Infiltration to vadose zone [mm*m^2]
            to_groundwater: Leakage to groundwater [mm*m^2]
            to_stormwater: Overflow from pervious interception [mm*m^2]
        """
        data = self.pervious_data
        precipitation = forcing['precipitation']
        potential_evaporation = forcing['potential_evaporation']
        irrigation = forcing.get('pervious_irrigation', 0.0) * data.irrigation_factor

        if data.area == 0:
            return

        # Calculate inflows
        irrigation_leakage = irrigation * self.leakage_rate / (1 - self.leakage_rate)
        roof_inflow = data.flows.get_flow('from_roof') / data.area
        pavement_inflow = data.flows.get_flow('from_pavement') / data.area
        total_inflow = precipitation + irrigation + roof_inflow + pavement_inflow

        # Calculate current storage
        current_storage = max(0.0, data.storage.previous + total_inflow)

        # Calculate infiltration capacity using linked vadose moisture
        infiltration_capacity = min(
            self.time_step * data.infiltration_capacity,
            self.moisture_root_capacity - data.vadose_moisture.previous +
            min(self.moisture_root_capacity - data.vadose_moisture.previous,
                self.time_step * self.saturated_permeability)
        )

        # Calculate time factor and resulting fluxes
        time_factor = min(1.0, current_storage / (potential_evaporation + infiltration_capacity))
        evaporation = time_factor * potential_evaporation
        infiltration = time_factor * infiltration_capacity

        # Calculate final storage and overflow
        data.storage.amount = min(data.storage.capacity,
                                  max(0.0, current_storage - evaporation - infiltration))
        overflow = max(0.0, total_inflow - evaporation - infiltration - data.storage.change)

        # Update flows
        data.flows.set_flow('precipitation', precipitation * data.area)
        data.flows.set_flow('irrigation', irrigation * data.area)
        data.flows.set_flow('evaporation', evaporation * data.area)
        data.flows.set_flow('to_vadose', infiltration * data.area)
        data.flows.set_flow('to_stormwater', overflow * data.area)
        data.flows.set_flow('to_groundwater', irrigation_leakage * data.area)