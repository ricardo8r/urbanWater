import pytest
import pandas as pd
import numpy as np
import sys
import os
from pathlib import Path
import warnings

# Filter the specific DeprecationWarning from geopandas/shapely immediately
warnings.filterwarnings("ignore", message="The 'shapely.geos' module is deprecated")

# Add project root to sys.path
# Assuming tests/ is at the root of the project
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from urbanWater.data_structures import UrbanWaterData
from urbanWater.components.impervious import ImperviousClass
from urbanWater.components.pervious import PerviousClass
from urbanWater.components.roof import RoofClass
from urbanWater.components.vadose import VadoseClass
from urbanWater.components.groundwater import GroundwaterClass
from urbanWater.components.stormwater import StormwaterClass
from urbanWater.components.sewerage import SewerageClass
from urbanWater.components.demand import DemandClass
from urbanWater.components.raintank import RainTankClass
from urbanWater.functions import soil_selector # Import the real one or mock it

# Mock data fixtures

@pytest.fixture
def urban_water_data():
    """Create a fresh instance of UrbanWaterData for each test."""
    return UrbanWaterData()

@pytest.fixture
def mock_params():
    """Create a dictionary of mock parameters."""
    return {
        'general': {
            'time_step': 1.0,
            'number_houses': 10,
            'indoor_water_use': 300.0 # L/day
        },
        'impervious': {
            'area': 100.0,
            'effective_area': 50.0, # example: 50
            'max_storage': 2.0, # example: 2
            'infiltration_capacity': 5.0 # example: 5
        },
        'pervious': {
            'area': 200.0,
            'max_storage': 8.0, # example: 8
            'infiltration_capacity': 35.0 # example: 35
        },
        'roof': {
            'area': 150.0,
            'max_storage': 2.0, # example: 2
            'effective_area': 80.0, # example: 80
            'leakage_rate': 0.0
        },
        'raintank': {
            'is_open': False,
            'area': 250.0,
            'capacity': 5000.0, # Liters
            'initial_storage': 0.0, 
            'first_flush': 2.0, 
            'effective_area': 80.0, # example: 80
            'install_ratio': 50.0 
        },
        'vadose': {
            'area': 200.0,
            'initial_moisture': 50.0
        },
        'groundwater': {
            'area': 200.0,
            'initial_level': 2.0,
            'leakage_rate': 2.5, # example: 2.5
            'seepage_model': 0, # constant
            'drainage_resistance': 25.0, # example: 25
            'seepage_resistance': 200.0, # example: 200
            'infiltration_recession': 0.0000015, # example: 0.0000015
            'hydraulic_head': 1.0,
            'downward_seepage': 1.4 # example: 1.4
        },
        'stormwater': {
            'is_open': True,
            'area': 100.0,
            'capacity': 1000.0, 
            'initial_storage': 0.0,
            'first_flush': 2.0, 
            'wastewater_runoff_per': 95.0 # example: 95
        },
        'sewerage': {
            'area': 1000.0, 
            'capacity': 10000.0, 
            'initial_storage': 0.0,
            'max_pipe_flow': 7000.0 # example: 7000
        },

        'reuse': {
            'area': 1000.0, 
            'capacity': 5000.0 
        },
        'irrigation': {
             'pervious': 1.0
        },
        'soil': {
            'soil_type': 1,
            'crop_type': 6 # example: 6
        }
    }

@pytest.fixture
def mock_forcing():
    """Create a mock forcing DataFrame."""
    dates = pd.date_range(start='2020-01-01', periods=5, freq='D')
    # Use simple values for easy verification
    data = {
        'precipitation': [0.0, 10.0, 5.0, 0.0, 20.0],
        'potential_evaporation': [2.0, 1.0, 1.5, 3.0, 0.5],
        'irrigation': [0.0, 0.0, 0.0, 0.0, 0.0],
        'roof_irrigation': [0.0, 0.0, 0.0, 0.0, 0.0],
        'pervious_irrigation': [0.0, 0.0, 0.0, 0.0, 0.0],
        'impervious_irrigation': [0.0, 0.0, 0.0, 0.0, 0.0]
    }
    return pd.DataFrame(data, index=dates)

@pytest.fixture
def mock_soil_df():
    """Create a mock soil DataFrame compatible with soil_selector."""
    # Data for dry soil (gwl=0, top) to wet (gwl=2+)
    # Using Soil Type 1 values from example
    data = {
        'soil_type': [1] * 30,
        'th_rz': [60] * 30, # Match et_data th_rz_m * 100 = 0.6 * 100 = 60
        'k_sat': [6.67] * 30,
        'moist_cont_eq_rz[mm]': [61.6 - (i * 0.5) for i in range(30)], # Decreasing moisture with depth/gwl proxy
        'stor_coef': [0.001 + (i * 0.01) for i in range(30)], # Increasing storage coef
        'capris_max[mm/d]': [5.0 if i < 10 else 0.5 for i in range(30)] # 5.0 at top, dropping to 0.5
    }
    return pd.DataFrame(data)

@pytest.fixture
def mock_et_df():
    """Create a mock evapotranspiration DataFrame compatible with et_selector."""
    # Values for Soil 1, Crop 6
    return pd.DataFrame({
        'soil_type': [1],
        'crop_type': [6],
        'th_rz_m': [0.6],
        'theta_h1_mm': [387.6],
        'theta_h2_mm': [367.9],
        'theta_h3h_mm': [262.3],
        'theta_h3l_mm': [242.1],
        'theta_h4_mm': [159.7]
    })

# Component fixtures

@pytest.fixture
def impervious_component(mock_params, urban_water_data):
    """Initialize ImperviousClass with mock data."""
    return ImperviousClass(mock_params, urban_water_data.impervious)

@pytest.fixture
def pervious_component(mock_params, mock_soil_df, mock_et_df, urban_water_data):
    """Initialize PerviousClass with mock data."""
    # Since we are providing compatible dataframes, we can use the real class init
    # which calls the real soil_selector.
    comp = PerviousClass(mock_params, mock_soil_df, mock_et_df, urban_water_data.pervious)
    
    # PerviousClass depends on vadose_moisture having area set (usually done by VadoseClass)
    # Since we test in isolation, we must set it here.
    comp.pervious_data.vadose_moisture.set_area(mock_params['pervious']['area'])
    
    return comp

@pytest.fixture
def roof_component(mock_params, urban_water_data):
    """Initialize RoofClass with mock data."""
    return RoofClass(mock_params, urban_water_data.roof)


@pytest.fixture
def raintank_component(mock_params, urban_water_data):
    """Initialize RainTankClass with mock data."""
    return RainTankClass(mock_params, urban_water_data.raintank)

@pytest.fixture
def vadose_component(mock_params, mock_soil_df, mock_et_df, urban_water_data):
    """Initialize VadoseClass with mock data."""
    # Similar to Pervious, Vadose relies on Groundwater Level.
    # In isolation, we may need to mock groundwater level previous state.
    comp = VadoseClass(mock_params, mock_soil_df, mock_et_df, urban_water_data.vadose)
    # Set initial groundwater level in linked data structure if needed
    comp.vadose_data.groundwater_level.set_area(mock_params['groundwater']['area'])
    comp.vadose_data.groundwater_level.set_previous(2.0, 'm')
    return comp

@pytest.fixture
def groundwater_component(mock_params, mock_soil_df, mock_et_df, urban_water_data):
    """Initialize GroundwaterClass with mock data."""
    return GroundwaterClass(mock_params, mock_soil_df, mock_et_df, urban_water_data.groundwater)

@pytest.fixture
def stormwater_component(mock_params, urban_water_data):
    """Initialize StormwaterClass with mock data."""
    return StormwaterClass(mock_params, urban_water_data.stormwater)

@pytest.fixture
def sewerage_component(mock_params, urban_water_data):
    """Initialize SewerageClass with mock data."""
    return SewerageClass(mock_params, urban_water_data.sewerage)


@pytest.fixture
def mock_demand_settings():
    return pd.DataFrame({
        'kitchen': [15.75],
        'bathroom': [32.75],
        'toilet': [30.75],
        'laundry': [20.75]
    })

@pytest.fixture
def mock_reuse_settings():
    return pd.DataFrame({
        'kitchen_to_graywater': [15.0],
        'bathroom_to_graywater': [25.0],
        'laundry_to_graywater': [15.0],
        'raintank_to_kitchen': [25.0],
        'raintank_to_bathroom': [25.0],
        'raintank_to_laundry': [25.0],
        'raintank_to_toilet': [25.0],
        'raintank_to_irrigation': [0.0],
        'wastewater_to_toilet': [0.0],
        'wastewater_to_irrigation': [0.0]
    })

@pytest.fixture
def demand_component(mock_params, mock_demand_settings, mock_reuse_settings, urban_water_data):
    """Initialize DemandClass with mock data."""
    return DemandClass(mock_params, mock_demand_settings, mock_reuse_settings, urban_water_data.demand)
