from typing import Dict, Any, Tuple
import pandas as pd
from duwcm.data_structures import GreenRoofData

class GreenRoofClass:
    """
    Calculates water balance for a green roof surface.

    Inflows: precipitation, irrigation
    Outflows: evaporation, overflow, infiltration to substrate
    """

    def __init__(self, params: Dict[str, Dict[str, Any]], greenroof_data: GreenRoofData):
        """
        Args:
            params (Dict[str, float]): System parameters
                area: Green roof area [m²]
                effective_outflow: Area connected with drainage [%]
                max_storage: Green roof storage capacity [mm]
                max_substrate_storage: Substrate storage capacity [mm]
                substrate_depth: Depth of substrate [mm]
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

        self.greenroof_data.effective_outflow = (1.0 if params['pervious']['area'] == 0
                                            else params['greenroof']['effective_area'] / 100)
        self.greenroof_data.substrate_depth = params['greenroof'].get('substrate_depth', 100)
        self.time_step = params['general']['time_step']

    def solve(self, forcing: pd.Series) -> None:
        """
        Args:
            forcing (pd.DataFrame): Climate forcing data with columns:
                precipitation: Precipitation [mm]
                potential_evaporation: Potential evaporation [mm]
                irrigation: Irrigation on roof (default: 0) [mm]

        Updates greenroof_data with:
            surface_storage: Surface water storage volume after total outflows [m³]
            substrate_storage: Substrate water storage volume after total outflows [m³]
        Updates flows with:
            precipitation: Direct precipitation [m³]
            irrigation: Irrigation [m³]
            from_demand: Demanded water for irrigation [m³]
            evaporation: Evaporation [m³]
            transpiration: Plant transpiration [m³]
            to_substrate: Infiltration to substrate [m³]
            to_stormwater: Effective runoff to stormwater system [m³]
            to_pervious: Non-effective runoff to pervious areas [m³]
        """
        data = self.greenroof_data

        if data.area == 0:
            return

        data.flows.set_flow('precipitation', forcing['precipitation'], 'mm')
        data.flows.set_flow('from_demand', forcing.get('greenroof_irrigation', 0.0), 'mm')

        # Calculate surface water balance
        surface_inflow = (data.flows.get_flow('precipitation', 'm3') +
                         data.flows.get_flow('from_demand', 'm3'))

        current_surface_storage = min(data.surface_storage.get_capacity('m3'),
                                    max(0.0, data.surface_storage.get_previous('m3') + surface_inflow))

        # Calculate substrate infiltration based on available storage in substrate
        substrate_capacity = data.substrate_storage.get_capacity('m3')
        current_substrate = data.substrate_storage.get_previous('m3')
        available_substrate_storage = max(0, substrate_capacity - current_substrate)

        # Infiltration to substrate depends on available space
        infiltration_rate = min(current_surface_storage, available_substrate_storage)
        data.flows.set_flow('to_substrate', infiltration_rate, 'm3')

        # Update substrate storage with infiltration
        data.substrate_storage.set_amount(current_substrate + infiltration_rate, 'm3')

        # Calculate evapotranspiration - enhanced due to plants
        # Green roofs typically have 2-3x more ET than conventional roofs
        et_factor = 2.0  # Evapotranspiration enhancement factor for green roofs
        potential_et = forcing['potential_evaporation'] * et_factor

        # Split between evaporation (from surface) and transpiration (from substrate)
        surface_fraction = max(0, min(1, current_surface_storage / (current_surface_storage + current_substrate)))

        # Calculate evaporation from surface water
        evaporation = surface_fraction * potential_et
        data.flows.set_flow('evaporation', evaporation, 'mm')
        evaporation_volume = min(data.flows.get_flow('evaporation', 'm3'), current_surface_storage)
        data.flows.set_flow('evaporation', evaporation_volume, 'm3')

        # Calculate transpiration from substrate
        transpiration = (1 - surface_fraction) * potential_et
        data.flows.set_flow('transpiration', transpiration, 'mm')
        transpiration_volume = min(data.flows.get_flow('transpiration', 'm3'), data.substrate_storage.get_amount('m3'))
        data.flows.set_flow('transpiration', transpiration_volume, 'm3')

        # Update substrate storage with transpiration loss
        data.substrate_storage.set_amount(data.substrate_storage.get_amount('m3') - transpiration_volume, 'm3')

        # Update surface storage after evaporation and infiltration
        data.surface_storage.set_amount(current_surface_storage -
                                      evaporation_volume -
                                      data.flows.get_flow('to_substrate', 'm3'),
                                      'm3')

        # Calculate overflow from surface
        excess_water = max(0.0, surface_inflow -
                          evaporation_volume -
                          data.flows.get_flow('to_substrate', 'm3') -
                          data.surface_storage.get_change('m3'))

        # Split runoff between stormwater and pervious based on effective outflow ratio
        effective_runoff = data.effective_outflow * excess_water
        non_effective_runoff = excess_water - effective_runoff

        data.flows.set_flow('to_stormwater', effective_runoff, 'm3')
        data.flows.set_flow('to_pervious', non_effective_runoff, 'm3')