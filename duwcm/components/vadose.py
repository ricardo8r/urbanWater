from typing import Dict, Any, Tuple
import pandas as pd
from duwcm.data_structures import VadoseData
from duwcm.functions import soil_selector, et_selector, gw_levels

# Constants
TO_METERS = 0.001
SATURATED_CONDUCTIVITY_FACTOR = 10
MIN_REFERENCE_EVAPORATION = 1.0  # mm/day
MAX_REFERENCE_EVAPORATION = 5.0  # mm/day

class VadoseClass:
    """
    Simulates water balance in the vadose zone.
    """
    def __init__(self, params: Dict[str, Dict[str, Any]], soil_data: pd.DataFrame,
                 et_data: pd.DataFrame, vadose_data: VadoseData):
        """
        Args:
            params (Dict[str, float]): Zone parameters
                area: Area of vadose zone [m²]
                previous: Vadose initial moisture [m³]
                time_step: Time step [day]
                soil_type: Soil type
                crop_type: Crop type

        Attributes: Equilibrium moisture content of soil in root zone:
            moisture_low_evaporation: Transpiration (E_pot ≤ 1 mm/d) reduction starts
            moisture_high_evaporation: Transpiration (E_pot ≥ 5 mm/d) reduction starts
            moisture_saturated: Groundwater level at surface level, i.e. complete saturation
            moisture_field_capacity: Groundwater level at bottom root zone, i.e. field capacity
            moisture_wilting_point: Transpiration = 0, i.e. permanent wilting point
        """
        self.vadose_data = vadose_data
        self.vadose_data.area = params['vadose']['area']

        self.vadose_data.moisture.set_area(self.vadose_data.area)
        self.vadose_data.moisture.set_previous = (params['vadose']['initial_moisture'], 'mm')

        self.time_step = params['general']['time_step']
        soil_type = params['soil']['soil_type']
        crop_type = params['soil']['crop_type']

        self.soil_params = soil_selector(soil_data, et_data, soil_type, crop_type)
        self.saturated_conductivity = SATURATED_CONDUCTIVITY_FACTOR * self.soil_params[0]['k_sat']

        self.et_params = et_selector(et_data, soil_type, crop_type)
        self.moisture_low_evaporation = self.et_params['theta_h3l_mm'].values[0]
        self.moisture_high_evaporation = self.et_params['theta_h3h_mm'].values[0]
        self.moisture_saturated = self.et_params['theta_h1_mm'].values[0]
        self.moisture_field_capacity = self.et_params['theta_h2_mm'].values[0]
        self.moisture_wilting_point = self.et_params['theta_h4_mm'].values[0]

    def solve(self, forcing: pd.Series) -> None:
        """
        Args:
            forcing (pd.DataFrame): Climate forcing data with columns:
                reference_evaporation: Reference evaporation [mm] (potential evaporation)

        Updates vadose_data with:
            moisture: Moisture content of root zone (t+1) [mm]
        Updates flows with:
            from_pervious: Infiltration from pervious area [m³]
            transpiration: Transpiration from vadose zone [m³]
            to_groundwater: Percolation to groundwater [m³]
        """
        data = self.vadose_data
        reference_evaporation = forcing['potential_evaporation']

        if data.area == 0:
            return

        # Get infiltration from pervious area through flows
        pervious_infiltration = data.flows.get_flow('from_pervious') / data.area

        # Calculate transpiration
        data.transpiration_threshold = self._transpiration_threshold(reference_evaporation)
        data.transpiration_factor = self._transpiration_factor(pervious_infiltration,
                                                               data.transpiration_threshold,
                                                               data.moisture.get_previous('mm')
                                                               )
        transpiration = min(data.transpiration_factor * reference_evaporation,
                            data.moisture.get_previous('mm') + pervious_infiltration)

        # Calculate soil moisture dynamics
        equilibrium_moisture, data.max_capillary = self._soil_properties(data.groundwater_level.get_previous('m'))
        current_moisture = data.moisture.get_previous('mm') + pervious_infiltration - transpiration

        # Calculate percolation
        if current_moisture > equilibrium_moisture:
            percolation = min(current_moisture - equilibrium_moisture,
                              self.time_step * self.saturated_conductivity)
        else:
            percolation = -1 * min(equilibrium_moisture - current_moisture,
                                   self.time_step * data.max_capillary)

        # Update final moisture
        #infiltration = np.sqrt(current_moisture - percolation) * self.infiltration_recession
        data.moisture.set_amount(current_moisture - percolation, 'mm') #- infiltration

        # Update flows
        data.flows.set_flow('transpiration', transpiration * data.area * TO_METERS)
        data.flows.set_flow('to_groundwater', percolation * data.area * TO_METERS)

    def _transpiration_threshold(self, reference_evaporation: float) -> float:
        if reference_evaporation < MIN_REFERENCE_EVAPORATION:
            return self.moisture_low_evaporation
        if reference_evaporation > MAX_REFERENCE_EVAPORATION:
            return self.moisture_high_evaporation

        return ((reference_evaporation - 1.0) / (MAX_REFERENCE_EVAPORATION - MIN_REFERENCE_EVAPORATION) *
                (self.moisture_high_evaporation - self.moisture_low_evaporation) + self.moisture_low_evaporation)

    def _transpiration_factor(self, infiltration: float, transpiration_threshold: float,
                              initial_moisture: float) -> float:
        total_moisture = initial_moisture + infiltration
        if total_moisture > self.moisture_saturated:
            return 0.0
        if total_moisture > self.moisture_field_capacity:
            return (1 - (total_moisture - self.moisture_field_capacity) /
                    (self.moisture_saturated - self.moisture_field_capacity))
        if total_moisture > transpiration_threshold:
            return 1.0
        if total_moisture > self.moisture_wilting_point:
            return ((total_moisture - self.moisture_wilting_point) /
                    (transpiration_threshold - self.moisture_wilting_point))

        return 0.0

    def _soil_properties(self, groundwater_level: float) -> Tuple[float, float]:
        gw_up, gw_low, id_up, id_low = gw_levels(groundwater_level)

        if groundwater_level < 10:    #REVIEW: Why 10?
            interpolation_factor = (groundwater_level - gw_up) / (gw_low - gw_up)
            equilibrium_moisture = self.soil_params[id_up]['moist_cont_eq_rz[mm]'] + interpolation_factor * (
                self.soil_params[id_low]['moist_cont_eq_rz[mm]'] - self.soil_params[id_up]['moist_cont_eq_rz[mm]'])
            max_capillary_rise = self.soil_params[id_up]['capris_max[mm/d]'] + interpolation_factor * (
                self.soil_params[id_low]['capris_max[mm/d]'] - self.soil_params[id_up]['capris_max[mm/d]'])
        else:
            equilibrium_moisture = self.soil_params[29]['moist_cont_eq_rz[mm]']
            max_capillary_rise = self.soil_params[29]['capris_max[mm/d]']

        return equilibrium_moisture, max_capillary_rise
