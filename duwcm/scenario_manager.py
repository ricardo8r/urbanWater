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

import logging
from joblib import Parallel, delayed
from dynaconf import Dynaconf
import pandas as pd

from duwcm.forcing import distribute_irrigation
from duwcm.water_model import UrbanWaterModel
from duwcm.water_balance import run_water_balance
from duwcm.diagnostics import DiagnosticTracker
from duwcm.utils import is_notebook

logger = logging.getLogger(__name__)

@dataclass
class Scenario:
    """Encapsulates model scenario parameters"""
    name: str
    description: str

    # Climate modifications
    precipitation_factor: float = 1.0
    evaporation_factor: float = 1.0
    irrigation_factor: float = 1.0
    open_water_factor: float = 1.0
    demand_factor: float = 1.0
    groundwater_factor: float = 1.0

    # Urban modifications
    pervious_ratio: Optional[float] = None
    raintank_adoption: Optional[float] = None

    # Infrastructure thresholds
    urbanization_threshold: float = 0.7
    urban_threshold: float = 0.7
    min_pavement_fraction: float = 0.2
    roof_fraction: float = 0.3
    pavement_fraction: float = 0.7

    def update_from_dict(self, config_dict):
        """Update variables from config dict"""
        for key, value in config_dict.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def modify_forcing(self, forcing: pd.DataFrame) -> pd.DataFrame:
        """Apply scenario modifications to forcing data"""
        modified = forcing.copy()
        modified['precipitation'] *= self.precipitation_factor
        modified['potential_evaporation'] *= self.evaporation_factor
        modified['open_water_level'] *= self.open_water_factor
        modified['pervious_irrigation'] *= self.irrigation_factor
        modified['impervious_irrigation'] *= self.irrigation_factor
        modified['roof_irrigation'] *= self.irrigation_factor
        return modified

    def modify_params(self, params: Dict) -> Dict:
        """Apply scenario modifications to model parameters"""
        modified = deepcopy(params)

        # Modify indoor water use
        if self.demand_factor != 1.0:
            for cell_id in modified:
                modified[cell_id]['general']['indoor_water_use'] *= self.demand_factor

        # Apply urban transformations if specified
        if self.pervious_ratio or self.raintank_adoption:
            for cell_id, cell_params in modified.items():
                self._modify_cell_params(cell_params)

        return modified

    def _modify_cell_params(self, cell_params: Dict) -> None:
        """Apply modifications to individual cell parameters"""
        total_area = (cell_params['pervious']['area'] +
                     cell_params['roof']['area'] +
                     cell_params['impervious']['area'])
        pervious_fraction = cell_params['pervious']['area'] / total_area
        urban_fraction = 1 - pervious_fraction

        if self.pervious_ratio:
            self._apply_urban_transformation(cell_params, total_area, pervious_fraction, urban_fraction)

        if self.raintank_adoption:
            self._modify_raintank_adoption(cell_params)

    def _apply_urban_transformation(self, cell_params: Dict, total_area: float,
                                  pervious_fraction: float, urban_fraction: float) -> None:
        """Apply urban transformation based on pervious ratio"""
        min_pavement = total_area * self.min_pavement_fraction

        # Greening scenario (positive ratio)
        if self.pervious_ratio > 0 and urban_fraction > self.urban_threshold:
            available_pavement = cell_params['impervious']['area'] - min_pavement
            if available_pavement > 0:
                area_change = min(cell_params['pervious']['area'] * self.pervious_ratio,
                                available_pavement)
                cell_params['pervious']['area'] += area_change
                cell_params['impervious']['area'] -= area_change

        # Urbanization scenario (negative ratio)
        elif self.pervious_ratio < 0 and pervious_fraction > self.urbanization_threshold:
            area_reduction = abs(cell_params['pervious']['area'] * self.pervious_ratio)
            cell_params['pervious']['area'] -= area_reduction
            cell_params['roof']['area'] += area_reduction * self.roof_fraction
            cell_params['impervious']['area'] += area_reduction * self.pavement_fraction

    def _modify_raintank_adoption(self, cell_params: Dict) -> None:
        """Modify raintank adoption rate"""
        current_adoption = cell_params['raintank']['install_ratio']
        new_adoption = current_adoption * (1 + self.raintank_adoption)
        cell_params['raintank']['install_ratio'] = min(100, max(0, new_adoption))

class ScenarioManager:
    """Manages and runs multiple urban water model scenarios"""

    def __init__(self):
        self.scenarios: Dict[str, Scenario] = {}

    @classmethod
    def from_config(cls, config: Dynaconf) -> 'ScenarioManager':
        """Create ScenarioManager from loaded config"""
        manager = cls()

        if not config.scenarios.enabled:
            return manager

        for name in config.scenarios.active_scenarios:
            if name == 'default':
                scenario = Scenario(
                    name=name,
                    description='default'
                )
                manager.add_scenario(scenario)
                continue

            scenario_config = getattr(config.scenarios, name)
            scenario = Scenario(
                name=name,
                description=scenario_config.description
            )
            scenario.update_from_dict(scenario_config)
            manager.add_scenario(scenario)

        return manager

    def add_scenario(self, scenario: Scenario) -> None:
        """Add a scenario to the manager"""
        self.scenarios[scenario.name] = scenario

    def get_scenario(self, name: str) -> Optional[Scenario]:
        """Get a scenario by name"""
        return self.scenarios.get(name)

    def run_scenarios(self, model_data: Dict, base_params: Dict, base_forcing: pd.DataFrame,
                      n_jobs: int = -1) -> Dict[str, Dict[str, pd.DataFrame]]:
        """Run scenarios in parallel"""
        # Prepare scenario parameters as a list
        scenario_names = []
        scenario_params = []

        if is_notebook():
            backend='threading'
            progress=True
        else:
            backend='loky'
            progress=False

        for idx, (name, scenario) in enumerate(self.scenarios.items()):
            scenario_names.append(name)
            modified_params = scenario.modify_params(base_params)
            modified_forcing = scenario.modify_forcing(base_forcing)
            scenario_params.append((name, modified_params, modified_forcing,
                                    model_data, None, idx, progress))

        # Run scenarios in parallel while preserving argument structure
        results_list = Parallel(n_jobs=n_jobs, backend=backend, verbose=0)(
            delayed(run_scenario)(params) for params in scenario_params
        )

        # Directly map results to scenario names
        results = dict(results_list)

        return results


def run_scenario(scenario_data):

    name, modified_params, modified_forcing, model_data, tracker, idx, progress = scenario_data

    distribute_irrigation(modified_params)
    model = UrbanWaterModel(
        params=modified_params,
        path=model_data['flow_paths'],
        soil_data=model_data['soil_data'],
        et_data=model_data['et_data'],
        demand_settings=model_data['demand_data'],
        reuse_settings=model_data['reuse_settings'],
        direction=model_data['direction']
    )
    results = run_water_balance(model, modified_forcing, tracker, idx, progress)
    return name, results