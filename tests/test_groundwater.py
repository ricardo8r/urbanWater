import pytest
import numpy as np

def test_groundwater_initialization(groundwater_component, mock_params):
    """Test successful initialization of GroundwaterClass."""
    assert groundwater_component.groundwater_data.area == mock_params['groundwater']['area']
    assert groundwater_component.groundwater_data.water_level.get_previous('m') == mock_params['groundwater']['initial_level']

def test_groundwater_solve_constant_flux(groundwater_component, mock_forcing):
    """Test solve method with constant flux model."""
    forcing_day = mock_forcing.iloc[0]
    
    # Ensure it runs without error (fixed IndexError)
    groundwater_component.solve(forcing_day)
    
    # Check basic outputs exist
    assert groundwater_component.groundwater_data.flows.get_flow('baseflow', 'm') is not None
    assert groundwater_component.groundwater_data.flows.get_flow('seepage', 'm') is not None
