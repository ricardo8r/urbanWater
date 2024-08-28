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

from typing import Dict, List
import pandas as pd

def check_all(results: Dict[str, pd.DataFrame], params: Dict[int, Dict[str, Dict[str, float]]],
              forcing: pd.DataFrame) -> pd.DataFrame:
    """
    Compute the water balance for the entire urban water system.

    Args:
        results (Dict[str, pd.DataFrame]): Dictionary of DataFrames containing results for each module
        params (Dict[int, Dict[str, Dict[str, float]]]): Dictionary of parameter dictionaries for each grid cell
        forcing (pd.DataFrame): Climate forcing data

    Returns:
        pd.DataFrame: Water balance components for the entire system
    """
    num_cells = len(params)
    num_timesteps = len(forcing)

    water_balance = pd.DataFrame(index=forcing.index, columns=[
        "inflow", "outflow", "storage_change", "water_balance_1", "water_balance_2",
        "inflow_precipitation", "inflow_sewer", "inflow_imported", "inflow_recycled", "irrigation",
        "outflow_subsurface", "total_evaporation", "outflow_evapotranspiration", "outflow_sewer", "outflow_recycled"
    ])

    for t in range(1, num_timesteps):

        inflow = precipitation = inflow_sewer = inflow_imported = inflow_recycled = irrigation = 0
        outflow = evaporation_sf = evaporation_st = evaporation_vd = 0
        outflow_sewer = outflow_subsurface = outflow_recycled = total_evaporation = 0
        storage_change = impervious = pervious = raintank = 0
        vadose = groundwater = storage = 0

        for cell_id in range(num_cells):
            cell_params = params[cell_id]

            # Inflows
            precipitation += (cell_params["raintank"]["is_open"] * cell_params["raintank"]["area"] +
                              cell_params["stormwater"]["is_open"] * cell_params["stormwater"]["area"] +
                              cell_params["roof"]["area"] + cell_params["pervious"]["area"] +
                              cell_params["pavement"]["area"]) * forcing.precipitation[t]
            inflow_sewer += (results["stormwater"].loc[(cell_id, t), "upstream_inflow"] +
                             results["wastewater"].loc[(cell_id, t), "upstream_inflow"])
            imported += results["reuse"].loc[(cell_id, t), "imported_water"]
            inflow_recycled += (results["wastewater"].loc[(cell_id, t), "supply"] +
                                results["stormwater"].loc[(cell_id, t), "supply"])
            irrigation += (results["reuse"].loc[(cell_id, t), "irrigation_demand"] * (cell_params["pervious"]["area"] +
                           cell_params["pavement"]["area"] + cell_params["roof"]["area"]))

            # Outflows
            evaporation_sf += (results["roof"].loc[(cell_id, t), "evaporation"] * cell_params["roof"]["area"] +
                               results["pavement"].loc[(cell_id, t), "evaporation"] * cell_params["pavement"]["area"] +
                               results["pervious"].loc[(cell_id, t), "evaporation"] * cell_params["pervious"]["area"])
            evaporation_st += (results["raintank"].loc[(cell_id, t), "evaporation"] +
                               results["stormwater"].loc[(cell_id, t), "evaporation"])
            evaporation_vd += (results["vadose"].loc[(cell_id, t), "transpiration"] *
                               cell_params["vadose"]["area"])
            total_evaporation += (evaporation_sf + evaporation_st +  evaporation_vd)
            outflow_subsurface += (results["groundwater"].loc[(cell_id, t), "seepage"] +
                                   results["groundwater"].loc[(cell_id, t), "baseflow"])
            outflow_sewer += (results["wastewater"].loc[(cell_id, t), "sewer_inflow"] +
                              results["stormwater"].loc[(cell_id, t), "sewer_inflow"])
            outflow_recycled += (results["wastewater"].loc[(cell_id, t), "use"] +
                                 results["stormwater"].loc[(cell_id, t), "use"])

            # Storage changes
            impervious += (cell_params["roof"]["area"] * (results["roof"].loc[(cell_id, t), "storage"] -
                                                          results["roof"].loc[(cell_id, t-1), "storage"]) +
                           cell_params["pavement"]["area"] * (results["pavement"].loc[(cell_id, t), "storage"] -
                                                              results["pavement"].loc[(cell_id, t-1), "storage"]))
            pervious += cell_params["pervious"]["area"] * (results["pervious"].loc[(cell_id, t), "storage"] -
                                                           results["pervious"].loc[(cell_id, t-1), "storage"])
            raintank += (results["raintank"].loc[(cell_id, t), "storage"] -
                         results["raintank"].loc[(cell_id, t-1), "storage"])
            vadose += cell_params["vadose"]["area"] * (results["vadose"].loc[(cell_id, t), "moisture"] -
                                                                 results["vadose"].loc[(cell_id, t-1), "moisture"])
            groundwater += (results["groundwater"].loc[(cell_id, t), "storage_coefficient"] *
                            cell_params["groundwater"]["area"] *
                            (results["groundwater"].loc[(cell_id, t), "water_level"] -
                             results["groundwater"].loc[(cell_id, t-1), "water_level"]))
            storage += ((results["stormwater"].loc[(cell_id, t), "storage"] -
                         results["stormwater"].loc[(cell_id, t-1), "storage"]) +
                        (results["wastewater"].loc[(cell_id, t), "storage"] -
                         results["wastewater"].loc[(cell_id, t-1), "storage"]) +
                        (results["reuse"].loc[(cell_id, t), "wastewater_storage"] -
                         results["reuse"].loc[(cell_id, t-1), "wastewater_storage"]))

        inflow = precipitation + imported
        outflow = (total_evaporation + outflow_subsurface + results['aggregated'].loc[t, 'runoff'] +
                   results['aggregated'].loc[t, 'wastewater'])
        storage_change = impervious + pervious + raintank + vadose + groundwater + storage

        water_balance_1 = inflow - outflow - storage_change
        water_balance_2 = ((inflow + inflow_sewer + inflow_recycled) -
                           (total_evaporation + outflow_subsurface + outflow_sewer + outflow_recycled) - storage_change)

        water_balance.loc[forcing.index[t]] = [
            inflow, outflow, storage_change, water_balance_1, water_balance_2,
            precipitation, inflow_sewer, inflow_imported, inflow_recycled, irrigation,
            outflow_subsurface, total_evaporation, evaporation_vd, outflow_sewer, outflow_recycled
        ]

    return water_balance

def check_cell(results: Dict[str, pd.DataFrame], params: Dict[int, Dict[str, Dict[str, float]]],
               forcing: pd.DataFrame) -> List[pd.DataFrame]:
    """
    Compute the water balance for each grid cell in the urban water system.

    Args:
        results (Dict[str, pd.DataFrame]): Dictionary of DataFrames containing results for each module
        params (Dict[int, Dict[str, Dict[str, float]]]): Dictionary of parameter dictionaries for each grid cell
        forcing (pd.DataFrame): Climate forcing data

    Returns:
        List[pd.DataFrame]: List of DataFrames containing water balance components for each grid cell
    """
    num_cells = len(params)
    num_timesteps = len(forcing)
    water_balance_list = []

    for cell_id in range(num_cells):
        cell_params = params[cell_id]
        water_balance = pd.DataFrame(index=forcing.index, columns=[
            "inflow", "outflow", "storage_change", "water_balance", "water_balance_use"
        ])

        for t in range(1, num_timesteps):

            # Inflows
            precipitation = ((cell_params["roof"]["area"] + cell_params["pavement"]["area"] +
                              cell_params["pervious"]["area"] +
                              cell_params["raintank"]["is_open"] * cell_params["raintank"]["area"] +
                              cell_params["stormwater"]["is_open"] * cell_params["stormwater"]["area"]) *
                             forcing.precipitation[t])
            irrigation = (results["reuse"].loc[(cell_id, t), "irrigation_demand"] *
                          (cell_params["pervious"]["area"] + cell_params["pavement"]["area"] +
                           cell_params["roof"]["area"]))
            inflow_sewer = (results["stormwater"].loc[(cell_id, t), "upstream_inflow"] +
                            results["wastewater"].loc[(cell_id, t), "upstream_inflow"])
            inflow_recycled = (results["reuse"].loc[(cell_id, t), "imported_water"] +
                               results["wastewater"].loc[(cell_id, t), "supply"] +
                               results["stormwater"].loc[(cell_id, t), "supply"])
            inflow = precipitation + inflow_sewer + inflow_recycled

            # Outflows
            evaporation_sf = (results["roof"].loc[(cell_id, t), "evaporation"] * cell_params["roof"]["area"] +
                              results["pavement"].loc[(cell_id, t), "evaporation"] * cell_params["pavement"]["area"] +
                              results["pervious"].loc[(cell_id, t), "evaporation"] * cell_params["pervious"]["area"])
            evaporation_vd = results["vadose"].loc[(cell_id, t), "transpiration"] * cell_params["vadose"]["area"]
            evaporation_st = (results["raintank"].loc[(cell_id, t), "evaporation"] +
                              results["stormwater"].loc[(cell_id, t), "evaporation"])
            total_evaporation = evaporation_sf + evaporation_st +  evaporation_vd
            outflow_sewer = (results["wastewater"].loc[(cell_id, t), "sewer_inflow"] +
                             results["stormwater"].loc[(cell_id, t), "sewer_inflow"])
            outflow_subsurface = (results["groundwater"].loc[(cell_id, t), "seepage"] +
                                  results["groundwater"].loc[(cell_id, t), "baseflow"])
            outflow_recycled = (results["wastewater"].loc[(cell_id, t), "use"] +
                                results["stormwater"].loc[(cell_id, t), "use"])
            outflow = total_evaporation + outflow_sewer + outflow_subsurface + outflow_recycled

            # Storage changes
            impervious = ((results["roof"].loc[(cell_id, t), "storage"] -
                           results["roof"].loc[(cell_id, t-1), "storage"]) * cell_params["roof"]["area"] +
                          (results["pavement"].loc[(cell_id, t), "storage"] -
                           results["pavement"].loc[(cell_id, t-1), "storage"]) * cell_params["pavement"]["area"])
            pervious = (results["pervious"].loc[(cell_id, t), "storage"] -
                        results["pervious"].loc[(cell_id, t-1), "storage"]) * cell_params["pervious"]["area"]
            raintank = (results["raintank"].loc[(cell_id, t), "storage"] -
                        results["raintank"].loc[(cell_id, t-1), "storage"])
            vadose = (results["vadose"].loc[(cell_id, t), "moisture"] -
                      results["vadose"].loc[(cell_id, t-1), "moisture"]) * cell_params["vadose"]["area"]
            groundwater = ((results["groundwater"].loc[(cell_id, t), "storage_coefficient"] *
                            (results["groundwater"].loc[(cell_id, t-1), "water_level"] -
                             results["groundwater"].loc[(cell_id, t), "water_level"])) *
                           cell_params["groundwater"]["area"])
            storage = ((results["stormwater"].loc[(cell_id, t), "storage"] -
                        results["stormwater"].loc[(cell_id, t-1), "storage"]) +
                       (results["wastewater"].loc[(cell_id, t), "storage"] -
                        results["wastewater"].loc[(cell_id, t-1), "storage"]))
            storage_change = impervious + pervious + raintank + vadose + groundwater + storage

            water_balance_value = inflow - outflow - storage_change
            water_balance_use = ((inflow_recycled - results["groundwater"].loc[(cell_id, t), "leakage_depth"] *
                                  cell_params["groundwater"]["area"]) +
                                 results["raintank"].loc[(cell_id, t), "use"] +
                                 results["reuse"].loc[(cell_id, t), "subsurface_graywater"].use +
                                 results["reuse"].loc[(cell_id, t), "wastewater"].use -
                                 irrigation - cell_params["general"]["indoor_water_use"])

            water_balance.loc[forcing.index[t]] = [inflow, outflow, storage_change,
                                                   water_balance_value, water_balance_use]

        water_balance_list.append(water_balance)

    return water_balance_list
