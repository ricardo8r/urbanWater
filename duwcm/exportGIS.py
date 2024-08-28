from typing import List, Dict, Any
from pathlib import Path
import pandas as pd
from dynaconf import Dynaconf

def exportGIS(results: Dict[str, pd.DataFrame], params: List[Dict[str, Any]],
                   config: Dynaconf, flux_names: List[str], yearly_sum: bool = False) -> pd.DataFrame:
    """
    Export model results for GIS visualization.

    Args:
        results (Dict[str, pd.DataFrame]): Model results
        params (List[Dict[str, Any]]): List of parameter dictionaries for each grid cell
        config (Dynaconf): Configuration object
        flux_names (List[str]): Names of the fluxes to export
        yearly_sum (bool): If True, calculate yearly sums instead of daily values

    Returns:
        pd.DataFrame: Exported data with cell IDs and selected fluxes
    """
    export_data = pd.DataFrame()

    for flux in flux_names:
        module, variable = flux.split('.')
        flux_data = results[module][variable]

        if yearly_sum:
            flux_data = flux_data.groupby(flux_data.index.get_level_values('timestep').year).sum()
        else:
            flux_data = flux_data.unstack(level='cell')

        export_data[flux] = flux_data

    export_data['cell_id'] = [param['general']['cell_id'] for param in params]

    # Export to CSV
    output_dir = Path(config.output.output_directory)
    export_path = output_dir / f"{config.output.gis_export_filename}.csv"
    export_data.to_csv(export_path, index=False)

    return export_data
