import pytest
import numpy as np

def test_roof_initialization(roof_component, mock_params):
    """Test successful initialization of RoofClass."""
    assert roof_component.roof_data.area == mock_params['roof']['area']
    assert roof_component.roof_data.storage.get_capacity('mm') == mock_params['roof']['max_storage']

def test_roof_solve(roof_component, mock_forcing):
    """Test solve method with precipitation."""
    forcing_day = mock_forcing.iloc[1] # 10.0mm precip, 1.0 pot evap
    
    # Set initial state
    roof_component.roof_data.storage.set_previous(0.0, 'mm')
    
    # Add irrigation (from demand)
    # forcing['roof_irrigation'] is 0.0 in mock
    # So Total Inflow = 10.0 mm
    
    roof_component.solve(forcing_day)
    
    # Logic verification:
    # Precip = 10.0
    # Evap = 1.0
    # Capped Storage (intermediate) = min(2.0, 0.0 + 10.0) = 2.0.
    # Actual Evap = min(1.0, 2.0) = 1.0.
    # Final Storage = 2.0 - 1.0 = 1.0.
    
    # Excess calculation (Runoff):
    # excess = Inflow (10) - Evap (1) - ΔStorage (1) = 8.0.
    
    # Split overflow (effective area 80%)
    # to_raintank = 8.0 * 0.8 = 6.4 mm
    # to_pervious = 8.0 * 0.2 = 1.6 mm
    
    assert roof_component.roof_data.storage.get_amount('mm') == pytest.approx(1.0)
    assert roof_component.roof_data.flows.get_flow('to_raintank', 'mm') == pytest.approx(6.4)
    assert roof_component.roof_data.flows.get_flow('to_pervious', 'mm') == pytest.approx(1.6)
    assert roof_component.roof_data.flows.get_flow('to_stormwater', 'mm') == pytest.approx(0.0)
    
def test_roof_water_balance(roof_component, mock_forcing):
    """Test water balance conservation in RoofClass."""
    forcing_day = mock_forcing.iloc[1] # 10.0mm precip
    
    # Check 1: Start empty
    roof_component.roof_data.storage.set_previous(0.0, 'mm')
    
    # We can add irrigation manually to stress inputs
    irrigation = 2.0 # mm
    roof_component.roof_data.flows.set_flow('from_demand', irrigation, 'mm')
    # Note: `solve` overwrites `from_demand` from `forcing.get('roof_irrigation')`!
    # roof.py line 60: `data.flows.set_flow('from_demand', forcing.get('roof_irrigation', 0.0), 'mm')`
    # So setting it manually here is futile if solve overwrites it.
    # We must rely on forcing or mock forcing.
    # mock_forcing has 'roof_irrigation' = 0.
    
    # Let's mock a forcing series that has irrigation
    forcing_day_custom = forcing_day.copy()
    forcing_day_custom['roof_irrigation'] = 5.0
    
    roof_component.solve(forcing_day_custom)
    
    # In = Precip (10) + Irrigation (5) = 15.
    # Out = Evap + Raintank + Stormwater + Pervious
    # ΔStorage
    
    precip = roof_component.roof_data.flows.get_flow('precipitation', 'mm')
    irrig = roof_component.roof_data.flows.get_flow('from_demand', 'mm')
    evap = roof_component.roof_data.flows.get_flow('evaporation', 'mm')
    to_tank = roof_component.roof_data.flows.get_flow('to_raintank', 'mm')
    to_storm = roof_component.roof_data.flows.get_flow('to_stormwater', 'mm')
    to_perv = roof_component.roof_data.flows.get_flow('to_pervious', 'mm')
    
    final_storage = roof_component.roof_data.storage.get_amount('mm')
    initial_storage = 0.0
    delta = final_storage - initial_storage
    
    total_in = precip + irrig
    total_out = evap + to_tank + to_storm + to_perv
    
    assert delta == pytest.approx(total_in - total_out, abs=1e-9)

    # Check 2: Full storage start
    roof_component.roof_data.storage.set_previous(2.0, 'mm')
    
    roof_component.solve(forcing_day_custom)
    
    # Verify balance again
    precip_2 = roof_component.roof_data.flows.get_flow('precipitation', 'mm')
    irrig_2 = roof_component.roof_data.flows.get_flow('from_demand', 'mm')
    evap_2 = roof_component.roof_data.flows.get_flow('evaporation', 'mm')
    to_tank_2 = roof_component.roof_data.flows.get_flow('to_raintank', 'mm')
    to_storm_2 = roof_component.roof_data.flows.get_flow('to_stormwater', 'mm')
    to_perv_2 = roof_component.roof_data.flows.get_flow('to_pervious', 'mm')
    
    final_storage_2 = roof_component.roof_data.storage.get_amount('mm')
    delta_2 = final_storage_2 - 2.0
    
    total_in_2 = precip_2 + irrig_2
    total_out_2 = evap_2 + to_tank_2 + to_storm_2 + to_perv_2
    
    assert delta_2 == pytest.approx(total_in_2 - total_out_2, abs=1e-9)

