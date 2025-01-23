"""
Urban area transformation scenario manager. Handles two main types of urban development scenarios:

1. Urban Greening (pervious_ratio > 0):
  - Converts paved areas into green/pervious spaces
  - Only applies to highly urbanized areas (>70% urban coverage)
  - Maintains minimum pavement for essential infrastructure
  
2. Urbanization (pervious_ratio < 0):
  - Converts undeveloped/rural areas into urban spaces
  - Only applies to mostly pervious areas (>70% pervious)
  - Creates typical urban split: 30% buildings, 70% infrastructure

Also manages raintank adoption scenarios for water infrastructure changes.

Parameters for both scenarios are configurable through thresholds:
- urbanization_threshold: Min pervious fraction for urbanizable areas
- urban_threshold: Min urban fraction for greening targets
- min_pavement_fraction: Required infrastructure in urban areas
- roof_fraction: Building footprint in new developments 
- pavement_fraction: Infrastructure footprint in new developments
"""
from dataclasses import dataclass
from typing import Dict, Optional
from copy import deepcopy
import pandas as pd

@dataclass
class ForceScenario:
    """Configuration for force modification scenario"""
    name: str
    description: str
    # Climate modifications
    precipitation_factor: float = 1.0
    evaporation_factor: float = 1.0
    irrigation_factor: float = 1.0
    # New force profiles (Optional)
    precipitation_profile: Optional[pd.Series] = None
    evaporation_profile: Optional[pd.Series] = None
    irrigation_profile: Optional[pd.Series] = None

    @classmethod
    def from_config(cls, name: str, config: dict) -> 'ForceScenario':
        """Create scenario from config dictionary"""
        return cls(
            name=name,
            description=config.get('description', ''),
            precipitation_factor=config.get('precipitation_factor', 1.0),
            evaporation_factor=config.get('evaporation_factor', 1.0),
            irrigation_factor=config.get('irrigation_factor', 1.0),
            precipitation_profile=config.get('precipitation_profile'),
            irrigation_profile=config.get('irrigation_profile')
        )

@dataclass
class AreaScenario:
    """
       Configuration for urban transformation scenarios.

       Args:
           name: Scenario identifier
           description: Detailed scenario description
           pervious_ratio: Change in pervious area (positive=greening, negative=urbanization)
           raintank_adoption: Change in raintank implementation rate
           urbanization_threshold: Min pervious fraction for urbanization (default 0.7)
           urban_threshold: Min urban fraction for greening (default 0.7)
           min_pavement_fraction: Required urban infrastructure (default 0.2)
           roof_fraction: Building ratio in new developments (default 0.3)
           pavement_fraction: Infrastructure ratio in new developments (default 0.7)
    """
    name: str
    description: str
    pervious_ratio: Optional[float] = None
    raintank_adoption: Optional[float] = None
    urbanization_threshold: float = 0.7
    urban_threshold: float = 0.7
    min_pavement_fraction: float = 0.2
    roof_fraction: float = 0.3
    pavement_fraction: float = 0.7

    @classmethod
    def from_config(cls, name: str, config: dict) -> 'AreaScenario':
        return cls(
            name=name,
            description=config.get('description', ''),
            pervious_ratio=config.get('pervious_ratio'),
            raintank_adoption=config.get('raintank_adoption'),
            urbanization_threshold=config.get('urbanization_threshold', 0.7),
            urban_threshold=config.get('urban_threshold', 0.7),
            min_pavement_fraction=config.get('min_pavement_fraction', 0.2),
            roof_fraction=config.get('roof_fraction', 0.3),
            pavement_fraction=config.get('pavement_fraction', 0.7)
        )

class ScenarioManager:
    def __init__(self, base_config: dict, base_params: dict):
        self.base_config = deepcopy(base_config)
        self.base_params = deepcopy(base_params)
        self.force_scenarios: Dict[str, ForceScenario] = {}
        self.area_scenarios: Dict[str, AreaScenario] = {}

    @classmethod
    def from_config(cls, config: dict, base_params: dict) -> 'ScenarioManager':
        """Create ScenarioManager from config"""
        manager = cls(config, base_params)

        if 'scenarios' in config and config.scenarios.get('enabled', False):
            for scenario_name, scenario_config in config.scenarios.items():
                if scenario_name != 'enabled':
                    if scenario_config.get('type') == 'force':
                        scenario = ForceScenario.from_config(scenario_name, scenario_config)
                        manager.force_scenarios[scenario_name] = scenario
                    elif scenario_config.get('type') == 'area':
                        scenario = AreaScenario.from_config(scenario_name, scenario_config)
                        manager.area_scenarios[scenario_name] = scenario

        return manager

    def add_force_scenario(self, scenario: ForceScenario) -> None:
        """Add a new force scenario to the manager"""
        self.force_scenarios[scenario.name] = scenario

    def add_area_scenario(self, scenario: AreaScenario) -> None:
        """Add a new area scenario to the manager"""
        self.area_scenarios[scenario.name] = scenario

    def modify_forcing(self, forcing: pd.DataFrame, scenario: ForceScenario) -> pd.DataFrame:
        """
            Modify model parameters according to urban transformation scenario.

            Args:
                params: Original model parameters
                scenario: Urban transformation scenario

            Returns:
                Modified parameter set reflecting scenario changes

            Notes:
                - Greening only applies to highly urban areas
                - Urbanization only applies to mostly pervious areas
                - Maintains minimum infrastructure requirements
        """
        modified = forcing.copy()

        # Apply factors
        modified['precipitation'] *= scenario.precipitation_factor
        modified['potential_evaporation'] *= scenario.evaporation_factor

        # Replace with new profiles if provided
        if scenario.precipitation_profile is not None:
            modified['precipitation'] = scenario.precipitation_profile
        if scenario.evaporation_profile is not None:
            modified['potential_evaporation'] = scenario.evaporation_profile

        return modified

    def modify_params(self, params: dict, scenario: AreaScenario) -> dict:
        """Modify model parameters according to area scenario"""
        modified = deepcopy(params)

        for cell_id, cell_params in modified.items():
            total_area = cell_params['pervious']['area'] + cell_params['roof']['area'] + cell_params['pavement']['area']
            pervious_fraction = cell_params['pervious']['area'] / total_area
            urban_fraction = (cell_params['roof']['area'] + cell_params['pavement']['area']) / total_area
            min_pavement = total_area * scenario.min_pavement_fraction

            if scenario.pervious_ratio:
                if scenario.pervious_ratio > 0 and urban_fraction > scenario.urban_threshold:
                    available_pavement = cell_params['pavement']['area'] - min_pavement
                    if available_pavement > 0:
                        area_change = min(cell_params['pervious']['area'] * scenario.pervious_ratio, available_pavement)
                        cell_params['pervious']['area'] += area_change
                        cell_params['pavement']['area'] -= area_change

                elif scenario.pervious_ratio < 0 and pervious_fraction > scenario.urbanization_threshold:
                    area_reduction = abs(cell_params['pervious']['area'] * scenario.pervious_ratio)
                    cell_params['pervious']['area'] -= area_reduction
                    cell_params['roof']['area'] += area_reduction * scenario.roof_fraction
                    cell_params['pavement']['area'] += area_reduction * scenario.pavement_fraction

            if scenario.raintank_adoption:
                current_adoption = cell_params['raintank']['install_ratio']
                cell_params['raintank']['install_ratio'] = current_adoption * (1 + scenario.raintank_adoption)
                cell_params['raintank']['install_ratio'] = min(100, max(0, cell_params['raintank']['install_ratio']))

        return modified

    def run_scenario(self, scenario_name: str, model_runner, forcing_data: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """Run a specific scenario"""
        if scenario_name in self.force_scenarios:
            scenario = self.force_scenarios[scenario_name]
            modified_forcing = self.modify_forcing(forcing_data, scenario)
            results = model_runner(self.base_config, self.base_params, modified_forcing)
        elif scenario_name in self.area_scenarios:
            scenario = self.area_scenarios[scenario_name]
            modified_params = self.modify_params(self.base_params, scenario)
            results = model_runner(self.base_config, modified_params, forcing_data)
        else:
            raise ValueError(f"Unknown scenario: {scenario_name}")

        return results

    def run_all_scenarios(self, model_runner, forcing_data: pd.DataFrame) -> Dict[str, Dict[str, pd.DataFrame]]:
        """Run all registered scenarios and return their results"""
        results = {}
        for name in self.force_scenarios:
            results[name] = self.run_scenario(name, model_runner, forcing_data)
        for name in self.area_scenarios:
            results[name] = self.run_scenario(name, model_runner, forcing_data)
        return results