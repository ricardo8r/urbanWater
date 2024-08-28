from typing import Dict, Any, Tuple
import pandas as pd
from duwcm.data_structures import UrbanWaterData, VadoseData
from duwcm.functions.selector import soil_selector, et_selector
from duwcm.functions.gwlcalculator import gw_levels

# Constants
SATURATED_CONDUCTIVITY_FACTOR = 10
MIN_REFERENCE_EVAPORATION = 1.0  # mm/day
MAX_REFERENCE_EVAPORATION = 5.0  # mm/day

class VadoseClass:
    """
    Simulates water balance in the vadose zone.
    """
    def __init__(self, params: Dict[str, Dict[str, Any]], soil_data: pd.DataFrame, et_data: pd.DataFrame):
        """
        Args:
            params (Dict[str, float]): Zone parameters
                area: Area of vadose zone [m^2]
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
        self.area = params['vadose']['area']
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

    def solve(self, forcing: pd.Series, previous_state: UrbanWaterData,
              current_state: UrbanWaterData) -> VadoseData:
        """
        Args:
            forcing (pd.DataFrame): Climate forcing data with columns:
                reference_evaporation: Reference evaporation [mm] (potential evaporation)
            previous_state (pd.DataFrame): State variables from the previous time step with columns:
                Groundwater:
                    groundwater_level: Groundwater storage level [m-SL]
                Vadose:
                    initial_moisture: Initial moisture content of root zone (t) [mm]
            current_state (pd.DataFrame): Current state variables with columns:
                Pervious:
                    infiltration: Infiltration from pervious area [mm m^2]

        Returns:
            Dict[str, float]:
                transpiration_threshold: Equilibriuym moisture content of soil in root zone 
                                        when transpiration reduction starts [mm]
                transpiration_factor: Transpiration reduction factor [-]
                transpiration: Transpiration from vadose zone [mm]
                equilibrium_moisture: Equilibrium moisture content of soil [mm]
                max_capillary: Maximum capillary rise rate [mm/d]
                percolation: Percolation from vadose zone to groundwater [mm]
                            (+percolation -capillary rise)
                moisture: Moisture content of root zone (t+1) [mm]
                water_balance: Total water balance in vadose zone [L]
        """
        reference_evaporation = forcing['potential_evaporation']

        initial_moisture = previous_state.vadose.moisture
        groundwater_level = previous_state.groundwater.water_level
        pervious_infiltration = current_state.pervious.infiltration

        if self.area == 0:
            return self._zero_balance(initial_moisture)

        transpiration_threshold = self._transpiration_threshold(reference_evaporation)
        transpiration_factor = self._transpiration_factor(pervious_infiltration,
                                                          transpiration_threshold, initial_moisture)
        transpiration = transpiration_factor * reference_evaporation

        equilibrium_moisture, max_capillary = self._soil_properties(groundwater_level)

        current_moisture = initial_moisture + pervious_infiltration - transpiration
        if current_moisture > equilibrium_moisture:
            percolation = min(current_moisture - equilibrium_moisture, self.time_step * self.saturated_conductivity)
        else:
            percolation = -1 * min((equilibrium_moisture - current_moisture), self.time_step * max_capillary)

        #infiltration = np.sqrt(current_moisture - percolation) * self.infiltration_recession
        final_moisture = current_moisture - percolation # - infiltration
        water_balance = (pervious_infiltration - (transpiration + percolation) -
                         (final_moisture - initial_moisture)) * self.area

        return VadoseData(
            transpiration_threshold = transpiration_threshold,
            transpiration_factor = transpiration_factor,
            transpiration = transpiration,
            equilibrium_moisture = equilibrium_moisture,
            max_capillary = max_capillary,
            percolation = percolation,
            moisture = final_moisture,
            water_balance = water_balance
        )

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

        if groundwater_level < 10.0:    #REVIEW: Why 10?
            interpolation_factor = (groundwater_level - gw_up) / (gw_low - gw_up)
            equilibrium_moisture = self.soil_params[id_up]['moist_cont_eq_rz[mm]'] + interpolation_factor * (
                self.soil_params[id_low]['moist_cont_eq_rz[mm]'] - self.soil_params[id_up]['moist_cont_eq_rz[mm]'])
            max_capillary_rise = self.soil_params[id_up]['capris_max[mm/d]'] + interpolation_factor * (
                self.soil_params[id_low]['capris_max[mm/d]'] - self.soil_params[id_up]['capris_max[mm/d]'])
        else:
            equilibrium_moisture = self.soil_params[29]['moist_cont_eq_rz[mm]']
            max_capillary_rise = self.soil_params[29]['capris_max[mm/d]']

        return equilibrium_moisture, max_capillary_rise

    @staticmethod
    def _zero_balance(initial_moisture: float) -> VadoseData:
        return VadoseData(
            transpiration_threshold = 0.0,
            transpiration_factor = 0.0,
            transpiration = 0.0,
            equilibrium_moisture = 0.0,
            max_capillary = 0.0,
            percolation = 0.0,
            moisture = initial_moisture,
            water_balance = 0.0
        )
