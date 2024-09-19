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

from typing import Dict, List
from dataclasses import fields

import pandas as pd
import numpy as np
from tqdm import tqdm

from duwcm.water_model import UrbanWaterModel
from duwcm.data_structures import UrbanWaterData

def run_water_balance(model: UrbanWaterModel, forcing: pd.DataFrame) -> pd.DataFrame:
    """Run the full simulation for all timesteps."""
    num_timesteps = len(forcing)

    # Initialize results as dictionaries of lists
    results = {field.name: [] for field in fields(UrbanWaterData)}
    results['aggregated'] = []

    # Add initial conditions to results at t=0
    initial_date = forcing.index[0] - pd.Timedelta(days=1)
    for cell_id, initial_state in model.previous.items():
        for module_name, module_data in initial_state.__dict__.items():
            results[module_name].append({
                'cell': cell_id,
                'date': initial_date,
                **module_data.__dict__
            })

    # Initialize aggregated results for t=0
    results['aggregated'].append({
        'date': initial_date,
        'stormwater': 0,
        'wastewater': 0,
        'baseflow': 0,
        'total_seepage': 0,
        'imported_water': 0,
        'transpiration': 0,
        'evaporation': 0
    })

    for t in tqdm(range(1, num_timesteps), desc="Water balance"):
        current_date = forcing.index[t]
        timestep_forcing = forcing.iloc[t]
        _solve_timestep(model, results, timestep_forcing, current_date)
        _aggregate_timestep(model, results, current_date)
        _distribute_wastewater(model, results)
        _distribute_stormwater(model, results)
        model.update_states()

    df_results = results_to_dataframes(results, model)
    df_results['local'] = selected_results(df_results)

    total_area = sum(params['groundwater']['area'] for params in model.params.values())
    df_results['aggregated'].attrs['total_area'] = total_area
    df_results['aggregated'].attrs['units'] = 'L'

    return df_results

def _solve_timestep(model: UrbanWaterModel, results: Dict[str, List[Dict]],
                    forcing: pd.Series, current_date: pd.Timestamp) -> None:
    """Solve the water balance for a single timestep for all cells in the specified order."""
    for cell_id in model.cell_order:
        upstream_cells = [int(up) for up in model.path.loc[cell_id][1:] if up != 0]

        # Calculate upstream inflows for the current timestep
        model.current[cell_id].stormwater.upstream_inflow = 0
        model.current[cell_id].wastewater.upstream_inflow = 0
        for up in upstream_cells:
            model.current[cell_id].stormwater.upstream_inflow += model.current[up].stormwater.sewer_inflow
            model.current[cell_id].wastewater.upstream_inflow += model.current[up].wastewater.sewer_inflow

        # Solve for each submodel
        for submodel_name, submodel in model.submodels[cell_id].items():
            setattr(model.current[cell_id], submodel_name,
                    submodel.solve(forcing, model.previous[cell_id], model.current[cell_id]))

        # Append results for this cell and timestep
        for module_name, module_data in model.current[cell_id].__dict__.items():
            results[module_name].append({
                'cell': cell_id,
                'date': current_date,
                **module_data.__dict__
            })

def _aggregate_timestep(model: UrbanWaterModel, results: Dict[str, List[Dict]], current_date: pd.Timestamp) -> None:
    """Aggregate results across all cells for the current timestep."""
    aggregated = {
        'date': current_date,
        'stormwater': 0,
        'wastewater': 0,
        'baseflow': 0,
        'total_seepage': 0,
        'imported_water': 0,
        'transpiration': 0,
        'evaporation': 0
    }

    for cell_id in model.params:
        current = model.current[cell_id]
        params = model.params[cell_id]

        if model.path.loc[cell_id, 'down'] == 0:
            aggregated['stormwater'] += current.stormwater.sewer_inflow
            aggregated['wastewater'] += current.wastewater.sewer_inflow

        aggregated['baseflow'] += current.groundwater.baseflow
        aggregated['total_seepage'] += current.groundwater.seepage
        aggregated['imported_water'] += current.reuse.imported_water
        aggregated['transpiration'] += current.vadose.transpiration * params['vadose']['area']
        aggregated['evaporation'] += (
            current.roof.evaporation +
            current.pavement.evaporation +
            current.pervious.evaporation +
            current.raintank.evaporation +
            current.stormwater.evaporation
        )

    results['aggregated'].append(aggregated)

def _distribute_wastewater(model: UrbanWaterModel, results: Dict[str, List[Dict]]) -> None:
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

            available_cells.remove(select)

    results['aggregated'][-1]['imported_water'] -= sum(model.current[w].wastewater.use for w in model.wastewater_cells)

def _distribute_stormwater(model: UrbanWaterModel, results: Dict[str, List[Dict]]) -> None:
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

            available_cells.remove(select)

    results['aggregated'][-1]['imported_water'] -= sum(model.current[s].stormwater.use for s in model.stormwater_cells)

def results_to_dataframes(results: Dict[str, List[Dict]], model: UrbanWaterModel) -> Dict[str, pd.DataFrame]:
    dataframe_results = {}
    for module, data in results.items():
        if module != 'aggregated':
            df = pd.DataFrame(data).set_index(['cell', 'date'])
            module_data = getattr(model.current[next(iter(model.current))], module)
            module_fields = fields(type(module_data))
            for column in df.columns:
                field = next(f for f in module_fields if f.name == column)
                df[column].attrs['unit'] = field.metadata['unit']
            dataframe_results[module] = df
        else:
            dataframe_results[module] = pd.DataFrame(data).set_index('date')
    return dataframe_results

def selected_results(dataframes: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    modules_to_keep = ['reuse', 'stormwater', 'wastewater', 'groundwater']
    variables_to_keep = {
        'reuse': {'imported_water': 'imported_water'},
        'stormwater': {'sewer_inflow': 'stormwater_runoff'},
        'wastewater': {'sewer_inflow': 'wastewater_runoff'},
        'groundwater': {'baseflow': 'baseflow', 'seepage': 'deep_seepage'}
    }

    dataframe_results = {}
    for module in modules_to_keep:
        df = dataframes[module]
        kept_columns = variables_to_keep[module]
        dataframe_results[module] = df[list(kept_columns.keys())].rename(columns=kept_columns)

    # Compute non-aggregated evapotranspiration
    et_components = {
        'roof': ('roof', 'evaporation'),
        'pavement': ('pavement', 'evaporation'),
        'pervious': ('pervious', 'evaporation'),
        'raintank': ('raintank', 'evaporation'),
        'stormwater': ('stormwater', 'evaporation'),
        'vadose': ('vadose', 'transpiration')
    }

    et_data = {
        component: dataframes[module][variable]
        for component, (module, variable) in et_components.items()
    }

    et_df = pd.DataFrame(et_data).sum(axis=1).to_frame(name='evapotranspiration')
    et_df['evapotranspiration'].attrs['unit'] = 'L'
    dataframe_results['evapotranspiration'] = et_df

    combined_results = pd.concat(list(dataframe_results.values()), axis=1)

    return combined_results
