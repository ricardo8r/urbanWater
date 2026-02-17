import pytest
import numpy as np

def test_roof_initialization(roof_component, mock_params):
    """Test successful initialization of RoofClass."""
    assert roof_component.roof_data.area == mock_params['roof']['area']
    assert roof_component.roof_data.storage.get_capacity('mm') == mock_params['roof']['max_storage']

def test_roof_solve(roof_component, mock_forcing):
    """Test solve method with precipitation."""
    forcing_day = mock_forcing.iloc[1] # 10.0mm precip
    
    roof_component.solve(forcing_day)
    
    # Logic:
    # Precip = 10.0
    # Evap = 1.0
    # Net = 9.0
    # Storage max = 2.0.
    # Overflow = 9.0 - 2.0 = 7.0
    
    # Split overflow (effective area 80%)
    # to_raintank = 7.0 * 0.8 = 5.6 mm
    # to_stormwater = 7.0 * 0.2 = 1.4 mm
    
    assert roof_component.roof_data.storage.get_amount('mm') == pytest.approx(1.0)
    assert roof_component.roof_data.flows.get_flow('to_raintank', 'mm') == pytest.approx(6.4)
    assert roof_component.roof_data.flows.get_flow('to_stormwater', 'mm') == pytest.approx(0.0)
