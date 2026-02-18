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
    
    # Set inflows: 5000L + 1000L = 6000L = 6.0m3
    sewerage_component.sewerage_data.flows.set_flow('from_stormwater', 5000.0, 'L') 
    sewerage_component.sewerage_data.flows.set_flow('from_demand', 1000.0, 'L')
    
    # Run solve
    sewerage_component.solve(forcing_day)
    
    # Capacity is 10.0 m3. 
    # Total inflow 6.0 m3.
    # Logic in Sewerage: 
    # storage = min(capacity, previous + inflow) -> min(10, 0+6) = 6.
    # discharge = max(0, total_inflow - storage_change) 
    #           = max(0, 6 - (6-0)) = 0?
    
    # Wait, let's re-read sewerage.py logic from step 29:
    # total_inflow = sum(inflows)
    # data.storage.set_amount(min(capacity, previous + total_inflow))
    # discharge = max(0.0, total_inflow - data.storage.get_change('m3'))
    
    # So if capacity is large enough, it stores everything?
    # Yes, it seems so. It acts as a storage that overflows.
    # But usually sewerage is a pipe that transmits? 
    # The comment says "Simulates cluster sewerage storage dynamics."
    # So it is a storage tank/pipe volume.
    
    assert sewerage_component.sewerage_data.storage.get_amount('m3') == pytest.approx(6.0)
    assert sewerage_component.sewerage_data.flows.get_flow('to_downstream', 'm3') == pytest.approx(0.0)

def test_sewerage_water_balance(sewerage_component, mock_forcing):
    """Test water balance conservation in SewerageClass."""
    forcing_day = mock_forcing.iloc[0]
    
    # Initial state
    initial_storage = 2.0 # m3
    sewerage_component.sewerage_data.storage.set_previous(initial_storage, 'm3')
    
    # Flows in
    inflow_stormwater = 5.0 # m3
    inflow_demand = 1.0 # m3
    sewerage_component.sewerage_data.flows.set_flow('from_stormwater', inflow_stormwater, 'm3')
    sewerage_component.sewerage_data.flows.set_flow('from_demand', inflow_demand, 'm3')
    
    # Run
    sewerage_component.solve(forcing_day)
    
    # Final state
    final_storage = sewerage_component.sewerage_data.storage.get_amount('m3')
    outflow_downstream = sewerage_component.sewerage_data.flows.get_flow('to_downstream', 'm3')
    
    # Balance: ΔStorage = In - Out
    # Change in storage (Current - Previous)
    # The component calculates change based on previous.
    change_storage = final_storage - initial_storage
    
    total_in = inflow_stormwater + inflow_demand
    total_out = outflow_downstream
    
    assert change_storage == pytest.approx(total_in - total_out, abs=1e-9)

    # Test Overflow case
    # Capacity is 10.0 m3. 
    # Use set_previous to set state before solve.
    sewerage_component.sewerage_data.storage.set_previous(8.0, 'm3')
    sewerage_component.sewerage_data.flows.set_flow('from_stormwater', 50.0, 'm3') # huge
    # Reset other flows to 0 or keep them? 
    # NOTE: set_flow sets the value. demand is still 1.0 unless reset.
    sewerage_component.sewerage_data.flows.set_flow('from_demand', 0.0, 'm3')
    
    sewerage_component.solve(forcing_day)
    
    final_storage_2 = sewerage_component.sewerage_data.storage.get_amount('m3')
    outflow_2 = sewerage_component.sewerage_data.flows.get_flow('to_downstream', 'm3')
    
    # Should be full
    assert final_storage_2 == pytest.approx(10.0) # Capacity
    # Balance check
    change_storage_2 = final_storage_2 - 8.0
    total_in_2 = 50.0 + 0.0 
    
    assert change_storage_2 == pytest.approx(total_in_2 - outflow_2, abs=1e-9)
