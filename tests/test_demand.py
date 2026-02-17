import pytest
import numpy as np

def test_demand_initialization(demand_component, mock_params, mock_demand_settings):
    """Test successful initialization of DemandClass."""
    # Check demands dictionary setup
    # indoor_water = 300.0 L (mock_params fix)
    # kitchen = 15.75% * 300 = 47.25 L
    assert demand_component.demands['kitchen'].iloc[0] == 47.25

def test_demand_solve_allocation(demand_component, mock_forcing):
    """Test water allocation from raintank and potable water."""
    
    # Setup availability
    # Raintank has 5000L capacity, 0 initial (mock_params defaults).
    # Let's add some water to raintank storage for allocation
    demand_component.demand_data.rt_storage.set_capacity(5000.0, 'L')
    demand_component.demand_data.rt_storage.set_amount(100.0, 'L')
    
    # forcing
    forcing_day = mock_forcing.iloc[0]
    
    # Allocation Logic
    # Kitchen demand = 15.75% * 300 = 47.25 L
    # RT factor = 25%
    # Target RT allocation = 11.8125 L
    # Available = 100.0. Allocation successful.
    
    # Solve
    demand_component.solve(forcing_day)
    
    # Assertions
    # Check internal flows
    assert demand_component.demand_data.internal_flows.rt_to_kitchen.get_amount('L') == pytest.approx(11.8125)
