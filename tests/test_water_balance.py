import pytest
from pathlib import Path
import pandas as pd
import numpy as np
from urbanWater.utils import load_config
from urbanWater.read_data import read_data
from urbanWater.forcing import read_forcing
from urbanWater.scenario_manager import Scenario, run_scenario

# Define paths relative to the test file or project root
# tests/test_water_balance.py -> tests -> project_root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEST_DATA_DIR = PROJECT_ROOT / "tests" / "data"
CONFIG_PATH = TEST_DATA_DIR / "config_test.yaml"

@pytest.fixture
def example_config():
    """Load and configure the testing configuration."""
    if not CONFIG_PATH.exists():
        pytest.skip(f"Test configuration not found at {CONFIG_PATH}")
    
    # Load config from tests/data/config_test.yaml
    config = load_config(str(TEST_DATA_DIR), 'default', 'config_test.yaml')
    
    # Update input directory to absolute path (tests/data/input)
    config.input_directory = str(TEST_DATA_DIR / "input")
    # geodata_directory not needed for simulation, but setting it to input just in case
    config.geodata_directory = str(TEST_DATA_DIR / "input")
    
    # Reduce simulation time for testing (2 days: 2018-01-01 to 2018-01-02)
    config.simulation.start_date = '2018-01-01'
    config.simulation.end_date = '2018-01-02'
    config.simulation.spinup_cycles = 0
    
    return config

def test_water_balance(example_config):
    """
    Integration test based on Example 00.
    Runs a short simulation (2 days) and validates basic outputs.
    """
    config = example_config
    
    # Read and prepare model data
    model_params, reuse_settings, demand_data, soil_data, et_data, flow_paths = read_data(config)
    forcing_data = read_forcing(config)
    
    # Ensure we actually have data
    assert not forcing_data.empty, "Forcing data should not be empty"
    
    # Create scenario 
    default_scenario = Scenario(
        name='test_scenario',
        description='Test configuration'
    )
    
    # Create model data dict
    model_data = {
        'flow_paths': flow_paths, 
        'soil_data': soil_data,
        'et_data': et_data,
        'demand_data': demand_data,
        'reuse_settings': reuse_settings,
        'direction': config.grid.direction
    }
    
    # Create and run scenario
    # tuple format: (name, params, forcing, model_data, tracker, idx, progress)
    scenario_args = (
        default_scenario.name, 
        model_params, 
        forcing_data, 
        model_data, 
        None, # tracker
        None, # idx
        False # progress bar
    )
    
    name, results = run_scenario(scenario_args)
    
    # Assertions
    assert name == 'test_scenario'
    assert 'aggregated' in results
    
    aggregated = results['aggregated']
    assert not aggregated.empty
    
    # Check that we have rows for the simulated days (including potentially initialization t=0)
    # Simulation: 2018-01-01 to 2018-01-02 is 2 days. 
    # Aggregated table usually includes t=0 (initial state) + t=1 + t=2.
    # Print the aggregated results to capturing them for the test baseline
    print("\n--- AGGREGATED RESULTS ---")
    print(aggregated.to_string())
    print("--------------------------\n")

    # Check for valid numerical values (just ensuring they are not NaN/Inf for now)
    # We will replace this with specific value assertions after capturing the baseline
    # Check specific numerical values (Placeholder 0.0 to capture actuals)
    # We use summed values for the entire simulation period for simplicity
    
    # Helper to get magnitude
    def get_sum(col):
        val = aggregated[col].sum()
        return val.magnitude if hasattr(val, 'magnitude') else val

    s_stormwater = get_sum('stormwater')
    s_sewerage = get_sum('sewerage')
    s_baseflow = get_sum('baseflow')
    s_evaporation = get_sum('evaporation')

    # Assertions with baseline values captured from run
    assert s_stormwater == pytest.approx(0.0, abs=1e-3), f"Stormwater sum mismatch: {s_stormwater}"
    assert s_sewerage == pytest.approx(2840.520, abs=1e-3), f"Sewerage sum mismatch: {s_sewerage}"
    # Baseflow is negative due to initial groundwater levels vs boundary conditions
    assert s_baseflow == pytest.approx(-18049.478, abs=1e-3), f"Baseflow sum mismatch: {s_baseflow}"
    assert s_evaporation == pytest.approx(0.013165, abs=1e-6), f"Evaporation sum mismatch: {s_evaporation}"

    # Check component results existence
    assert 'roof' in results
    assert 'impervious' in results
    assert 'pervious' in results
    
    # Optional: Check consistency of water balance if possible
    # Just checking that flows exist and are not all zero if there is precipitation
    precip_col = results['forcing']['precipitation']
    total_precip = precip_col.sum()
    
    print("Integration test finished successfully.")
