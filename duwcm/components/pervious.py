from typing import Dict, Any, Tuple
import pandas as pd
from duwcm.data_structures import PerviousData
from duwcm.functions import soil_selector

# Constants
SATURATED_PERMEABILITY_FACTOR = 10

class PerviousClass:
    """
    Calculates water balance for a pervious area.

    Inflows: Precipitation, irrigation, non-effective runoff from roof and impervious
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

        self.pervious_data.flows.set_areas(self.pervious_data.area)
        self.pervious_data.storage.set_area(self.pervious_data.area)
        self.pervious_data.storage.set_capacity(params['pervious']['max_storage'], 'mm')
        self.pervious_data.storage.set_previous(0, 'mm')

        self.infiltration_capacity = params['pervious']['infiltration_capacity']
        self.pervious_data.irrigation_factor = params['irrigation']['pervious']

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
            from_impervious: Non-effective runoff from impervious area [m³]
            evaporation: Evaporation from pervious area [m³]
            to_vadose: Infiltration to vadose zone [m³]
            to_groundwater: Leakage to groundwater [m³]
            to_stormwater: Overflow from pervious interception [m³]
        """
        data = self.pervious_data

        if data.area == 0:
            return

        data.flows.set_flow('precipitation', forcing['precipitation'], 'mm')
        data.flows.set_flow('from_demand', forcing.get('pervious_irrigation', 0.0) * data.irrigation_factor, 'mm')

        # Calculate inflows
        total_inflow = (data.flows.get_flow('precipitation', 'mm') +
                        data.flows.get_flow('from_demand', 'mm') +
                        data.flows.get_flow('from_roof', 'mm') +
                        data.flows.get_flow('from_impervious', 'mm'))

        # Calculate current storage
        current_storage = max(0.0, data.storage.get_previous('mm') + total_inflow)

        # Calculate infiltration capacity using linked vadose moisture
        available_space = max(0, self.moisture_root_capacity - data.vadose_moisture.get_previous('mm'))
        max_percolation = self.time_step * self.saturated_permeability
        data.infiltration_capacity = min(self.time_step * self.infiltration_capacity, available_space +
                                    min(available_space, max_percolation))

        # Calculate time factor and resulting fluxes
        data.flows.set_flow('evaporation', forcing['potential_evaporation'], 'mm')
        denominator = data.flows.get_flow('evaporation', 'mm') + data.infiltration_capacity
        time_factor = 0.0 if denominator <= 0 else min(1.0, current_storage / denominator)

        data.flows.set_flow('evaporation', time_factor * data.flows.get_flow('evaporation', 'mm'), 'mm')
        data.flows.set_flow('to_vadose', time_factor * data.infiltration_capacity, 'mm')

        # Calculate final storage and overflow
        data.storage.set_amount(min(data.storage.get_capacity('mm'),
                                    max(0.0, current_storage -
                                        data.flows.get_flow('evaporation', 'mm') -
                                        data.flows.get_flow('to_vadose', 'mm'))
                                    ),
                                'mm')

        overflow = max(0.0, total_inflow -
                       data.flows.get_flow('evaporation', 'mm') -
                       data.flows.get_flow('to_vadose', 'mm') -
                       data.storage.get_change('mm'))

        data.flows.set_flow('to_stormwater', overflow, 'mm')
        data.flows.set_flow('to_groundwater',data.flows.get_flow('from_demand', 'mm') *
                            self.leakage_rate / (1 - self.leakage_rate), 'mm')
        data.flows.set_flow('from_demand', data.flows.get_flow('from_demand', 'mm') /
                            (1 - self.leakage_rate), 'mm')