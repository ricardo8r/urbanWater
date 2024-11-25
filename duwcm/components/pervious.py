from typing import Dict, Any, Tuple
import pandas as pd
from duwcm.data_structures import PerviousData
from duwcm.functions import soil_selector

# Constants
TO_METERS = 0.001
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
                area: Pervious area [m²]
                capacity: Maximum storage capacity [m³]
                previous: Initial storage [m³]
                infiltration_capacity: Pervious infiltration capacity [m/d]
                time_step: Time step [day]
                soil_type: Soil type []
                crop_type: Crop type []
            soil_matrix: Soil parameter matrix
            et_matrix: Evapotranspiration matrix

        Attributes:
            moisture_root_capacity: Root zone water capacity [m]
            saturated_permeability: Saturated soil permeability [m/d]
        """
        self.pervious_data = pervious_data
        self.pervious_data.area = params['pervious']['area']

        self.pervious_data.storage.set_area(self.pervious_data.area)
        self.pervious_data.storage.set_capacity(params['pervious']['max_storage'], 'mm')
        self.pervious_data.storage.set_previous(0, 'mm')

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
            storage: Final interception storage level (t+1) [m³]
        Updates flows with:
            precipitation: Precipitation on pervious area [m³]
            irrigation: Irrigation on pervious area [m³]
            from_roof: Non-effective runoff from roof area [m³]
            from_pavement: Non-effective runoff from pavement area [m³]
            evaporation: Evaporation from pervious area [m³]
            to_vadose: Infiltration to vadose zone [m³]
            to_groundwater: Leakage to groundwater [m³]
            to_stormwater: Overflow from pervious interception [m³]
        """
        data = self.pervious_data
        precipitation = forcing['precipitation'] * data.area
        potential_evaporation = forcing['potential_evaporation'] * data.area
        irrigation = forcing.get('pervious_irrigation', 0.0) * data.irrigation_factor * data.area

        if data.area == 0:
            return

        # Calculate inflows
        irrigation_leakage = irrigation * self.leakage_rate / (1 - self.leakage_rate)
        roof_inflow = data.flows.get_flow('from_roof') / TO_METERS
        pavement_inflow = data.flows.get_flow('from_pavement') / TO_METERS
        total_inflow = precipitation + irrigation + roof_inflow + pavement_inflow

        # Calculate current storage
        current_storage = max(0.0, data.storage.get_previous('L') + total_inflow)

        # Calculate infiltration capacity using linked vadose moisture
        infiltration_capacity = min(
            self.time_step * data.infiltration_capacity,
            self.moisture_root_capacity - data.vadose_moisture.get_previous('mm') +
            min(self.moisture_root_capacity - data.vadose_moisture.get_previous('mm'),
                self.time_step * self.saturated_permeability)
        )

        # Calculate time factor and resulting fluxes
        time_factor = min(1.0, current_storage / (potential_evaporation + infiltration_capacity * data.area))
        evaporation = time_factor * potential_evaporation
        infiltration = time_factor * infiltration_capacity * data.area

        # Calculate final storage and overflow
        data.storage.set_amount(min(data.storage.get_capacity('L'),
                                    max(0.0, current_storage - evaporation - infiltration)), 'L')
        overflow = max(0.0, total_inflow - evaporation - infiltration - data.storage.get_change('L'))

        # Update flows
        data.flows.set_flow('precipitation', precipitation * TO_METERS)
        data.flows.set_flow('from_demand', irrigation + irrigation_leakage * TO_METERS)
        data.flows.set_flow('evaporation', evaporation * TO_METERS)
        data.flows.set_flow('to_vadose', infiltration * TO_METERS)
        data.flows.set_flow('to_stormwater', overflow * TO_METERS)
        data.flows.set_flow('to_groundwater', irrigation_leakage * TO_METERS)