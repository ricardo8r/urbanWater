from typing import Dict, Any, Tuple, Optional
import pandas as pd
from urbanWater.data_structures import GreenRoofData

class GreenRoofClass:
    """
    Calculates water balance for a green roof surface.

    Inflows: precipitation, irrigation
    Outflows: evaporation, overflow, infiltration to substrate, transpiration, substrate drainage
    
    Model: two-layer storage
    1. Surface Storage: Intercepts precip/irrigation. Lost to evaporation, infiltration to substrate, or overflow.
    2. Substrate Storage: Receives infiltration. Lost to transpiration or drainage (when saturated).
    """

    def __init__(self, params: Dict[str, Dict[str, Any]], greenroof_data: GreenRoofData,
                 et_data: Optional[pd.DataFrame] = None):
        """
        Args:
            params (Dict[str, float]): System parameters
                area: Green roof area [m²]
                effective_outflow: Area connected with drainage [%]
                max_storage: Surface storage capacity [mm]
                max_substrate_storage: Substrate storage capacity [mm] (e.g. porosity * depth)
                substrate_depth: Depth of substrate [mm]
                crop_factor: Crop coefficient (Kc) [-]
                conductivity: Hydraulic conductivity of substrate [mm/h]. 
                              Limits infiltration rate and drainage rate.
                time_step: Time step [day]
        """
        self.greenroof_data = greenroof_data

        self.greenroof_data.area = abs(params['greenroof']['area'])
        self.greenroof_data.flows.set_areas(self.greenroof_data.area)
        self.greenroof_data.surface_storage.set_area(self.greenroof_data.area)
        self.greenroof_data.substrate_storage.set_area(self.greenroof_data.area)

        self.greenroof_data.surface_storage.set_capacity(params['greenroof']['max_storage'], 'mm')
        self.greenroof_data.substrate_storage.set_capacity(params['greenroof']['max_substrate_storage'], 'mm')

        self.greenroof_data.surface_storage.set_previous(0, 'mm')
        self.greenroof_data.substrate_storage.set_previous(
            params['greenroof'].get('initial_substrate_storage', 0), 'mm')

        self.greenroof_data.effective_outflow = (1.0 if params['pervious'].get('area', 0) == 0
                                            else params['greenroof'].get('effective_area', 100.0) / 100.0)
        self.greenroof_data.substrate_depth = params['greenroof'].get('substrate_depth', 100.0)
        self.greenroof_data.crop_factor = params['greenroof'].get('crop_factor', 1.0)
        self.greenroof_data.conductivity = params['greenroof'].get('conductivity', 10.0)

        self.time_step = params['general'].get('time_step', 1.0)

    def solve(self, forcing: pd.Series) -> None:

        """
        Calculate water balance for one time step.

        Args:
            forcing (pd.DataFrame): Climate forcing data with columns:
                precipitation: Precipitation [mm]
                potential_evaporation: Potential evaporation [mm]
                greenroof_irrigation: Irrigation [mm] (optional)

        Updates greenroof_data with:
            surface_storage: Surface water storage volume after total outflows [m³]
            substrate_storage: Substrate water storage volume after total outflows [m³]

        Updates flows with:
            precipitation: Direct precipitation [m³]
            from_demand: Irrigation water [m³]
            evaporation: Evaporation from surface storage [m³]
            transpiration: Transpiration from substrate storage [m³]
            to_substrate: Infiltration from surface to substrate [m³]
            to_stormwater: Effective runoff (Surface Overflow + Substrate Drainage) [m³]
            to_pervious: Non-effective runoff (Surface Overflow + Substrate Drainage) [m³]
        """
        data = self.greenroof_data

        if data.area == 0:
            return

        # 1. Inputs
        data.flows.set_flow('precipitation', forcing['precipitation'], 'mm')
        data.flows.set_flow('from_demand', forcing.get('greenroof_irrigation', 0.0), 'mm')

        total_inflow = (data.flows.get_flow('precipitation', 'm3') +
                        data.flows.get_flow('from_demand', 'm3'))

        # 2. Surface Balance
        current_surface_storage_vol = data.surface_storage.get_previous('m3') + total_inflow

        # 3. Surface Evaporation
        pe_mm = forcing['potential_evaporation']

        # Evaporation from surface (before infiltration)
        evaporation_vol = min(current_surface_storage_vol, 
                              (pe_mm * data.area / 1000.0))

        data.flows.set_flow('evaporation', evaporation_vol, 'm3')
        current_surface_storage_vol -= evaporation_vol

        # 4. Infiltration to Substrate
        # Driven by: Available water on surface and infiltration capacity (conductivity).

        # Max infiltration based on K_sat
        max_infiltration_vol = (data.conductivity * 24.0 * self.time_step * data.area / 1000.0)

        # Infiltration limited by surface water and conductivity
        # (Substrate capacity is handled via drainage/overflow in the new model)
        infiltration_vol = min(current_surface_storage_vol, max_infiltration_vol)

        data.flows.set_flow('to_substrate', infiltration_vol, 'm3')

        current_surface_storage_vol -= infiltration_vol
        current_substrate_vol = data.substrate_storage.get_previous('m3') + infiltration_vol

        # 5. Transpiration from Substrate
        potential_transpiration_mm = pe_mm * data.crop_factor
        transpiration_vol = min(current_substrate_vol, 
                                potential_transpiration_mm * data.area / 1000.0)

        data.flows.set_flow('transpiration', transpiration_vol, 'm3')
        current_substrate_vol -= transpiration_vol

        # 6. Substrate Drainage (Saturation Excess)
        substrate_capacity_vol = data.substrate_storage.get_capacity('m3')
        excess_substrate_vol = max(0.0, current_substrate_vol - substrate_capacity_vol)

        charge_drainage = excess_substrate_vol # Instant drainage
        drainage_vol = charge_drainage
        current_substrate_vol -= drainage_vol

        data.substrate_storage.set_amount(current_substrate_vol, 'm3')

        # 7. Surface Overflow
        surface_capacity_vol = data.surface_storage.get_capacity('m3')
        excess_surface_vol = max(0.0, current_surface_storage_vol - surface_capacity_vol)
        surface_overflow_vol = excess_surface_vol
        current_surface_storage_vol -= surface_overflow_vol

        data.surface_storage.set_amount(current_surface_storage_vol, 'm3')

        # 8. Total Runoff & Routing
        total_runoff_vol = surface_overflow_vol + drainage_vol

        effective_runoff = total_runoff_vol * data.effective_outflow
        non_effective_runoff = total_runoff_vol - effective_runoff

        data.flows.set_flow('to_stormwater', effective_runoff, 'm3')
        data.flows.set_flow('to_pervious', non_effective_runoff, 'm3')