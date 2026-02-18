import pytest
import numpy as np

def test_raintank_initialization(raintank_component, mock_params):
    """Test successful initialization of RainTankClass."""
    # raintank_total_ratio = number_houses (10) * install_ratio (0.5) = 5.0
    # area = params['area'] (250) * 5.0 = 1250.0
    assert raintank_component.raintank_data.area == 1250.0
    assert raintank_component.raintank_data.storage.get_capacity('L') == 25000.0
    assert raintank_component.raintank_data.storage.get_amount('L') == 0.0

def test_raintank_solve(raintank_component, mock_forcing):
    """Test solve method with inflow from roof."""
    forcing_day = mock_forcing.iloc[1] # 10mm precip
    
    # Set initial state
    raintank_component.raintank_data.storage.set_previous(0.0, 'L')

    # Roof inflow: 5.0 m3 = 5000 Liters
    raintank_component.raintank_data.flows.set_flow('from_roof', 5000.0, 'L')
    
    # Run
    raintank_component.solve(forcing_day)
    
    # Verify outputs
    # Component logic checks:
    # 1. First flush removal. 
    #    params: flush = 2.0 L? No, params['raintank']['first_flush'] = 2.0.
    #    In __init__: self.raintank_data.first_flush = params... * total_ratio * 0.001 (m3).
    #    mock_params['raintank']['first_flush'] = 2.0. 
    #    install_ratio = 0.5 (50%). number_houses=10.
    #    total_ratio = 10 * 0.5 = 5.0.
    #    first_flush_vol = 2.0 * 5.0 * 0.001 m3 = 0.01 m3 = 10 L.
    
    # 2. Inflow to tank
    #    Roof Inflow = 5000 L.
    #    Installed portion = 5000 * 0.5 = 2500 L.
    #    Deduct flush = 2500 - 10 = 2490 L.
    #    Precipitation? 'is_open' = False in mock_params. So 0.
    #    Net Inflow to Storage = 2490 L.
    
    # 3. Storage
    #    Capacity = 25000 L.
    #    Previous = 0.
    #    New Storage = 2490 L (since 2490 < 25000).
    
    # 4. Overflow
    #    Inflow (2490) - Evap (0) - ΔStorage (2490) = 0.
    
    # 5. System Outflow
    #    Flush (10 L) + Overflow (0 L) + Bypass (5000 * 0.5 = 2500 L).
    #    Total Outflow = 2510 L.
    
    # 6. Split to Stormwater / Impervious
    #    effective_area = 80%.
    #    to_stormwater = 2510 * 0.8 = 2008 L.
    #    to_impervious = 2510 * 0.2 = 502 L.

    assert raintank_component.raintank_data.storage.get_amount('L') == pytest.approx(2490.0)
    assert raintank_component.raintank_data.flows.get_flow('to_stormwater', 'L') == pytest.approx(2008.0)
    assert raintank_component.raintank_data.flows.get_flow('to_impervious', 'L') == pytest.approx(502.0)

def test_raintank_water_balance(raintank_component, mock_forcing):
    """Test water balance conservation in RainTankClass."""
    forcing_day = mock_forcing.iloc[1] # 10mm precip
    
    # Case 1: Open tank (receives precip), with pre-filled storage
    raintank_component.raintank_data.is_open = True
    initial_storage = 10000.0 # L
    raintank_component.raintank_data.storage.set_previous(initial_storage, 'L')
    
    # Inflows
    roof_inflow = 4000.0 # L
    raintank_component.raintank_data.flows.set_flow('from_roof', roof_inflow, 'L')
    
    raintank_component.solve(forcing_day)
    
    # Get all flows
    precip_in = raintank_component.raintank_data.flows.get_flow('precipitation', 'L')
    # Use roof_inflow variable directly as it's the input
    
    evap_out = raintank_component.raintank_data.flows.get_flow('evaporation', 'L')
    storm_out = raintank_component.raintank_data.flows.get_flow('to_stormwater', 'L')
    imp_out = raintank_component.raintank_data.flows.get_flow('to_impervious', 'L')
    
    final_storage = raintank_component.raintank_data.storage.get_amount('L')
    delta_storage = final_storage - initial_storage
    
    # Mass Balance: In = Out + ΔS
    # In = Roof + Precip
    # Out = Evap + Storm + Imp
    
    total_in = roof_inflow + precip_in
    total_out = evap_out + storm_out + imp_out
    
    assert delta_storage == pytest.approx(total_in - total_out, abs=1e-9)
    
    # Case 2: Overflow
    # Fill close to capacity
    capacity = raintank_component.raintank_data.storage.get_capacity('L') # 25000 L
    initial_storage_2 = 24000.0
    raintank_component.raintank_data.storage.set_previous(initial_storage_2, 'L')
    
    # Large inflow
    roof_inflow_2 = 10000.0 # L
    raintank_component.raintank_data.flows.set_flow('from_roof', roof_inflow_2, 'L')
    
    raintank_component.solve(forcing_day)
    
    final_storage_2 = raintank_component.raintank_data.storage.get_amount('L')
    
    # Should be full (minus evap if any)
    # Evap depends on is_open. It is still True.
    # Precip also adds in.
    
    precip_in_2 = raintank_component.raintank_data.flows.get_flow('precipitation', 'L')
    evap_out_2 = raintank_component.raintank_data.flows.get_flow('evaporation', 'L')
    storm_out_2 = raintank_component.raintank_data.flows.get_flow('to_stormwater', 'L')
    imp_out_2 = raintank_component.raintank_data.flows.get_flow('to_impervious', 'L')
    
    delta_storage_2 = final_storage_2 - initial_storage_2
    total_in_2 = roof_inflow_2 + precip_in_2
    total_out_2 = evap_out_2 + storm_out_2 + imp_out_2
    
    assert delta_storage_2 == pytest.approx(total_in_2 - total_out_2, abs=1e-9)
    
    # Verify we hit capacity (approx, considering evap)
    # If evap < inflow, it should be full.
    assert final_storage_2 <= capacity

