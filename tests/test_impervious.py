import pytest
import numpy as np

def test_impervious_initialization(impervious_component, mock_params):
    """Test successful initialization of ImperviousClass."""
    assert impervious_component.impervious_data.area == mock_params['impervious']['area']
    assert impervious_component.impervious_data.storage.get_capacity('mm') == mock_params['impervious']['max_storage']

def test_impervious_solve(impervious_component, mock_forcing):
    """Test solve method with precipitation and overflow logic."""
    forcing_day = mock_forcing.iloc[1] # 10mm precip, 1.0 pot evap
    
    # Initial state: Empty
    impervious_component.impervious_data.storage.set_previous(0.0, 'mm')
    
    # Run
    impervious_component.solve(forcing_day)
    
    # Verify outputs exist
    final_storage = impervious_component.impervious_data.storage.get_amount('mm')
    evap = impervious_component.impervious_data.flows.get_flow('evaporation', 'mm')
    runoff_storm = impervious_component.impervious_data.flows.get_flow('to_stormwater', 'mm')
    runoff_perv = impervious_component.impervious_data.flows.get_flow('to_pervious', 'mm')
    
    # Mass balance check for this single run
    # In = 10.0. Out = Evap + Runoff. ΔStorage = Final.
    total_out = evap + runoff_storm + runoff_perv
    assert (10.0 - total_out) == pytest.approx(final_storage, abs=1e-9)
    
    # Ensure some runoff happened (since 10mm > Cap typically)
    assert (runoff_storm + runoff_perv) > 0.0

def test_impervious_water_balance(impervious_component, mock_forcing):
    """Test water balance conservation in ImperviousClass."""
    forcing_day = mock_forcing.iloc[1] # 10.0mm precip
    
    # Set capacity known (modify capacity for test)
    impervious_component.impervious_data.storage.set_capacity(2.0, 'mm')
    
    # Initial state
    initial_storage = 0.5 # mm
    impervious_component.impervious_data.storage.set_previous(initial_storage, 'mm')
    
    # Inflows
    # Precip = 10.0 (from forcing)
    # Raintank overflow? Manual set in m3.
    area = impervious_component.impervious_data.area
    inv_rain = 1.0 # m3
    impervious_component.impervious_data.flows.set_flow('from_raintank', inv_rain, 'm3')
    
    # Demand irrigation (from forcing 'impervious_irrigation' - default 0).
    # Let's mock forcing to have irrigation
    forcing_day_mod = forcing_day.copy()
    forcing_day_mod['impervious_irrigation'] = 2.0 # mm
    
    # Solve
    impervious_component.solve(forcing_day_mod)
    
    # Verify
    precip_m3 = impervious_component.impervious_data.flows.get_flow('precipitation', 'm3')
    irrig_m3 = impervious_component.impervious_data.flows.get_flow('from_demand', 'm3')
    rt_m3 = impervious_component.impervious_data.flows.get_flow('from_raintank', 'm3')
    
    evap_m3 = impervious_component.impervious_data.flows.get_flow('evaporation', 'm3')
    storm_m3 = impervious_component.impervious_data.flows.get_flow('to_stormwater', 'm3')
    perv_m3 = impervious_component.impervious_data.flows.get_flow('to_pervious', 'm3')
    
    final_storage_m3 = impervious_component.impervious_data.storage.get_amount('m3')
    initial_storage_m3 =  initial_storage * area / 1000.0 # mm to m3
    
    delta_m3 = final_storage_m3 - initial_storage_m3
    
    total_in = precip_m3 + irrig_m3 + rt_m3
    total_out = evap_m3 + storm_m3 + perv_m3
    
    assert delta_m3 == pytest.approx(total_in - total_out, abs=1e-9)
