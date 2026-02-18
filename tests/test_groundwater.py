import pytest
import numpy as np

def test_groundwater_initialization(groundwater_component, mock_params):
    """Test successful initialization of GroundwaterClass."""
    assert groundwater_component.groundwater_data.area == mock_params['groundwater']['area']
    assert groundwater_component.groundwater_data.water_level.get_previous('m') == mock_params['groundwater']['initial_level']

def test_groundwater_solve_constant_flux(groundwater_component, mock_forcing):
    """Test solve method with constant flux model."""
    forcing_day = mock_forcing.iloc[0]
    
    # Run
    groundwater_component.solve(forcing_day)
    
    # Check outputs exist and are reasonable
    # Seepage should be positive (downward)? 
    # Params: hydraulic_head=-5.0. Initial level=-3.0. 
    # Logic: Seepage = downward_seepage * dt (constant flux model).
    # mock_params['groundwater']['downward_seepage'] = 0.0??
    # test_groundwater.py didn't show params.
    # conftest.py usually has downward_seepage.
    
    assert groundwater_component.groundwater_data.flows.get_flow('baseflow', 'm') is not None
    assert groundwater_component.groundwater_data.flows.get_flow('seepage', 'm') is not None

def test_groundwater_water_balance(groundwater_component, mock_forcing):
    """Test water balance conservation in GroundwaterClass."""
    forcing_day = mock_forcing.iloc[0] # open_water_level?
    
    # Set known state
    initial_level = -2.0 # m
    groundwater_component.groundwater_data.water_level.set_previous(initial_level, 'm')
    groundwater_component.groundwater_data.surface_water_level.set_previous(0.0, 'm')
    
    # Set inputs
    # Inflow from Vadose (Percolation)
    percolation = 0.005 # m (5mm)
    groundwater_component.groundwater_data.flows.set_flow('from_vadose', percolation, 'm')
    
    # Inflow from Demand (Leakage) - handled inside solve based on forcing/params.
    # We can assume it calculates something.
    
    # Run
    groundwater_component.solve(forcing_day)
    
    # Retrieve all components
    # Flows (m)
    inflow_vadose = groundwater_component.groundwater_data.flows.get_flow('from_vadose', 'm')
    inflow_demand = groundwater_component.groundwater_data.flows.get_flow('from_demand', 'm')
    
    outflow_seepage = groundwater_component.groundwater_data.flows.get_flow('seepage', 'm')
    outflow_pipe = groundwater_component.groundwater_data.flows.get_flow('to_sewerage', 'm')
    outflow_baseflow = groundwater_component.groundwater_data.flows.get_flow('baseflow', 'm')
    
    # Storage Change
    # Needs storage coefficient
    sc = groundwater_component.groundwater_data.storage_coefficient
    
    wl_change = groundwater_component.groundwater_data.water_level.get_change('m')
    surf_change = groundwater_component.groundwater_data.surface_water_level.get_change('m')
    
    # Calculate storage change in equivalent water depth
    storage_change_depth = (wl_change * sc) + surf_change
    
    # Balance: In - Out = ΔStorage
    # But note: baseflow calculation in code acts as residual?
    # Code: baseflow = (SC * ΔH + ΔS + In - Seep - Inf) * dt ??
    # Wait, line 118: baseflow = (SC*ΔH + ΔSurf + In? No... Wait)
    # Re-reading line 118 in groundwater.py:
    # baseflow = (data.storage_coefficient * data.water_level.get_change('m') +
    #             data.surface_water_level.get_change('m') +
    #             inflow - seepage - infiltration) * self.time_step
    
    # Logic in line 118 seems wrong dimensionally or algebraically for residual?
    # If `baseflow` is an outflow.
    # `In - Out = ΔS`.
    # `In - (Seep + Inf + Base) = ΔS`.
    # `Base = In - Seep - Inf - ΔS`.
    # Code says: `Base = ΔS + In - Seep - Inf`.
    # So `Base` has SAME sign as `In`??
    # If `In` is huge, `Base` is huge positive.
    # If `Base` is outflow, it should be positive?
    
    # Let's check `ΔS`.
    # If Inflow causes Level rise (positive ΔS).
    # `Base = ΔS + In ...` -> Positive + Positive = Double counting?
    
    # Let's assume the code intended `Base = (In - Seep - Inf) - ΔS`.
    # Code: `(ΔS + In - Seep - Inf)`.
    # If ΔH is calculated based on Inflow, then ΔH is related to Inflow.
    # Analytical solution `_dynamic_flux` computes H_new.
    # If `H_new` is correctly computed, then `baseflow` should be the flux TO surface water?
    # The term `(SC * ΔH)` is change in volume.
    
    # Wait, if `baseflow` is defined as `(H - OpenWater) / DrainageResistance`.
    # Does the code use that?
    # No, it calculates `baseflow` line 118 explicitly.
    # But `_dynamic_flux` uses `drainage_resistance` to find H.
    # So `H` satisfies the differential equation which includes baseflow term.
    # So `baseflow` variable calculated at end is just for reporting?
    # And it calculates it as residual?
    
    # See line 118 again: `(SC*ΔH + ΔSurf + In - Seep - Inf)`?
    # If `In - Out = ΔS`. `Out = Seep + Inf + Base`.
    # `In - Seep - Inf - Base = ΔS`.
    # `Base = In - Seep - Inf - ΔS`.
    # Code: `Base = ΔS + In ...`?
    # If ΔS is subtracted?
    # `data.water_level.get_change` is (Current - Previous).
    # So `ΔS` is positive if level rises.
    # If `Base = ΔS + In...`, then `Base` is `ΔS + NetIn`.
    
    # Maybe `Base` is Inflow FROM Open Water?
    # If `Base` > 0 means entering GW?
    # Usually Baseflow is GW -> Surf.
    # If code definition is `Base = ...`.
    # Let's check mass balance assertion with "Code's Baseflow".
    # Assertion: `In - (Seep + Inf) - Base =? ΔS`?
    # If `Base` is calculated as `ΔS + NetIn`, then `Base - ΔS = NetIn`.
    # `Base = NetIn + ΔS`.
    # `Base - NetIn = ΔS`.
    # This implies `Baseflow` is `NetIn + ΔS`.
    # This verifies the calculation, but is it physically correct?
    
    # If `H` comes from analytical solution, assume `H` is correct.
    # Then `Baseflow` is the flux that sustains this H?
    # If `Base = NetIn - ΔS`.
    # Code: `Base = ΔS + NetIn`.
    # Difference is sign of ΔS? Or sign of NetIn?
    # If `NetIn` (In - Seep - Inf) is positive.
    # `ΔS` should be positive (rise).
    # Then `NetIn - ΔS` is small (residual).
    # `NetIn + ΔS` is huge.
    
    # This suggests line 118 might have a SIGN ERROR in `groundwater.py`.
    # `baseflow = (... - ... + inflow ...)`
    # Should probably be `inflow - ... - ... - ...`?
    
    # I will assert what the CODE DOES to verify consistency, and flag if it looks weird.
    # `calculated_base = (sc * wl_change + surf_change + inflow_vadose + inflow_demand - outflow_seepage - outflow_pipe)`
    # We ignore time_step multiply inside `solve`?
    # line 118: `... * self.time_step`.
    # So `baseflow` variable is Volume (L or m depth over step).
    
    # Re-calculate expected baseflow from variables
    input_net = inflow_vadose + inflow_demand - outflow_seepage - outflow_pipe
    storage_change = storage_change_depth
    
    # Code implementation check:
    # baseflow_code = (storage_change + input_net) * 1.0 (if dt=1 check params)
    
    # Wait, `solve` line 120: `... * self.time_step`.
    # Variables `get_change`, `inflow` are fluxes / absolute diffs?
    # `get_change` is difference in level (m).
    # `inflow` is depth (m).
    # `seepage` is depth (m).
    # `infiltration` is depth (m) (line 117 * time_step).
    # Wait, line 117: `infiltration = ... * self.time_step`.
    # line 111: `seepage = ... * self.time_step`.
    # So `seepage`, `infiltration`, `inflow` are all Volumes (Depth) per Step.
    # `baseflow` line 118 is `(... ) * self.time_step`.
    # This suggests `(... )` is a Rate?
    # But `get_change` (m) is absolute change, not rate.
    # `inflow` (m) is depth per step?
    # `seepage` (m) is depth per step?
    # If `(... )` sums depths, multiplying by `time_step` makes it `m * day`?
    # That is WRONG units.
    # `Baseflow` should be depth [m].
    # Use of `* self.time_step` on line 120 implies the terms in parenthesis are Rates?
    # But `water_level.get_change('m')` is a difference, not a rate.
    # `inflow` (from flows) is set as `L` converted to `m`. Usually per step.
    
    # Conclusion: There is likely a BUG in `groundwater.py` line 118-120.
    # 1. Sign of balance.
    # 2. Multiplication by `time_step`.
    
    # I will write the test to FAIL if this bug exists, or PASS if I adjust expectation to match code?
    # The goal is "Strict water balance check".
    # If the component is buggy, the test should fail (or I fix the component).
    # I should fix the component if it violates mass balance.
    
    # Let's verify `groundwater.py` again.
    # `seepage` line 106: `... * self.time_step / resistance`. (Head/Time * Time = Head? No. Head / Time * Time = Head? Resistance in days. m / d * d = m.)
    # Correct.
    # `baseflow` line 118.
    # `( ... ) * self.time_step`.
    # If `baseflow` is `m`, then `(...)` must be `m/d`.
    # But `get_change('m')` is `m`. `inflow` is `m`.
    # So `(m + m + m - m - m) * d` = `m*d`.
    # This is dimensionally wrong.
    
    # FIX: `baseflow` should likely NOT be multiplied by `time_step` if terms are already depths.
    # AND the sign should be `In - Out - ΔS`.
    
    # Strategy:
    # 1. Refactor test to assert `In - Out = ΔS`.
    # 2. Run test. Expect FAIL.
    # 3. Fix `groundwater.py`.
    
    total_in = inflow_vadose + inflow_demand
    total_out = outflow_seepage + outflow_pipe + outflow_baseflow # Assuming baseflow is outflow
    
    delta_s = storage_change_depth
    
    # We expect `total_in - total_out == delta_s +- epsilon`
    # If this fails, we know component is broken.
    assert delta_s == pytest.approx(total_in - total_out, abs=1e-9)

