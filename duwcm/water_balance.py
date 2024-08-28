"""
Urban Water Balance Module

This module provides functions to run urban water balance simulations using the
UrbanWaterModel.

The simulation process includes:
1. Initialization of result storage
2. Time-stepping through the simulation period
3. Solving water balance for each cell at each timestep
4. Distributing water between cells (cluster water and stormwater)
5. Aggregating results for each timestep
6. Updating model states
"""

from typing import Dict
from dataclasses import fields
import pandas as pd
import numpy as np
from tqdm import tqdm

from duwcm.water_model import UrbanWaterModel
from duwcm.data_structures import UrbanWaterData

def create_results_dataframe(num_cells: int, num_timesteps: int) -> Dict[str, pd.DataFrame]:
    """Initialize the results dictionary of DataFrames with pre-allocated memory for all time steps."""
    results = {}
    for field in fields(UrbanWaterData):
        module_name = field.name
        module_type = field.type
        columns = [f.name for f in fields(module_type)]

        index = pd.MultiIndex.from_product([range(num_cells), range(num_timesteps)],
                                           names=['cell', 'timestep'])
        results[module_name] = pd.DataFrame(index=index, columns=columns, dtype=float)

    aggregated_cols = [
        'runoff', 'wastewater', 'baseflow', 'total_seepage',
        'imported_water', 'evapotranspiration', 'evaporation'
    ]
    results['aggregated'] = pd.DataFrame(index=range(num_timesteps), columns=aggregated_cols, dtype=float)
    return results

def run_simulation(model: UrbanWaterModel, forcing: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """Run the full simulation for all timesteps."""
    num_timesteps = len(forcing)
    num_cells = len(model.params)

    results = create_results_dataframe(num_cells, num_timesteps)

    # Add initial conditions to results at t=0
    for cell_id, initial_state in model.previous.items():
        for module_name, module_data in initial_state.__dict__.items():
            for var, value in module_data.__dict__.items():
                results[module_name].loc[(cell_id, 0), var] = value

    for t in tqdm(range(1, num_timesteps), desc="Simulating", unit="timestep"):
        timestep_forcing = forcing.iloc[t]
        _solve_timestep(model, results, timestep_forcing, t)
        _aggregate_timestep(model, results, t)
        _distribute_wastewater(model, results, t)
        _distribute_stormwater(model, results, t)
        model.update_states()

    return results

def _solve_timestep(model: UrbanWaterModel, results: Dict[str, pd.DataFrame],
                    forcing: pd.Series, timestep: int) -> None:
    """Solve the water balance for a single timestep for all cells in the specified order."""
    for cell_id in model.cell_order:
        upstream_cells = [int(up) for up in model.path.loc[cell_id][1:] if up != 0]

        # Calculate upstream inflows for the current timestep
        model.current[cell_id].stormwater.upstream_inflow = sum(
            results['stormwater'].loc[(up, timestep-1), 'sewer_inflow'] for up in upstream_cells
        )
        model.current[cell_id].wastewater.upstream_inflow = sum(
            results['wastewater'].loc[(up, timestep-1), 'sewer_inflow'] for up in upstream_cells
        )

        # Solve for each submodel
        for module_name, submodel in model.submodels[cell_id].items():
            setattr(model.current[cell_id], module_name,
                    submodel.solve(forcing, model.previous[cell_id], model.current[cell_id]))

        # Update results
        for module_name, module_data in model.current[cell_id].__dict__.items():
            for var, value in module_data.__dict__.items():
                results[module_name].loc[(cell_id, timestep), var] = value

        # Handle outflows for cells without downstream neighbors
        if model.path.loc[cell_id, 'down'] == 0:
            results['aggregated'].loc[timestep, 'runoff'] += model.current[cell_id].stormwater.sewer_inflow
            results['aggregated'].loc[timestep, 'wastewater'] += model.current[cell_id].wastewater.sewer_inflow

def _distribute_wastewater(model: UrbanWaterModel, results: Dict[str, pd.DataFrame], timestep: int) -> None:
    """Distribute water from cluster wastewater storage to other cells."""
    for w in model.wastewater_cells:
        available_cells = list(model.cell_order)
        while model.current[w].wastewater.storage > 0 and available_cells:
            select = np.random.choice(available_cells)
            reuse_index = 1 if model.reuse_settings.shape[1] == 1 else select
            setreuse = model.reuse_settings[reuse_index]

            # Toilet use
            wws_toilet_use = min(model.current[w].wastewater.storage,
                                 model.current[select].reuse.toilet_demand * setreuse.cWWSforT)
            model.current[select].reuse.toilet_demand -= wws_toilet_use

            # Irrigation use
            wws_irrigation_use = min(model.current[w].wastewater.storage - wws_toilet_use,
                                     model.current[select].reuse.irrigation_demand * setreuse.cWWSforIR)
            model.current[select].reuse.irrigation_demand -= wws_irrigation_use

            # Update storages and uses
            model.current[w].wastewater.storage -= (wws_toilet_use + wws_irrigation_use)
            model.current[w].wastewater.use += (wws_toilet_use + wws_irrigation_use)
            model.current[select].wastewater.supply += (wws_toilet_use + wws_irrigation_use)
            model.current[select].reuse.imported_water -= (wws_toilet_use + wws_irrigation_use)

            # Update results
            results['wastewater'].loc[(w, timestep), 'storage'] = model.current[w].wastewater.storage
            results['wastewater'].loc[(w, timestep), 'use'] = model.current[w].wastewater.use
            results['wastewater'].loc[(select, timestep), 'supply'] = model.current[select].wastewater.supply
            results['reuse'].loc[(select, timestep), 'imported_water'] = model.current[select].reuse.imported_water

            available_cells.remove(select)
        results['aggregated'].loc[timestep, 'imported_water'] -= model.current[w].wastewater.use

def _distribute_stormwater(model: UrbanWaterModel, results: Dict[str, pd.DataFrame], timestep: int) -> None:
    """Distribute water from stormwater storage to other cells."""
    for s in model.stormwater_cells:
        available_cells = list(model.cell_order)
        while model.current[s].stormwater.storage > 0 and available_cells:
            select = np.random.choice(available_cells)
            reuse_index = 1 if model.reuse_settings.shape[1] == 1 else select
            setreuse = model.reuse_settings[reuse_index]

            # Toilet use
            sws_toilet_use = min(model.current[s].stormwater.storage,
                                 model.current[select].reuse.toilet_demand * setreuse.SWSforT)
            model.current[select].reuse.toilet_demand -= sws_toilet_use

            # Irrigation use
            sws_irrigation_use = min(model.current[s].stormwater.storage - sws_toilet_use,
                                     model.current[select].reuse.irrigation_demand * setreuse.SWSforIR)
            model.current[select].reuse.irrigation_demand -= sws_irrigation_use

            # Update storages and uses
            model.current[s].stormwater.storage -= (sws_toilet_use + sws_irrigation_use)
            model.current[s].stormwater.use += (sws_toilet_use + sws_irrigation_use)
            model.current[select].stormwater.supply += (sws_toilet_use + sws_irrigation_use)
            model.current[select].reuse.imported_water -= (sws_toilet_use + sws_irrigation_use)

            # Update results
            results['stormwater'].loc[(s, timestep), 'storage'] = model.current[s].stormwater.storage
            results['stormwater'].loc[(s, timestep), 'use'] = model.current[s].stormwater.use
            results['stormwater'].loc[(select, timestep), 'supply'] = model.current[select].stormwater.supply
            results['reuse'].loc[(select, timestep), 'imported_water'] = model.current[select].reuse.imported_water

            available_cells.remove(select)
        results['aggregated'].loc[timestep, 'imported_water'] -= model.current[s].stormwater.use

def _aggregate_timestep(model: UrbanWaterModel, results: Dict[str, pd.DataFrame], timestep: int) -> None:
    """Aggregate results across all cells for the current timestep."""
    agg_data = results['aggregated']

    agg_data.loc[timestep, 'baseflow'] = sum(model.current[cell].groundwater.baseflow for cell in model.params)
    agg_data.loc[timestep, 'seepage'] = sum(model.current[cell].groundwater.seepage for cell in model.params)
    agg_data.loc[timestep, 'imported_water'] = sum(model.current[cell].reuse.imported_water for cell in model.params)

    total_et = sum(model.current[cell].vadose.transpiration * model.params[cell]['vadose']['area']
                   for cell in model.params)
    agg_data.loc[timestep, 'evapotranspiration'] = total_et

    total_evaporation = sum(
        model.current[cell].roof.evaporation * model.params[cell]['roof']['area'] +
        model.current[cell].pavement.evaporation * model.params[cell]['pavement']['area'] +
        model.current[cell].pervious.evaporation * model.params[cell]['pervious']['area'] +
        model.current[cell].raintank.evaporation +
        model.current[cell].vadose.transpiration * model.params[cell]['vadose']['area'] +
        model.current[cell].stormwater.evaporation
        for cell in model.params
    )
    agg_data.loc[timestep, 'evaporation'] = total_evaporation
