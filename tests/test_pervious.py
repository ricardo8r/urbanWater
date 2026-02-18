import pytest
import numpy as np

def test_pervious_initialization(pervious_component, mock_params):
    """Test successful initialization of PerviousClass."""
    assert pervious_component.pervious_data.area == mock_params['pervious']['area']
    assert pervious_component.pervious_data.storage.get_capacity('mm') == mock_params['pervious']['max_storage']

def test_pervious_solve_dry(pervious_component, mock_forcing):
    """Test solve method with no precipitation."""
    forcing_day = mock_forcing.iloc[0] # Precip=0, PotEvap=2.0
    
    pervious_component.pervious_data.storage.set_previous(1.0, 'mm')
    
    pervious_component.solve(forcing_day)
    
    # Evap 1.0mm (limited by storage)
    # Since storage was 1.0, and Evap 2.0 -> Evap should be 1.0?
    # Logic check:
    # current_storage = max(0, 1.0 + 0) = 1.0.
    # infiltration? Depends on vadose state.
    # mock_params: inf_cap=35.
    # available_space in vadose? Mocked?
    # conftest mocks PerviousClass initialization but doesn't mock vadose moisture state directly unless we access it.
    # `pervious_component` fixture in step 77 sets vadose_moisture area.
    # Initial moisture is 0.0??
    # `self.pervious_data.vadose_moisture.set_previous(..., 'mm')`. 
    # Not set in fixture. Defaults to 0.0.
    # `moisture_root_capacity` from soil_selector. Mock soil returns ~60mm.
    # available_space = 60 - 0 = 60mm.
    # infiltration_capacity = min(35, 60 + ...) = 35.
    
    # Time factor?
    # evap + inf = 1.0 (since denom = 2.0 + 35.0 = 37.0).
    # current_storage / denom = 1.0 / 37.0.
    # evap = time_factor * 2.0 = 1.0/37.0 * 2.0 = 0.054.
    # inf = time_factor * 35.0 = 1.0/37.0 * 35.0 = 0.946.
    
    # Wait, pervious logic uses time factor if total potential > storage?
    # Logic in pervious.py (step 32):
    # denominator = evap + infiltration_capacity
    # time_factor = min(1.0, current_storage / denominator)
    # outputs = time_factor * potentials.
    
    # So if storage (1.0) < denom (37.0), then factor = 1/37.
    # Outputs sum to 1.0.
    # Evap is negligible fraction. Infiltration is dominant.
    
    # Assert
    # Evaporation small but non-zero
    assert pervious_component.pervious_data.flows.get_flow('evaporation', 'mm') > 0.0
    assert pervious_component.pervious_data.flows.get_flow('evaporation', 'mm') < 0.1
    # Storage should be empty?
    # flow_out = (evap + inf) = 1.0. 
    # Remaining = 1.0 - 1.0 = 0.0.
    assert pervious_component.pervious_data.storage.get_amount('mm') == pytest.approx(0.0)

def test_pervious_solve_infiltration_limit(pervious_component, mock_forcing):
    """Test solve method where infiltration capacity limits input."""
    # Use heavy rain day (index 4: 20.0mm) + some inflow from impervious
    forcing_day = mock_forcing.iloc[4]
    
    # Set previous storage to 0
    pervious_component.pervious_data.storage.set_previous(0.0, 'mm')
    
    # Add upstream inflow from impervious (e.g., 0.1 m3 -> 0.1/200m2 = 0.5mm)
    pervious_component.pervious_data.flows.set_flow('from_impervious', 0.1, 'm3')
    
    # Total input: 20.0 (precip) + 0.5 (runon) = 20.5 mm
    # Infiltration capacity = 35.0 mm/d (mock_params)
    # Storage max = 8.0 mm
    
    # Vadose moisture (mocked in logic via linked object, checked above). 
    # If vadose is empty (0.0), capacity is high.
    
    # Run
    pervious_component.solve(forcing_day)
    
    data = pervious_component.pervious_data
    
    # Check consistency
    precip = data.flows.get_flow('precipitation', 'mm')
    runon = data.flows.get_flow('from_impervious', 'mm')
    store_change = data.storage.get_change('mm')
    evap = data.flows.get_flow('evaporation', 'mm')
    inf = data.flows.get_flow('to_vadose', 'mm')
    runoff = data.flows.get_flow('to_stormwater', 'mm') 
    
    input_total = precip + runon
    output_total = evap + inf + runoff + store_change
    
    assert input_total == pytest.approx(output_total, abs=1e-5)

def test_pervious_solve_saturation(pervious_component, mock_forcing):
    """Test saturation excess runoff."""
    forcing_day = mock_forcing.iloc[4] # 20mm
    
    # Fill storage to MAX
    max_storage = 8.0
    pervious_component.pervious_data.storage.set_previous(max_storage, 'mm')
    
    # We want to force runoff.
    # Infiltration capacity is 35.0.
    # Input 20.0. 
    # If infiltration consumes everything, no runoff happens unless rate limit is hit.
    # But infiltration capacity > input.
    # So all input infiltrates... EXCEPT if vadose is full?
    
    # Let's fill vadose manually to reduce infiltration capacity to 0.
    # In `PerviousClass`, `available_space = max(0, moisture_root_capacity - vadose_moisture.get_previous())`
    # We need to set `vadose_moisture.previous` to `moisture_root_capacity`.
    # `moisture_root_capacity` is from `soil_params['moist_cont_eq_rz[mm]']`.
    # For mock_soil_df type 1: 61.6mm.
    
    # How to access vadose moisture from pervious component?
    # It is linked: `pervious_data.vadose_moisture`.
    pervious_component.pervious_data.vadose_moisture.set_previous(100.0, 'mm') # Set high to ensure 0 space.
    
    pervious_component.solve(forcing_day)
    
    # Infiltration capacity should be 0.
    # Evap (0.5mm pot) -> should happen.
    # Runoff = Input + Previous - Evap - MaxStorage (since Inf=0)
    # Input = 20.0. Previous = 8.0.
    # Evap = 0.5.
    # Net = 27.5.
    # Capped at 8.0.
    # Runoff = 19.5?
    
    assert pervious_component.pervious_data.flows.get_flow('to_vadose', 'mm') == pytest.approx(0.0)
    assert pervious_component.pervious_data.flows.get_flow('to_stormwater', 'mm') > 0.0

def test_pervious_water_balance(pervious_component, mock_forcing):
    """Test water balance conservation in PerviousClass."""
    forcing_day = mock_forcing.iloc[1] # 10.0mm precip
    
    # Initial state
    initial_storage = 4.0 # mm (half full)
    pervious_component.pervious_data.storage.set_previous(initial_storage, 'mm')
    
    # Inflows
    pervious_component.pervious_data.flows.set_flow('from_roof', 1.0, 'mm')
    pervious_component.pervious_data.flows.set_flow('from_impervious', 2.0, 'mm')
    
    # Run
    pervious_component.solve(forcing_day)
    
    # Verify
    precip = pervious_component.pervious_data.flows.get_flow('precipitation', 'mm')
    from_roof = pervious_component.pervious_data.flows.get_flow('from_roof', 'mm')
    from_imp = pervious_component.pervious_data.flows.get_flow('from_impervious', 'mm')
    # Demand irrgation? forcing doesn't have it set, defaults to 0.
    irrig = pervious_component.pervious_data.flows.get_flow('from_demand', 'mm')
    
    evap = pervious_component.pervious_data.flows.get_flow('evaporation', 'mm')
    infiltration = pervious_component.pervious_data.flows.get_flow('to_vadose', 'mm')
    runoff = pervious_component.pervious_data.flows.get_flow('to_stormwater', 'mm')
    
    final_storage = pervious_component.pervious_data.storage.get_amount('mm')
    delta = final_storage - initial_storage
    
    total_in = precip + from_roof + from_imp + irrig
    total_out = evap + infiltration + runoff
    
    assert delta == pytest.approx(total_in - total_out, abs=1e-9)

