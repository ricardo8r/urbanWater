"""
This module provides functions for checking the water balance in the urban water model.
It includes two main functions:

1. check_all: Computes the water balance for the entire urban water system.
2. check_cell: Computes the water balance for each individual grid cell in the system.

These functions take simulation results, model parameters, and forcing data as inputs,
and return water balance components in pandas DataFrames. They can be used to verify
the conservation of water in the system and to analyze the distribution of water
across different components of the urban water cycle.
"""
import pandas as pd
from tqdm import tqdm

def check_all(results: dict, params: dict, forcing: pd.DataFrame) -> pd.DataFrame:
    """
    Compute the water balance for the entire urban water system using vectorized operations.
    """
    num_timesteps = len(forcing)
    cell_ids = list(params.keys())

    # Pre-calculate area sums
    areas = pd.DataFrame({
        'roof': [params[cell_id]['roof']['area'] for cell_id in cell_ids],
        'pavement': [params[cell_id]['pavement']['area'] for cell_id in cell_ids],
        'pervious': [params[cell_id]['pervious']['area'] for cell_id in cell_ids],
        'raintank': [params[cell_id]['raintank']['is_open'] *
                     params[cell_id]['raintank']['area'] for cell_id in cell_ids],
        'stormwater': [params[cell_id]['stormwater']['is_open'] *
                       params[cell_id]['stormwater']['area'] for cell_id in cell_ids],
        'groundwater': [params[cell_id]['groundwater']['area'] for cell_id in cell_ids],
        'vadose': [params[cell_id]['vadose']['area'] for cell_id in cell_ids]
    }, index=cell_ids)

    # Initialize result DataFrame
    water_balance = pd.DataFrame(index=range(1, num_timesteps), columns=[
        "inflow", "outflow", "storage_change", "water_balance_1", "water_balance_2",
        "inflow_precipitation", "inflow_sewer", "inflow_imported", "inflow_recycled", "irrigation",
        "outflow_subsurface", "total_evaporation", "outflow_evapotranspiration", "outflow_sewer", "outflow_recycled"
    ])

    def get_timestep_data(module, timestep):
        return results[module].xs(timestep, level='timestep').reset_index().set_index('cell')

    for t in tqdm(range(1, num_timesteps), desc="Checker"):
        # Extract data for current and previous timesteps
        current_data = {module: get_timestep_data(module, t) for module in results if module != 'aggregated'}
        prev_data = {module: get_timestep_data(module, t-1) for module in results if module != 'aggregated'}

        # Vectorized calculations
        precipitation = ((areas['roof'] + areas['pavement'] + areas['pervious'] +
                          areas['raintank'] + areas['stormwater']) * forcing.precipitation.iloc[t]).sum()

        inflow_sewer = (current_data["stormwater"]["upstream_inflow"].sum() +
                        current_data["wastewater"]["upstream_inflow"].sum())

        inflow_imported = current_data["reuse"]["imported_water"].sum()

        inflow_recycled = 0#(current_data["wastewater"]["supply"].sum() +
                          # current_data["stormwater"]["supply"].sum())

        irrigation = ((forcing.pervious_irrigation.iloc[t] * areas['pervious'] +
                       forcing.pavement_irrigation.iloc[t] * areas['pavement'] +
                       forcing.roof_irrigation.iloc[t] * areas['roof']).sum())

        evaporation_sf = ((current_data["roof"]["evaporation"] * areas['roof'] +
                           current_data["pavement"]["evaporation"] * areas['pavement'] +
                           current_data["pervious"]["evaporation"] * areas['pervious']).sum())

        evaporation_st = (current_data["raintank"]["evaporation"].sum() +
                          current_data["stormwater"]["evaporation"].sum())

        evaporation_vd = (current_data["vadose"]["transpiration"] * areas['vadose']).sum()

        total_evaporation = evaporation_sf + evaporation_st + evaporation_vd

        outflow_subsurface = (current_data["groundwater"]["seepage"].sum() +
                              current_data["groundwater"]["baseflow"].sum())

        outflow_sewer = (current_data["wastewater"]["sewer_inflow"].sum() +
                         current_data["stormwater"]["sewer_inflow"].sum())

        outflow_recycled = 0#(current_data["wastewater"]["use"].sum() +
                            #current_data["stormwater"]["use"].sum())

        # Storage changes
        storage_changes = {
            'impervious': ((current_data["roof"]["storage"] - prev_data["roof"]["storage"]) * areas['roof'] +
                           (current_data["pavement"]["storage"] -
                            prev_data["pavement"]["storage"]) * areas['pavement']).sum(),
            'pervious': (areas['pervious'] * (current_data["pervious"]["storage"] -
                                              prev_data["pervious"]["storage"])).sum(),
            'raintank': (current_data["raintank"]["storage"] - prev_data["raintank"]["storage"]).sum(),
            'vadose': (areas['vadose'] * (current_data["vadose"]["moisture"] - prev_data["vadose"]["moisture"])).sum(),
            'groundwater': (current_data["groundwater"]["storage_coefficient"] * areas['groundwater'] *
                            (current_data["groundwater"]["water_level"] -
                             prev_data["groundwater"]["water_level"])).sum(),
            'storage': ((current_data["stormwater"]["storage"] - prev_data["stormwater"]["storage"]) +
                        (current_data["wastewater"]["storage"] - prev_data["wastewater"]["storage"]) +
                        (current_data["reuse"]["wws_storage"] - prev_data["reuse"]["wws_storage"])).sum()
        }

        storage_change = sum(storage_changes.values())

        inflow = precipitation + inflow_imported
        outflow = (total_evaporation + outflow_subsurface + results['aggregated'].loc[t, 'stormwater'] +
                   results['aggregated'].loc[t, 'wastewater'])

        water_balance_1 = inflow - outflow - storage_change
        water_balance_2 = ((inflow + inflow_sewer + inflow_recycled) -
                           (total_evaporation + outflow_subsurface + outflow_sewer + outflow_recycled) - storage_change)

        water_balance.loc[t] = [
            inflow, outflow, storage_change, water_balance_1, water_balance_2,
            precipitation, inflow_sewer, inflow_imported, inflow_recycled, irrigation,
            outflow_subsurface, total_evaporation, evaporation_vd, outflow_sewer, outflow_recycled
        ]

    return water_balance

def check_cell(results: dict, params: dict, forcing: pd.DataFrame) -> pd.DataFrame:
    """
    Compute the water balance for each grid cell in the urban water system using vectorized operations.
    """
    num_timesteps = len(forcing)
    cell_ids = list(params.keys())

    # Pre-calculate area sums
    areas = pd.DataFrame({
        'roof': [params[cell_id]['roof']['area'] for cell_id in cell_ids],
        'pavement': [params[cell_id]['pavement']['area'] for cell_id in cell_ids],
        'pervious': [params[cell_id]['pervious']['area'] for cell_id in cell_ids],
        'raintank': [params[cell_id]['raintank']['is_open'] *
                     params[cell_id]['raintank']['area'] for cell_id in cell_ids],
        'stormwater': [params[cell_id]['stormwater']['is_open'] *
                       params[cell_id]['stormwater']['area'] for cell_id in cell_ids],
        'groundwater': [params[cell_id]['groundwater']['area'] for cell_id in cell_ids],
        'vadose': [params[cell_id]['vadose']['area'] for cell_id in cell_ids]
    }, index=cell_ids)

    # Initialize result DataFrame
    index = pd.MultiIndex.from_product([cell_ids, range(1, num_timesteps)], names=['cell', 'timestep'])
    water_balance = pd.DataFrame(index=index, columns=[
        "inflow", "outflow", "storage_change", "water_balance", "water_balance_use"
    ], dtype=float)

    for t in tqdm(range(1, num_timesteps), desc="Cell checker"):
        # Extract data for current and previous timesteps
        current_data = {module: results[module].xs(t, level='timestep') for module in results if module != 'aggregated'}
        prev_data = {module: results[module].xs(t-1, level='timestep') for module in results if module != 'aggregated'}

        # Vectorized calculations
        precipitation = ((areas['roof'] + areas['pavement'] + areas['pervious'] +
                          areas['raintank'] + areas['stormwater']) * forcing.precipitation.iloc[t])

        irrigation = (forcing.pervious_irrigation.iloc[t] * areas['pervious'] +
                      forcing.pavement_irrigation.iloc[t] * areas['pavement'] +
                      forcing.roof_irrigation.iloc[t] * areas['roof'])

        inflow_sewer = (current_data["stormwater"]["upstream_inflow"] +
                        current_data["wastewater"]["upstream_inflow"])

        inflow_recycled = (current_data["reuse"]["imported_water"])# +
                           #current_data["wastewater"]["supply"] +
                           #current_data["stormwater"]["supply"])

        inflow = precipitation + inflow_sewer + inflow_recycled

        evaporation_sf = (current_data["roof"]["evaporation"] * areas['roof'] +
                          current_data["pavement"]["evaporation"] * areas['pavement'] +
                          current_data["pervious"]["evaporation"] * areas['pervious'])

        evaporation_st = (current_data["raintank"]["evaporation"] +
                          current_data["stormwater"]["evaporation"])

        evaporation_vd = current_data["vadose"]["transpiration"] * areas['vadose']

        total_evaporation = evaporation_sf + evaporation_st + evaporation_vd

        outflow_sewer = (current_data["wastewater"]["sewer_inflow"] +
                         current_data["stormwater"]["sewer_inflow"])

        outflow_subsurface = (current_data["groundwater"]["seepage"] +
                              current_data["groundwater"]["baseflow"])

        outflow_recycled = 0#(current_data["wastewater"]["use"] +
                           # current_data["stormwater"]["use"])

        outflow = total_evaporation + outflow_sewer + outflow_subsurface + outflow_recycled

        # Storage changes
        storage_changes = pd.DataFrame({
            'impervious': ((current_data["roof"]["storage"] - prev_data["roof"]["storage"]) * areas['roof'] +
                           (current_data["pavement"]["storage"] -
                            prev_data["pavement"]["storage"]) * areas['pavement']),
            'pervious': (areas['pervious'] * (current_data["pervious"]["storage"] - prev_data["pervious"]["storage"])),
            'raintank': (current_data["raintank"]["storage"] - prev_data["raintank"]["storage"]),
            'vadose': (areas['vadose'] * (current_data["vadose"]["moisture"] - prev_data["vadose"]["moisture"])),
            'groundwater': (current_data["groundwater"]["storage_coefficient"] * areas['groundwater'] *
                            (current_data["groundwater"]["water_level"] - prev_data["groundwater"]["water_level"])),
            'storage': ((current_data["stormwater"]["storage"] - prev_data["stormwater"]["storage"]) +
                        (current_data["wastewater"]["storage"] - prev_data["wastewater"]["storage"]) +
                        (current_data["reuse"]["wws_storage"] - prev_data["reuse"]["wws_storage"]))
        })

        storage_change = storage_changes.sum(axis=1)

        water_balance_value = inflow - outflow - storage_change

        water_balance_use = ((inflow_recycled - current_data["groundwater"]["leakage_depth"] * areas['groundwater']) +
                             current_data["reuse"]["rt_use"] +
                             current_data["reuse"]["ssg_use"] +
                             current_data["reuse"]["wws_use"] -
                             irrigation -
                             pd.Series([params[cell_id]['general']['indoor_water_use'] for cell_id in cell_ids], index=cell_ids))

        # Assign results to water_balance DataFrame
        water_balance.loc[(slice(None), t), "inflow"] = inflow
        water_balance.loc[(slice(None), t), "outflow"] = outflow
        water_balance.loc[(slice(None), t), "storage_change"] = storage_change
        water_balance.loc[(slice(None), t), "water_balance"] = water_balance_value
        water_balance.loc[(slice(None), t), "water_balance_use"] = water_balance_use

    return water_balance
