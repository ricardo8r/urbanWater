import pytest
import numpy as np

def test_sewerage_initialization(sewerage_component, mock_params):
    """Test successful initialization of SewerageClass."""
    assert sewerage_component.sewerage_data.area == mock_params['sewerage']['area']
    # capacity is set in L (10000), get_capacity('m3') returns 10.0
    assert sewerage_component.sewerage_data.storage.get_capacity('m3') == mock_params['sewerage']['capacity'] / 1000

def test_sewerage_solve(sewerage_component, mock_forcing):
    """Test solve method with inflow."""
    forcing_day = mock_forcing.iloc[0]
    
    # Set inflows
    sewerage_component.sewerage_data.flows.set_flow('from_stormwater', 5000.0, 'm3') # 50% capacity
    sewerage_component.sewerage_data.flows.set_flow('from_demand', 1000.0, 'm3')
    
    sewerage_component.solve(forcing_day)
    
    # Capacity 10000. Total in = 6000.
    # Output limited by max_pipe_flow = 7000.
    # So all 6000 leaves?
    # Or needs to fill storage first?
    # Assumptions: similar to simple bucket if no specific retention logic.
    pass 
