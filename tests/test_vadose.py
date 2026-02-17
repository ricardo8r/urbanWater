import pytest
import numpy as np

def test_vadose_initialization(vadose_component, mock_params):
    """Test successful initialization of VadoseClass."""
    assert vadose_component.vadose_data.area == mock_params['vadose']['area']
    assert vadose_component.vadose_data.moisture.get_previous('mm') == mock_params['vadose']['initial_moisture']
    
    # k_sat = 6.67 -> saturated_conductivity = 66.7 (fixed expectation)
    assert vadose_component.saturated_conductivity == pytest.approx(66.7)

def test_vadose_solve_no_infiltration(vadose_component, mock_forcing):
    """Test solve method with no infiltration from pervious."""
    forcing_day = mock_forcing.iloc[0] # pot evap 2.0
    
    # Reset state
    vadose_component.vadose_data.flows.set_flow('from_pervious', 0.0, 'mm')
    
    vadose_component.solve(forcing_day)
    
    data = vadose_component.vadose_data
    flows = data.flows
    
    # Transpiration (0.0 due to dry soil below wilting point)
    assert flows.get_flow('transpiration', 'mm') == pytest.approx(0.0)
    
    # Percolation (negative due to capillary rise)
    # Max capillary = 0.5 (mock_soil_df at depth 2.0m/index 20)
    # Percolation = -0.5
    assert flows.get_flow('to_groundwater', 'mm') == pytest.approx(-0.5)
    
    # Final moisture = 50.0 - 0.0 - (-0.5) = 50.5
    assert data.moisture.get_amount('mm') == pytest.approx(50.5)
