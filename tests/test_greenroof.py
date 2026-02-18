import pytest
import pandas as pd
import numpy as np
from urbanWater.components.greenroof import GreenRoofClass
from urbanWater.data_structures import GreenRoofData
from urbanWater.flow_manager import FlowDirection

@pytest.fixture
def mock_params():
    return {
        'general': {'time_step': 1.0},
        'greenroof': {
            'area': 100.0,
            'effective_area': 100.0, # 100% connected
            'max_storage': 2.0, # mm (Surface)
            'max_substrate_storage': 10.0, # mm (Substrate)
            'initial_substrate_storage': 0.0,
            'substrate_depth': 100.0, # mm
            'crop_factor': 1.0,
            'conductivity': 100.0 # mm/h (Fast drainage for testing)
        },
        'pervious': {'area': 10.0} # Non-zero to enable effective_outflow logic
    }

@pytest.fixture
def greenroof_component(mock_params):
    data = GreenRoofData()
    return GreenRoofClass(mock_params, data)

@pytest.fixture
def mock_forcing():
    # 5 days of forcing
    return pd.DataFrame({
        'precipitation': [0, 10, 0, 50, 0],
        'potential_evaporation': [2, 2, 2, 0, 0],
        'greenroof_irrigation': [0, 0, 0, 0, 0]
    })

def test_initialization(greenroof_component, mock_params):
    """Test successful initialization."""
    assert greenroof_component.greenroof_data.area == 100.0
    assert greenroof_component.greenroof_data.surface_storage.get_capacity('mm') == 2.0
    assert greenroof_component.greenroof_data.substrate_storage.get_capacity('mm') == 10.0
    assert greenroof_component.greenroof_data.crop_factor == 1.0
    assert greenroof_component.greenroof_data.conductivity == 100.0

def test_solve_basic(greenroof_component, mock_forcing):
    """Test solve method with simple precipitation event."""
    # Day 1: 10mm precip, 2mm PE.
    # Surface Cap: 2mm. Substrate Cap: 10mm.
    # 1. Inflow = 10mm.
    # 2. Surface Storage = 10mm.
    # 3. Evap = min(10, 2) = 2mm. Surface = 8mm.
    # 4. Infiltration. K=100mm/h -> Unlimited.
    #    Infilt = min(8, unlimited) = 8mm.
    #    Surface = 0. Substrate = 8mm.
    # 5. Transpiration. PE=2, kc=1 -> 2mm.
    #    Transp = min(8, 2) = 2mm. Substrate = 6mm.
    # 6. Drainage. Substrate=6mm. Cap=10mm. No drainage.
    # 7. Surface Overflow. Surface=0. No overflow.
    # 8. Runoff = 0.
    
    forcing_day = mock_forcing.iloc[1] # 10mm rain
    greenroof_component.solve(forcing_day)
    
    data = greenroof_component.greenroof_data
    
    assert data.surface_storage.get_amount('mm') == pytest.approx(0.0)
    assert data.substrate_storage.get_amount('mm') == pytest.approx(6.0)
    assert data.flows.get_flow('evaporation', 'mm') == pytest.approx(2.0)
    assert data.flows.get_flow('transpiration', 'mm') == pytest.approx(2.0)
    assert data.flows.get_flow('to_stormwater', 'mm') == pytest.approx(0.0)

def test_solve_saturation_runoff(greenroof_component, mock_forcing):
    """Test runoff generation from saturation/drainage."""
    # Run Day 1 first to fill substrate partially (State: Substrate=6mm)
    forcing_day1 = mock_forcing.iloc[1]
    greenroof_component.solve(forcing_day1)
    
    # Update states to persist storage to next timestep
    greenroof_component.greenroof_data.surface_storage.update()
    greenroof_component.greenroof_data.substrate_storage.update()
    
    # Day 3: 50mm precip, 0 PE.
    # Initial: Surface=0, Substrate=6.
    # 1. Inflow = 50. Surface = 50.
    # 2. Evap = 0.
    # 3. Infiltration = 50. Surface = 0. Substrate = 6+50 = 56.
    # 4. Transp = 0.
    # 5. Drainage. Excess = 56 - 10 = 46mm.
    #    Drainage = 46mm. Substrate = 10mm.
    # 6. Overflow. Surface = 0.
    # 7. Total Runoff = 46mm.
    
    forcing_storm = mock_forcing.iloc[3] # 50mm rain
    greenroof_component.solve(forcing_storm)
    
    data = greenroof_component.greenroof_data
    
    assert data.surface_storage.get_amount('mm') == pytest.approx(0.0)
    assert data.substrate_storage.get_amount('mm') == pytest.approx(10.0)
    assert data.flows.get_flow('to_stormwater', 'mm') == pytest.approx(46.0 * 1.0) # 100% effective
    assert data.flows.get_flow('to_substrate', 'mm') == pytest.approx(50.0)

def test_solve_surface_overflow(greenroof_component, mock_forcing):
    """Test runoff generation from surface overflow (limited infiltration)."""
    # Set VERY LOW conductivity to force surface overflow check
    greenroof_component.greenroof_data.conductivity = 0.0 # No infiltration
    
    # Day 1: 10mm rain, 2mm evap.
    # 1. Inflow 10. Surface 10.
    # 2. Evap 2. Surface 8.
    # 3. Infilt 0. Surface 8.
    # 4. Transp 0 (Substrate empty).
    # 5. Drainage 0.
    # 6. Overflow. Surface Cap 2. Excess = 8 - 2 = 6mm.
    #    Overflow = 6mm. Surface = 2mm.
    
    forcing_day = mock_forcing.iloc[1]
    greenroof_component.solve(forcing_day)
    
    data = greenroof_component.greenroof_data
    
    assert data.surface_storage.get_amount('mm') == pytest.approx(2.0)
    assert data.substrate_storage.get_amount('mm') == pytest.approx(0.0)
    assert data.flows.get_flow('to_stormwater', 'mm') == pytest.approx(6.0)

def test_water_balance(greenroof_component, mock_forcing):
    """Verify conservation of mass."""
    # Precip 10
    forcing = mock_forcing.iloc[1]
    greenroof_component.solve(forcing)
    
    data = greenroof_component.greenroof_data
    
    # In = Precip (10) + Irrig (0)
    # Out = Evap + Transp + Runoff(stormwater+pervious)
    # Delta S = Delta Surface + Delta Substrate
    
    inflow = (data.flows.get_flow('precipitation', 'm3') + 
              data.flows.get_flow('from_demand', 'm3'))
              
    outflow = (data.flows.get_flow('evaporation', 'm3') +
               data.flows.get_flow('transpiration', 'm3') +
               data.flows.get_flow('to_stormwater', 'm3') +
               data.flows.get_flow('to_pervious', 'm3'))
               
    d_storage = (data.surface_storage.get_change('m3') + 
                 data.substrate_storage.get_change('m3'))
                 
    assert (inflow - outflow - d_storage) == pytest.approx(0.0, abs=1e-9)
